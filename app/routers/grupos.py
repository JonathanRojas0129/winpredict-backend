import uuid
import random
import string
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Grupo, GrupoParticipante, User, RolGrupo
from app.schemas.grupos import (
    GrupoIn,
    ReglasIn,
    UnirseIn,
    UnirseOut,
    SolicitudOut,
    SolicitudesListOut,
    AprobarSolicitudOut,
    RechazarSolicitudOut,
)

router = APIRouter()

ESTADO_PENDIENTE = "pendiente"
ESTADO_APROBADO = "aprobado"
ESTADO_RECHAZADO = "rechazado"

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


def contar_aprobados(db: Session, grupo_id: uuid.UUID) -> int:
    return (
        db.query(GrupoParticipante)
        .filter(
            GrupoParticipante.grupo_id == grupo_id,
            GrupoParticipante.estado_participante == ESTADO_APROBADO,
        )
        .count()
    )


def obtener_participacion(
    db: Session, grupo_id: uuid.UUID, user_id: uuid.UUID
) -> GrupoParticipante | None:
    return (
        db.query(GrupoParticipante)
        .filter(
            GrupoParticipante.grupo_id == grupo_id,
            GrupoParticipante.user_id == user_id,
        )
        .first()
    )


def validar_acceso_grupo(participante: GrupoParticipante | None) -> None:
    if not participante:
        raise HTTPException(status_code=403, detail="No eres miembro de este grupo")
    if participante.estado_participante == ESTADO_PENDIENTE:
        raise HTTPException(
            status_code=403,
            detail="Tu solicitud de ingreso está pendiente de aprobación",
        )
    if participante.estado_participante == ESTADO_RECHAZADO:
        raise HTTPException(
            status_code=403,
            detail="Tu solicitud de ingreso fue rechazada",
        )


def validar_estado_solicitud_existente(participacion: GrupoParticipante) -> None:
    estado = participacion.estado_participante
    if estado == ESTADO_APROBADO:
        raise HTTPException(status_code=400, detail="Ya eres miembro de este grupo")
    if estado == ESTADO_PENDIENTE:
        raise HTTPException(
            status_code=400,
            detail="Ya tienes una solicitud pendiente para este grupo",
        )
    if estado == ESTADO_RECHAZADO:
        raise HTTPException(
            status_code=400,
            detail="Tu solicitud fue rechazada. Contacta al administrador del grupo.",
        )


