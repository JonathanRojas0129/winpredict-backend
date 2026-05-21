"""
Registro de auditoría de autenticación (auth_logs).
Nunca interrumpe el flujo principal.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import AuthLog

logger = logging.getLogger(__name__)

ACCION_LOGIN_OK = "login_ok"
ACCION_LOGIN_FAIL = "login_fail"
ACCION_LOGIN_BLOQUEADO = "login_bloqueado"
ACCION_PASSWORD_CHANGE = "password_change"
ACCION_PASSWORD_RESET = "password_reset"
ACCION_CUENTA_DESBLOQUEADA = "cuenta_desbloqueada"


def registrar_auth_log(
    db: Session,
    *,
    accion: str,
    email: str,
    user_id: Optional[uuid.UUID] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Inserta en auth_logs; errores se registran sin propagar."""
    try:
        entrada = AuthLog(
            user_id=user_id,
            email=email.strip().lower(),
            accion=accion,
            ip=ip or "desconocida",
            user_agent=user_agent,
        )
        db.add(entrada)
        db.commit()
    except Exception as exc:
        logger.warning("No se pudo registrar auth_log (%s): %s", accion, exc)
        try:
            db.rollback()
        except Exception:
            pass
