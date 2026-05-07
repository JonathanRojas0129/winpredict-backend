"""
routers/partidos.py
Refactorizado: Lógica de negocio separada de los esquemas de validación.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Partido, EstadoPartido, User

# ─── Schemas Importados ──────────────────────────────────────────────────
# Importamos el esquema desde la nueva carpeta centralizada
from app.schemas.partidos import PartidoOut

router = APIRouter()

# ─── Endpoints ───────────────────────────────────────────────────────────

@router.get("/", response_model=list[PartidoOut])
def listar_partidos(
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Lista todos los partidos registrados. 
    Permite filtrar por estado (pendiente, vivo, finalizado).
    """
    q = db.query(Partido)
    
    if estado:
        # Validamos que el estado enviado sea uno de los permitidos en el Enum
        q = q.filter(Partido.estado == estado)
        
    return q.order_by(Partido.fecha_hora).all()


@router.get("/{partido_id}", response_model=PartidoOut)
def detalle_partido(
    partido_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Obtiene la información detallada de un solo partido por su ID.
    """
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    
    if not partido:
        raise HTTPException(
            status_code=404, 
            detail="Partido no encontrado"
        )
        
    return partido
