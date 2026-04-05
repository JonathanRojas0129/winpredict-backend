import uuid
import random
import string
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Grupo, GrupoParticipante, User, RolGrupo

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────

class ReglasIn(BaseModel):
    """Reglas de puntuación configurables por el admin. Rango: 0-10 pts."""
    pts_marcador_exacto:  int = Field(default=5,  ge=0, le=10)
    pts_ganador:          int = Field(default=3,  ge=0, le=10)
    pts_empate:           int = Field(default=2,  ge=0, le=10)
    pts_gol:              int = Field(default=1,  ge=0, le=10)
    pts_prediccion_unica: int = Field(default=2,  ge=0, le=10)
    bono_dieciseisavos:   int = Field(default=1,  ge=0, le=10)
    bono_octavos:         int = Field(default=2,  ge=0, le=10)
    bono_cuartos:         int = Field(default=3,  ge=0, le=10)
    bono_semifinales:     int = Field(default=4,  ge=0, le=10)
    bono_final:           int = Field(default=5,  ge=0, le=10)


class GrupoIn(BaseModel):
    nombre:            str
    max_participantes: int = 50
    premio_valor:      Optional[float] = None
    premio_moneda:     Optional[str]  = None
    descripcion:       Optional[str]  = None
    reglas:            ReglasIn = ReglasIn()


class GrupoOut(BaseModel):
    id:                   uuid.UUID
    nombre:               str
    codigo_invitacion:    str
    max_participantes:    int
    premio_valor:         Optional[float]
    premio_moneda:        Optional[str]
    descripcion:          Optional[str]
    pts_marcador_exacto:  int
    pts_ganador:          int
    pts_empate:           int
    pts_gol:              int
    pts_prediccion_unica: int
    bono_dieciseisavos:   int
    bono_octavos:         int
    bono_cuartos:         int
    bono_semifinales:     int
    bono_final:           int
    total_participantes:  int = 0

    class Config:
        from_attributes = True


class UnirseIn(BaseModel):
    codigo_invitacion: str


# ─── Helpers ─────────────────────────────────────────────────────────────

