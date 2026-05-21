"""
Router de autenticación — registro, login, perfil, contraseña y recuperación.
Incluye rate limiting, bloqueo de cuenta y auditoría auth_logs.
"""

import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.ip_utils import get_client_ip

from app.core.auth_audit import (
    ACCION_CUENTA_DESBLOQUEADA,
    ACCION_LOGIN_BLOQUEADO,
    ACCION_LOGIN_FAIL,
    ACCION_LOGIN_OK,
    ACCION_PASSWORD_CHANGE,
    ACCION_PASSWORD_RESET,
    registrar_auth_log,
)
from app.core.database import get_db
from app.core.limiter import limiter
from app.core.reset_token import (
    create_reset_token,
    decode_and_validate_reset_token,
    mark_reset_token_used,
)
from app.core.security import (
    bearer_scheme,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.core.supabase_client import (
    ensure_supabase_auth_user,
    sign_out_other_supabase_sessions,
    update_supabase_auth_password,
)
from app.models.models import ProveedorAuth, User
from app.schemas.auth import (
    ChangePasswordIn,
    ForgotPasswordGoogleOut,
    ForgotPasswordIn,
    ForgotPasswordLocalOut,
    LoginIn,
    PasswordChangeOut,
    ResetPasswordIn,
    ResetPasswordOut,
    TokenOut,
    UserOut,
    UserRegister,
    ValidateResetTokenOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()

LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30

def _client_user_agent(request: Request) -> str | None:
    return request.headers.get("User-Agent")


def _locked_until_hora(locked_until: datetime) -> str:
    return locked_until.strftime("%H:%M")


def _raise_account_locked(user: User, db: Session, request: Request) -> None:
    hora = _locked_until_hora(user.locked_until)
    registrar_auth_log(
        db,
        accion=ACCION_LOGIN_BLOQUEADO,
        email=user.email,
        user_id=user.id,
        ip=get_client_ip(request),
        user_agent=_client_user_agent(request),
    )
    raise HTTPException(
        status_code=status.HTTP_423_LOCKED,
        detail=(
            f"Cuenta bloqueada hasta las {hora}. "
            "Contacta al administrador si crees que es un error."
        ),
    )


def _check_account_lock(user: User, db: Session, request: Request) -> None:
    if user.locked_until and user.locked_until > datetime.utcnow():
        _raise_account_locked(user, db, request)


# ─── Endpoints existentes (lógica preservada + capas de seguridad) ─────────


@router.post("/registro", response_model=TokenOut, status_code=201)
@limiter.limit("3/hour")
def registro(
    request: Request,
    data: UserRegister,
    db: Session = Depends(get_db),
):
    """Registrar un nuevo usuario."""
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta con ese correo",
        )
    user = User(
        nombre=data.nombre,
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        proveedor_auth=ProveedorAuth.local,
        failed_login_attempts=0,
        locked_until=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    ensure_supabase_auth_user(user.email, data.password)

    token = create_access_token({"sub": str(user.id)})
    return TokenOut(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenOut)
@limiter.limit("5/minute")
def login(
    request: Request,
    data: LoginIn,
    db: Session = Depends(get_db),
):
    """Iniciar sesión con email y contraseña."""
    email = data.email.lower()
    ip = get_client_ip(request)
    ua = _client_user_agent(request)
    user = db.query(User).filter(User.email == email).first()

    if user:
        _check_account_lock(user, db, request)

    credenciales_validas = (
        user is not None
        and user.password_hash
        and verify_password(data.password, user.password_hash)
    )

    if not credenciales_validas:
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= LOCKOUT_MAX_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(
                    minutes=LOCKOUT_DURATION_MINUTES
                )
                db.add(user)
                db.commit()
                _raise_account_locked(user, db, request)
            db.add(user)
            db.commit()
            registrar_auth_log(
                db,
                accion=ACCION_LOGIN_FAIL,
                email=email,
                user_id=user.id,
                ip=ip,
                user_agent=ua,
            )
        else:
            registrar_auth_log(
                db,
                accion=ACCION_LOGIN_FAIL,
                email=email,
                user_id=None,
                ip=ip,
                user_agent=ua,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)
    db.commit()

    registrar_auth_log(
        db,
        accion=ACCION_LOGIN_OK,
        email=user.email,
        user_id=user.id,
        ip=ip,
        user_agent=ua,
    )

    token = create_access_token({"sub": str(user.id)})
    return TokenOut(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Obtener el perfil del usuario autenticado."""
    return current_user


@router.patch("/cambiar-contrasena", response_model=PasswordChangeOut)
def cambiar_contrasena(
    data: ChangePasswordIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Actualiza la contraseña del usuario autenticado (solo cuentas locales)."""
    if current_user.proveedor_auth != ProveedorAuth.local:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta cuenta usa inicio de sesión externo y no permite cambiar la contraseña aquí.",
        )
    if not current_user.password_hash or not verify_password(
        data.current_password, current_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta.",
        )

    current_user.password_hash = hash_password(data.new_password)
    db.add(current_user)
    db.commit()

    update_supabase_auth_password(current_user.email, data.new_password)
    sign_out_other_supabase_sessions(credentials.credentials)

    registrar_auth_log(
        db,
        accion=ACCION_PASSWORD_CHANGE,
        email=current_user.email,
        user_id=current_user.id,
        ip="sesion_autenticada",
        user_agent=None,
    )

    return PasswordChangeOut()


@router.post("/forgot-password")
@limiter.limit("3/15minutes")
def forgot_password(
    request: Request,
    data: ForgotPasswordIn,
    db: Session = Depends(get_db),
):
    """
    Consulta users por email y proveedor_auth.
    - 404 si no existe
    - 200 + google=true si es Google
    - 200 + reset_token si es local (JWT 15 min)
    """
    email = data.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontramos una cuenta con ese correo.",
        )

    if user.proveedor_auth == ProveedorAuth.google:
        return ForgotPasswordGoogleOut()

    reset_token = create_reset_token(str(user.id), user.email)
    return ForgotPasswordLocalOut(reset_token=reset_token)


@router.get("/validate-reset-token", response_model=ValidateResetTokenOut)
def validate_reset_token(token: str, db: Session = Depends(get_db)):
    """Verifica que el JWT temporal sea válido y no haya sido usado."""
    payload = decode_and_validate_reset_token(token, db)
    return ValidateResetTokenOut(email=payload["email"])


@router.post("/reset-password", response_model=ResetPasswordOut)
@limiter.limit("3/15minutes")
def reset_password(
    request: Request,
    data: ResetPasswordIn,
    db: Session = Depends(get_db),
):
    """
    Valida JWT temporal, actualiza password_hash y Supabase Auth, invalida jti.
    """
    payload = decode_and_validate_reset_token(data.token, db)
    user_id = payload.get("user_id")
    email = (payload.get("email") or "").lower()
    jti = payload.get("jti")

    try:
        uid = uuid.UUID(str(user_id))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El enlace expiró. Solicita uno nuevo.",
        ) from exc

    user = db.query(User).filter(User.id == uid, User.email == email).first()
    if not user or user.proveedor_auth != ProveedorAuth.local:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El enlace expiró. Solicita uno nuevo.",
        )

    user.password_hash = hash_password(data.new_password)
    db.add(user)
    mark_reset_token_used(jti, db)
    db.commit()

    update_supabase_auth_password(email, data.new_password)

    registrar_auth_log(
        db,
        accion=ACCION_PASSWORD_RESET,
        email=email,
        user_id=user.id,
        ip=get_client_ip(request),
        user_agent=_client_user_agent(request),
    )

    return ResetPasswordOut()
