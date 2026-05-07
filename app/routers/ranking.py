"""
routers/ranking.py
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import GrupoParticipante, User, Grupo

router = APIRouter()

@router.get("/{grupo_id}")
def ranking_grupo(
    grupo_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    participantes = (
        db.query(GrupoParticipante, User)
        .join(User, User.id == GrupoParticipante.user_id)
        .filter(GrupoParticipante.grupo_id == grupo_id)
        .order_by(GrupoParticipante.total_puntos.desc())
        .all()
    )

    if not participantes:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")

    resultado = []
    for i, (p, u) in enumerate(participantes, start=1):
        resultado.append({
            "posicion":     i,
            "user_id":      str(p.user_id),
            "nombre":       u.nombre,
            "avatar_url":   u.avatar_url,
            "es_pro":       u.es_pro,
            "total_puntos": p.total_puntos,
            "es_yo":        p.user_id == current_user.id,
        })
    return resultado
