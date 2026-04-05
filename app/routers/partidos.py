"""
routers/partidos.py
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Partido, EstadoPartido, FasePartido, User

router = APIRouter()

class PartidoOut(BaseModel):
    id: uuid.UUID
    equipo_local: str
    equipo_visitante: str
    bandera_local: Optional[str]
    bandera_visitante: Optional[str]
    fecha_hora: datetime
    fase: str
    goles_local: Optional[int]
    goles_visitante: Optional[int]
    estado: str
    cierre_pronosticos: datetime

    class Config:
        from_attributes = True

@router.get("/", response_model=list[PartidoOut])
def listar_partidos(
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Partido)
    if estado:
        q = q.filter(Partido.estado == estado)
    return q.order_by(Partido.fecha_hora).all()

@router.get("/{partido_id}", response_model=PartidoOut)
def detalle_partido(
    partido_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido
