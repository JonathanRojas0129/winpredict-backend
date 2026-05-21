import secrets
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


# ─── Contraseñas ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    password = password[:72]  # truncar a 72 bytes máximo
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        plain = plain[:72]
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ─── JWT ────────────────────────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── Dependency: usuario actual ─────────────────────────────────────────

def tiene_pro_vigente(user) -> bool:
    """True si el usuario tiene plan PRO activo (incluye ventana hasta pro_expira_en)."""
    if not getattr(user, "es_pro", False):
        return False
    exp = getattr(user, "pro_expira_en", None)
    if exp is None:
        return True
    now = datetime.now(timezone.utc)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp > now


def require_internal_api_key(
    x_internal_key: str | None = Header(default=None, alias="X-Internal-Key"),
) -> None:
    """Protege endpoints llamados solo por jobs internos (p. ej. score_updater)."""
    expected = (settings.INTERNAL_API_KEY or "").strip()
    if not expected:
        if settings.DEBUG:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_API_KEY no está configurada; no se aceptan jobs internos.",
        )
    provided = (x_internal_key or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    from app.models.models import User
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token inválido")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


def get_current_pro_user(current_user=Depends(get_current_user)):
    """Solo permite el acceso a usuarios PRO con suscripción vigente."""
    if not tiene_pro_vigente(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta función requiere WinPredict PRO activo",
        )
    return current_user


def _admin_email_set() -> set[str]:
    raw = (settings.ADMIN_EMAILS or "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def require_admin(current_user=Depends(get_current_user)):
    """Solo usuarios cuyo email está en ADMIN_EMAILS (.env)."""
    if current_user.email.lower() not in _admin_email_set():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos de administrador.",
        )
    return current_user
