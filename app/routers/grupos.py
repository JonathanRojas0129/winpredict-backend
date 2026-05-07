import uuid
import random
import string
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Grupo, GrupoParticipante, User, RolGrupo
from app.schemas.grupos import GrupoIn, GrupoOut, ReglasIn, UnirseIn

router = APIRouter()

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
        GrupoParticipante.user_id  == user_id,
        GrupoParticipante.rol      == RolGrupo.admin,
    ).first()
    return p is not None

def grupo_a_dict(grupo: Grupo, total_participantes: int, current_user_id: uuid.UUID, participante: GrupoParticipante | None) -> dict:
    return {
        "id":                   grupo.id,
        "nombre":               grupo.nombre,
        "codigo_invitacion":    grupo.codigo_invitacion,
        "max_participantes":    grupo.max_participantes,
        "premio_valor":         grupo.premio_valor,
        "premio_moneda":        grupo.premio_moneda,
        "descripcion":          grupo.descripcion,
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
        "total_participantes":  total_participantes,
    }

# ─── POST / — Crear grupo ─────────────────────────────────────────────────

@router.post("/", status_code=201)
def crear_grupo(
    data: GrupoIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = data.reglas
    grupo = Grupo(
        creador_id=        current_user.id,
        nombre=            data.nombre,
        codigo_invitacion= generar_codigo(db),
        max_participantes= data.max_participantes,
        premio_valor=      data.premio_valor,
        premio_moneda=     data.premio_moneda.upper() if data.premio_moneda else None,
        descripcion=       data.descripcion,
        pts_marcador_exacto=  r.pts_marcador_exacto,
        pts_ganador=          r.pts_ganador,
        pts_empate=           r.pts_empate,
        pts_gol=              r.pts_gol,
        pts_prediccion_unica= r.pts_prediccion_unica,
        bono_dieciseisavos=   r.bono_dieciseisavos,
        bono_octavos=         r.bono_octavos,
        bono_cuartos=         r.bono_cuartos,
        bono_semifinales=     r.bono_semifinales,
        bono_final=           r.bono_final,
    )
    db.add(grupo)
    db.flush()

    participante = GrupoParticipante(
        grupo_id= grupo.id,
        user_id=  current_user.id,
        rol=      RolGrupo.admin,
    )
    db.add(participante)
    db.commit()
    db.refresh(grupo)

    return grupo_a_dict(grupo, 1, current_user.id, participante)


# ─── PUT /{grupo_id}/reglas — Actualizar reglas ───────────────────────────

@router.put("/{grupo_id}/reglas")
def actualizar_reglas(
    grupo_id: uuid.UUID,
    reglas: ReglasIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    return grupo_a_dict(grupo, total, current_user.id, None)


# ─── POST /unirse — Unirse a un grupo ────────────────────────────────────

@router.post("/unirse")
def unirse_grupo(
    data: UnirseIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    grupo = db.query(Grupo).filter(
        Grupo.codigo_invitacion == data.codigo_invitacion.upper()
    ).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Código de invitación inválido")

    # Verificar si ya es miembro
    ya_miembro = db.query(GrupoParticipante).filter(
        GrupoParticipante.grupo_id == grupo.id,
        GrupoParticipante.user_id  == current_user.id,
    ).first()
    if ya_miembro:
        raise HTTPException(status_code=400, detail="Ya eres miembro de este grupo")

    # Verificar capacidad
    total = db.query(GrupoParticipante).filter(
        GrupoParticipante.grupo_id == grupo.id
    ).count()
    if total >= grupo.max_participantes:
        raise HTTPException(status_code=400, detail="El grupo está lleno")

    participante = GrupoParticipante(
        grupo_id= grupo.id,
        user_id=  current_user.id,
        rol=      RolGrupo.player,
    )
    db.add(participante)
    db.commit()

    return grupo_a_dict(grupo, total + 1, current_user.id, participante)


# ─── GET /mis-grupos — Grupos del usuario ────────────────────────────────

@router.get("/mis-grupos")
def mis_grupos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    participaciones = db.query(GrupoParticipante).filter(
        GrupoParticipante.user_id == current_user.id
    ).all()

    resultado = []
    for p in participaciones:
        grupo = db.query(Grupo).filter(Grupo.id == p.grupo_id).first()
        if not grupo:
            continue
        total = db.query(GrupoParticipante).filter(
            GrupoParticipante.grupo_id == grupo.id
        ).count()
        resultado.append({
            "id":                   str(grupo.id),
            "nombre":               grupo.nombre,
            "codigo_invitacion":    grupo.codigo_invitacion,
            "premio_valor":         grupo.premio_valor,
            "premio_moneda":        grupo.premio_moneda,
            "total_participantes":  total,
            "max_participantes":    grupo.max_participantes,
            "mi_rol":               p.rol.value,
            "mis_puntos":           p.total_puntos or 0,
            "mi_posicion":          p.posicion,
            "estado":               grupo.estado or "activo",
        })

    return resultado


# ─── GET /{grupo_id} — Detalle de un grupo ───────────────────────────────

@router.get("/{grupo_id}")
def detalle_grupo(
    grupo_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")

    participante = db.query(GrupoParticipante).filter(
        GrupoParticipante.grupo_id == grupo_id,
        GrupoParticipante.user_id  == current_user.id,
    ).first()
    if not participante:
        raise HTTPException(status_code=403, detail="No eres miembro de este grupo")

    total = db.query(GrupoParticipante).filter(
        GrupoParticipante.grupo_id == grupo_id
    ).count()

    return grupo_a_dict(grupo, total, current_user.id, participante)