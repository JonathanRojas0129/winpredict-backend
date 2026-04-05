"""
routers/ranking.py
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import GrupoParticipante, User

router = APIRouter()

@router.get("/{grupo_id}")
def ranking_grupo(
    grupo_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ranking de participantes en un grupo ordenado por puntos."""
    participantes = db.query(GrupoParticipante).filter(
        GrupoParticipante.grupo_id == grupo_id
    ).order_by(GrupoParticipante.total_puntos.desc()).all()

    if not participantes:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")

    resultado = []
    for i, p in enumerate(participantes, start=1):
        resultado.append({
            "posicion": i,
            "user_id": str(p.user_id),
            "nombre": p.user.nombre,
            "avatar_url": p.user.avatar_url,
            "es_pro": p.user.es_pro,
            "total_puntos": p.total_puntos,
            "es_yo": p.user_id == current_user.id,
        })
    return resultado