def generar_codigo(db: Session, largo: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    while True:
        codigo = "".join(random.choices(chars, k=largo))
        if not db.query(Grupo).filter(Grupo.codigo_invitacion == codigo).first():
            return codigo


def es_admin_del_grupo(db: Session, grupo_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    p = db.query(GrupoParticipante).filter(
        GrupoParticipante.grupo_id == grupo_id,
        GrupoParticipante.user_id == user_id,
        GrupoParticipante.rol == RolGrupo.admin,
    ).first()
    return p is not None


# ─── Endpoints ───────────────────────────────────────────────────────────

@router.post("/", response_model=GrupoOut, status_code=201)
def crear_grupo(
    data: GrupoIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crear grupo con reglas de puntuación personalizadas."""
    r = data.reglas
    grupo = Grupo(
        creador_id=current_user.id,
        nombre=data.nombre,
        codigo_invitacion=generar_codigo(db),
        max_participantes=data.max_participantes,
        premio_valor=data.premio_valor,
        premio_moneda=data.premio_moneda.upper() if data.premio_moneda else None,
        descripcion=data.descripcion,
        pts_marcador_exacto=r.pts_marcador_exacto,
        pts_ganador=r.pts_ganador,
        pts_empate=r.pts_empate,
        pts_gol=r.pts_gol,
        pts_prediccion_unica=r.pts_prediccion_unica,
        bono_dieciseisavos=r.bono_dieciseisavos,
        bono_octavos=r.bono_octavos,
        bono_cuartos=r.bono_cuartos,
        bono_semifinales=r.bono_semifinales,
        bono_final=r.bono_final,
    )
    db.add(grupo)
    db.flush()

    participante = GrupoParticipante(
        grupo_id=grupo.id,
        user_id=current_user.id,
        rol=RolGrupo.admin,
    )
    db.add(participante)
    db.commit()
    db.refresh(grupo)
    return {**GrupoOut.from_orm(grupo).dict(), "total_participantes": 1}


@router.put("/{grupo_id}/reglas", response_model=GrupoOut)
def actualizar_reglas(
    grupo_id: uuid.UUID,
    reglas: ReglasIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Solo el admin puede actualizar las reglas del grupo."""
    grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    if not es_admin_del_grupo(db, grupo_id, current_user.id):
        raise HTTPException(status_code=403, detail="Solo el admin puede cambiar las reglas")

    grupo.pts_marcador_exacto  = reglas.pts_marcador_exacto
    grupo.pts_ganador          = reglas.pts_ganador
    grupo.pts_empate           = reglas.pts_empate
    grupo.pts_gol              = reglas.pts_gol
    grupo.pts_prediccion_unica = reglas.pts_prediccion_unica
    grupo.bono_dieciseisavos   = reglas.bono_dieciseisavos
    grupo.bono_octavos         = reglas.bono_octavos
    grupo.bono_cuartos         = reglas.bono_cuartos
    grupo.bono_semifinales     = reglas.bono_semifinales
    grupo.bono_final           = reglas.bono_final

    db.commit()
    db.refresh(grupo)
    total = db.query(GrupoParticipante).filter(GrupoParticipante.grupo_id == grupo.id).count()
    return {**GrupoOut.from_orm(grupo).dict(), "total_participantes": total}


@router.get("/{grupo_id}/reglas")
def ver_reglas(
    grupo_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Ver las reglas de puntuación vigentes de un grupo."""
    grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    return {
        "grupo_id":             str(grupo_id),
        "grupo_nombre":         grupo.nombre,
        "pts_marcador_exacto":  grupo.pts_marcador_exacto,
        "pts_ganador":          grupo.pts_ganador,
        "pts_empate":           grupo.pts_empate,
        "pts_gol":              grupo.pts_gol,
        "pts_prediccion_unica": grupo.pts_prediccion_unica,
        "bono_dieciseisavos":   grupo.bono_dieciseisavos,
        "bono_octavos":         grupo.bono_octavos,
        "bono_cuartos":         grupo.bono_cuartos,
        "bono_semifinales":     grupo.bono_semifinales,
        "bono_final":           grupo.bono_final,
    }


@router.post("/unirse", status_code=200)
def unirse_grupo(
    data: UnirseIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unirse a un grupo con código de invitación."""
    grupo = db.query(Grupo).filter(
        Grupo.codigo_invitacion == data.codigo_invitacion.upper()
    ).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Código de invitación no válido")

    ya_esta = db.query(GrupoParticipante).filter(
        GrupoParticipante.grupo_id == grupo.id,
        GrupoParticipante.user_id == current_user.id,
    ).first()
    if ya_esta:
        raise HTTPException(status_code=400, detail="Ya eres parte de este grupo")

    total = db.query(GrupoParticipante).filter(GrupoParticipante.grupo_id == grupo.id).count()
    if total >= grupo.max_participantes:
        raise HTTPException(status_code=400, detail="El grupo ya está lleno")

    db.add(GrupoParticipante(
        grupo_id=grupo.id,
        user_id=current_user.id,
        rol=RolGrupo.player,
    ))
    db.commit()
    return {"mensaje": f"Te uniste a {grupo.nombre} exitosamente", "grupo_id": str(grupo.id)}


@router.get("/mis-grupos")
def mis_grupos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Listar todos los grupos del usuario autenticado."""
    participaciones = db.query(GrupoParticipante).filter(
        GrupoParticipante.user_id == current_user.id
    ).all()
    resultado = []
    for p in participaciones:
        grupo = p.grupo
        total = db.query(GrupoParticipante).filter(GrupoParticipante.grupo_id == grupo.id).count()
        resultado.append({
            "id":                  str(grupo.id),
            "nombre":              grupo.nombre,
            "codigo_invitacion":   grupo.codigo_invitacion,
            "premio_valor":        grupo.premio_valor,
            "premio_moneda":       grupo.premio_moneda,
            "total_participantes": total,
            "max_participantes":   grupo.max_participantes,
            "mi_rol":              p.rol,
            "mis_puntos":          p.total_puntos,
            "mi_posicion":         p.posicion,
            "estado":              grupo.estado,
        })
    return resultado