def grupo_a_dict(
    grupo: Grupo,
    total_participantes: int,
    current_user_id: uuid.UUID,
    participante: GrupoParticipante | None,
) -> dict:
    return {
        "id": grupo.id,
        "nombre": grupo.nombre,
        "codigo_invitacion": grupo.codigo_invitacion,
        "max_participantes": grupo.max_participantes,
        "premio_valor": grupo.premio_valor,
        "premio_moneda": grupo.premio_moneda,
        "descripcion": grupo.descripcion,
        "pts_marcador_exacto": grupo.pts_marcador_exacto,
        "pts_ganador": grupo.pts_ganador,
        "pts_empate": grupo.pts_empate,
        "pts_gol": grupo.pts_gol,
        "pts_prediccion_unica": grupo.pts_prediccion_unica,
        "bono_dieciseisavos": grupo.bono_dieciseisavos,
        "bono_octavos": grupo.bono_octavos,
        "bono_cuartos": grupo.bono_cuartos,
        "bono_semifinales": grupo.bono_semifinales,
        "bono_final": grupo.bono_final,
        "total_participantes": total_participantes,
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
        estado_participante=ESTADO_APROBADO,
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

    grupo.pts_marcador_exacto = reglas.pts_marcador_exacto
    grupo.pts_ganador = reglas.pts_ganador
    grupo.pts_empate = reglas.pts_empate
    grupo.pts_gol = reglas.pts_gol
    grupo.pts_prediccion_unica = reglas.pts_prediccion_unica
    grupo.bono_dieciseisavos = reglas.bono_dieciseisavos
    grupo.bono_octavos = reglas.bono_octavos
    grupo.bono_cuartos = reglas.bono_cuartos
    grupo.bono_semifinales = reglas.bono_semifinales
    grupo.bono_final = reglas.bono_final

    db.commit()
    db.refresh(grupo)
    total = contar_aprobados(db, grupo.id)
    return grupo_a_dict(grupo, total, current_user.id, None)


# ─── POST /unirse — Solicitar ingreso a un grupo ─────────────────────────

@router.post("/unirse", status_code=202, response_model=UnirseOut)
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

    participacion = obtener_participacion(db, grupo.id, current_user.id)
    if participacion:
        validar_estado_solicitud_existente(participacion)

    total_aprobados = contar_aprobados(db, grupo.id)
    if total_aprobados >= grupo.max_participantes:
        raise HTTPException(status_code=400, detail="El grupo está lleno")

    participante = GrupoParticipante(
        grupo_id=grupo.id,
        user_id=current_user.id,
        rol=RolGrupo.player,
        estado_participante=ESTADO_PENDIENTE,
    )
    db.add(participante)
    db.commit()

    return UnirseOut(
        message="Solicitud enviada. El administrador del grupo debe aprobar tu ingreso.",
        grupo_nombre=grupo.nombre,
        grupo_id=str(grupo.id),
    )


# ─── GET /mis-grupos — Grupos del usuario (solo aprobados) ───────────────

@router.get("/mis-grupos")
def mis_grupos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    participaciones = (
        db.query(GrupoParticipante)
        .filter(
            GrupoParticipante.user_id == current_user.id,
            GrupoParticipante.estado_participante == ESTADO_APROBADO,
        )
        .all()
    )

    resultado = []
    for p in participaciones:
        grupo = db.query(Grupo).filter(Grupo.id == p.grupo_id).first()
        if not grupo:
            continue
        total = contar_aprobados(db, grupo.id)
        resultado.append({
            "id": str(grupo.id),
            "nombre": grupo.nombre,
            "codigo_invitacion": grupo.codigo_invitacion,
            "premio_valor": grupo.premio_valor,
            "premio_moneda": grupo.premio_moneda,
            "total_participantes": total,
            "max_participantes": grupo.max_participantes,
            "mi_rol": p.rol.value,
            "mis_puntos": p.total_puntos or 0,
            "mi_posicion": p.posicion,
            "estado": grupo.estado or "activo",
        })

    return resultado


# ─── GET /preview/{codigo} — Vista previa sin unirse ─────────────────────

@router.get("/preview/{codigo}")
def preview_grupo(
    codigo: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    grupo = db.query(Grupo).filter(
        Grupo.codigo_invitacion == codigo.upper()
    ).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Código de invitación inválido")

    participacion = obtener_participacion(db, grupo.id, current_user.id)
    if participacion:
        validar_estado_solicitud_existente(participacion)

    total = contar_aprobados(db, grupo.id)

    return {
        "nombre": grupo.nombre,
        "descripcion": grupo.descripcion,
        "total_participantes": total,
        "max_participantes": grupo.max_participantes,
        "premio_valor": grupo.premio_valor,
        "premio_moneda": grupo.premio_moneda,
        "estado": grupo.estado or "activo",
    }


# ─── GET /{grupo_id}/solicitudes — Pendientes (solo admin) ───────────────

@router.get("/{grupo_id}/solicitudes", response_model=SolicitudesListOut)
def listar_solicitudes(
    grupo_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    if not es_admin_del_grupo(db, grupo_id, current_user.id):
        raise HTTPException(
            status_code=403,
            detail="Solo el administrador del grupo puede ver las solicitudes",
        )

    filas = (
        db.query(GrupoParticipante, User)
        .join(User, User.id == GrupoParticipante.user_id)
        .filter(
            GrupoParticipante.grupo_id == grupo_id,
            GrupoParticipante.estado_participante == ESTADO_PENDIENTE,
        )
        .order_by(GrupoParticipante.unido_en.asc())
        .all()
    )

    solicitudes = [
        SolicitudOut(
            id=p.id,
            user_id=p.user_id,
            nombre=u.nombre,
            email=u.email,
            solicitado_en=p.unido_en,
        )
        for p, u in filas
    ]

    return SolicitudesListOut(solicitudes=solicitudes, total=len(solicitudes))


# ─── PATCH /{grupo_id}/solicitudes/{participante_id}/aprobar ─────────────

@router.patch(
    "/{grupo_id}/solicitudes/{participante_id}/aprobar",
    response_model=AprobarSolicitudOut,
)
def aprobar_solicitud(
    grupo_id: uuid.UUID,
    participante_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    if not es_admin_del_grupo(db, grupo_id, current_user.id):
        raise HTTPException(
            status_code=403,
            detail="Solo el administrador del grupo puede aprobar solicitudes",
        )

    participante = (
        db.query(GrupoParticipante)
        .filter(
            GrupoParticipante.id == participante_id,
            GrupoParticipante.grupo_id == grupo_id,
        )
        .first()
    )
    if not participante:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    if participante.estado_participante == ESTADO_APROBADO:
        raise HTTPException(status_code=400, detail="El usuario ya fue aprobado")

    if participante.estado_participante == ESTADO_RECHAZADO:
        raise HTTPException(
            status_code=400,
            detail="La solicitud fue rechazada. El usuario debe enviar una nueva solicitud.",
        )

    total_aprobados = contar_aprobados(db, grupo_id)
    if total_aprobados >= grupo.max_participantes:
        raise HTTPException(status_code=400, detail="El grupo está lleno")

    usuario = db.query(User).filter(User.id == participante.user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    participante.estado_participante = ESTADO_APROBADO
    db.add(participante)
    db.commit()

    return AprobarSolicitudOut(
        message="Usuario aprobado",
        user_email=usuario.email,
    )


# ─── PATCH /{grupo_id}/solicitudes/{participante_id}/rechazar ────────────

@router.patch(
    "/{grupo_id}/solicitudes/{participante_id}/rechazar",
    response_model=RechazarSolicitudOut,
)
def rechazar_solicitud(
    grupo_id: uuid.UUID,
    participante_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    if not es_admin_del_grupo(db, grupo_id, current_user.id):
        raise HTTPException(
            status_code=403,
            detail="Solo el administrador del grupo puede rechazar solicitudes",
        )

    participante = (
        db.query(GrupoParticipante)
        .filter(
            GrupoParticipante.id == participante_id,
            GrupoParticipante.grupo_id == grupo_id,
        )
        .first()
    )
    if not participante:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    if participante.user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="No puedes rechazar tu propia solicitud",
        )

    if participante.estado_participante == ESTADO_RECHAZADO:
        raise HTTPException(status_code=400, detail="El usuario ya fue rechazado")

    if participante.estado_participante == ESTADO_APROBADO:
        raise HTTPException(
            status_code=400,
            detail="El usuario ya es miembro aprobado del grupo",
        )

    usuario = db.query(User).filter(User.id == participante.user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    participante.estado_participante = ESTADO_RECHAZADO
    db.add(participante)
    db.commit()

    return RechazarSolicitudOut(
        message="Usuario rechazado",
        user_email=usuario.email,
    )


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

    participante = obtener_participacion(db, grupo_id, current_user.id)
    validar_acceso_grupo(participante)

    total = contar_aprobados(db, grupo_id)

    return grupo_a_dict(grupo, total, current_user.id, participante)
