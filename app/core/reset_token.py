"""
JWT temporal de un solo uso para restablecer contraseña (15 minutos).
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import UsedToken

RESET_TOKEN_EXPIRE_MINUTES = 15
RESET_PURPOSE = "reset"


def create_reset_token(user_id: str, email: str) -> str:
    """Genera JWT firmado con jti único para uso en /reset-password."""
    jti = str(uuid.uuid4())
    expire = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    payload = {
        "user_id": str(user_id),
        "email": email.strip().lower(),
        "purpose": RESET_PURPOSE,
        "jti": jti,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_and_validate_reset_token(token: str, db: Session) -> dict:
    """
    Verifica firma, expiración, purpose y que el jti no haya sido usado.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El enlace expiró. Solicita uno nuevo.",
        ) from exc

    if payload.get("purpose") != RESET_PURPOSE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El enlace expiró. Solicita uno nuevo.",
        )

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El enlace expiró. Solicita uno nuevo.",
        )

    if db.query(UsedToken).filter(UsedToken.jti == jti).first():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El enlace expiró o ya fue utilizado. Solicita uno nuevo.",
        )

    return payload


def mark_reset_token_used(jti: str, db: Session) -> None:
    """Registra el jti como usado (token de un solo uso). El commit lo hace el caller."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    db.add(UsedToken(jti=jti, used_at=now, expires_at=expires_at))
