"""
Endpoints de administración (desbloqueo de cuentas, etc.).
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth_audit import ACCION_CUENTA_DESBLOQUEADA, registrar_auth_log
from app.core.database import get_db
from app.core.security import require_admin
from app.models.models import User
from app.schemas.auth import AdminUnlockIn, AdminUnlockOut
from app.core.ip_utils import get_client_ip

router = APIRouter()


@router.post("/desbloquear-cuenta", response_model=AdminUnlockOut)
def desbloquear_cuenta(
    request: Request,
    data: AdminUnlockIn,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Resetea intentos fallidos y bloqueo temporal de una cuenta."""
    email = data.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontramos una cuenta con ese correo.",
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)
    db.commit()

    registrar_auth_log(
        db,
        accion=ACCION_CUENTA_DESBLOQUEADA,
        email=email,
        user_id=user.id,
        ip=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )

    return AdminUnlockOut(email=email)
