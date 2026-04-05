import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    Pronostico, Partido, Grupo, GrupoParticipante,
    User, FuentePronostico, FasePartido
)

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────

class PronosticoIn(BaseModel):
    partido_id:      uuid.UUID
    grupo_id:        uuid.UUID
    goles_local:     int
    goles_visitante: int


class PronosticoOut(BaseModel):
    id:                uuid.UUID
    partido_id:        uuid.UUID
    grupo_id:          uuid.UUID
    goles_local:       int
    goles_visitante:   int
    puntos_obtenidos:  int | None
    fuente:            str
    fue_autocompletado: bool
    registrado_en:     datetime

    class Config:
        from_attributes = True


# ─── Lógica de puntuación dinámica ───────────────────────────────────────

def calcular_puntos(
    pred_local:     int,
    pred_visitante: int,
    real_local:     int,
    real_visitante: int,
    fase:           str,
    grupo:          Grupo,
    clasificado_local: bool | None = None,
    es_prediccion_unica: bool = False,
) -> dict:
    """
    Calcula los puntos usando las reglas configuradas por el admin del grupo.
    Retorna el total y el detalle del desglose.
    """
    puntos      = 0
    desglose    = {}

    # ── Marcador exacto ──────────────────────────────────────────────────
    if pred_local == real_local and pred_visitante == real_visitante:
        puntos += grupo.pts_marcador_exacto
        desglose["marcador_exacto"] = grupo.pts_marcador_exacto

        # Goles acertados (aplica solo si NO hay marcador exacto para no duplicar)
        # en este caso no sumamos goles por separado, ya el exacto los incluye
    else:
        # ── Ganador acertado ─────────────────────────────────────────────
        local_gana_pred  = pred_local > pred_visitante
        local_gana_real  = real_local > real_visitante
        visita_gana_pred = pred_local < pred_visitante
        visita_gana_real = real_local < real_visitante

        if (local_gana_pred and local_gana_real) or (visita_gana_pred and visita_gana_real):
            puntos += grupo.pts_ganador
            desglose["ganador_acertado"] = grupo.pts_ganador

        # ── Empate acertado ──────────────────────────────────────────────
        elif pred_local == pred_visitante and real_local == real_visitante:
            puntos += grupo.pts_empate
            desglose["empate_acertado"] = grupo.pts_empate

        # ── Goles acertados (por cada gol que coincide) ──────────────────
        if grupo.pts_gol > 0:
            goles_coinciden = 0
            if pred_local == real_local:
                goles_coinciden += 1
            if pred_visitante == real_visitante:
                goles_coinciden += 1
            if goles_coinciden > 0:
                bonus_goles = goles_coinciden * grupo.pts_gol
                puntos += bonus_goles
                desglose["goles_acertados"] = bonus_goles

    # ── Predicción única ─────────────────────────────────────────────────
    if es_prediccion_unica and grupo.pts_prediccion_unica > 0:
        puntos += grupo.pts_prediccion_unica
        desglose["prediccion_unica"] = grupo.pts_prediccion_unica

    # ── Bonos por fase eliminatoria ──────────────────────────────────────
    bonos_por_fase = {
        FasePartido.dieciseisavos: grupo.bono_dieciseisavos,
        FasePartido.octavos:       grupo.bono_octavos,
        FasePartido.cuartos:       grupo.bono_cuartos,
        FasePartido.semifinal:     grupo.bono_semifinales,
        FasePartido.final:         grupo.bono_final,
    }

    bono_fase = bonos_por_fase.get(fase, 0)
    if bono_fase > 0 and clasificado_local is not None:
        pred_clasifica_local = pred_local >= pred_visitante
        if pred_clasifica_local == clasificado_local:
            puntos += bono_fase
            desglose[f"bono_{fase}"] = bono_fase

    return {"total": puntos, "desglose": desglose}


def verificar_prediccion_unica(
    db: Session,
    partido_id: uuid.UUID,
    grupo_id: uuid.UUID,
    goles_local: int,
    goles_visitante: int,
    excluir_user_id: uuid.UUID,
) -> bool:
    """Verifica si este marcador es único en el grupo (nadie más lo pronosticó)."""
    otros = db.query(Pronostico).filter(
        Pronostico.partido_id == partido_id,
        Pronostico.grupo_id   == grupo_id,
        Pronostico.user_id    != excluir_user_id,
        Pronostico.goles_local     == goles_local,
        Pronostico.goles_visitante == goles_visitante,
    ).count()
    return otros == 0


# ─── Endpoints ───────────────────────────────────────────────────────────

@router.post("/", response_model=PronosticoOut, status_code=201)
def registrar_pronostico(
    data: PronosticoIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registrar o actualizar el pronóstico de un partido en un grupo."""
    partido = db.query(Partido).filter(Partido.id == data.partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    if datetime.utcnow() >= partido.cierre_pronosticos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El tiempo para registrar pronósticos ha cerrado",
        )

    participante = db.query(GrupoParticipante).filter(
        GrupoParticipante.grupo_id == data.grupo_id,
        GrupoParticipante.user_id  == current_user.id,
    ).first()
    if not participante:
        raise HTTPException(status_code=403, detail="No eres parte de este grupo")

    existente = db.query(Pronostico).filter(
        Pronostico.user_id    == current_user.id,
        Pronostico.partido_id == data.partido_id,
        Pronostico.grupo_id   == data.grupo_id,
    ).first()

    if existente:
        existente.goles_local      = data.goles_local
        existente.goles_visitante  = data.goles_visitante
        existente.fuente           = FuentePronostico.manual
        existente.registrado_en    = datetime.utcnow()
        db.commit()
        db.refresh(existente)
        return existente

    pronostico = Pronostico(
        user_id=current_user.id,
        partido_id=data.partido_id,
        grupo_id=data.grupo_id,
        goles_local=data.goles_local,
        goles_visitante=data.goles_visitante,
        fuente=FuentePronostico.manual,
    )
    db.add(pronostico)
    db.commit()
    db.refresh(pronostico)
    return pronostico


@router.post("/calcular/{partido_id}")
def calcular_puntos_partido(
    partido_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Calcula y guarda los puntos de todos los pronósticos de un partido.
    Llamar cuando el partido termina y se registra el resultado oficial.
    """
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    if partido.goles_local is None or partido.goles_visitante is None:
        raise HTTPException(status_code=400, detail="El partido aún no tiene resultado")

    pronosticos = db.query(Pronostico).filter(
        Pronostico.partido_id == partido_id
    ).all()

    actualizados = 0
    for p in pronosticos:
        grupo = db.query(Grupo).filter(Grupo.id == p.grupo_id).first()

        # ¿Es predicción única en su grupo?
        es_unica = verificar_prediccion_unica(
            db, partido_id, p.grupo_id,
            p.goles_local, p.goles_visitante, p.user_id,
        ) and (p.goles_local == partido.goles_local and
               p.goles_visitante == partido.goles_visitante)

        resultado = calcular_puntos(
            pred_local=p.goles_local,
            pred_visitante=p.goles_visitante,
            real_local=partido.goles_local,
            real_visitante=partido.goles_visitante,
            fase=partido.fase,
            grupo=grupo,
            clasificado_local=partido.clasificado_local,
            es_prediccion_unica=es_unica,
        )

        p.puntos_obtenidos = resultado["total"]

        # Actualizar puntos acumulados en grupo_participantes
        participante = db.query(GrupoParticipante).filter(
            GrupoParticipante.grupo_id == p.grupo_id,
            GrupoParticipante.user_id  == p.user_id,
        ).first()
        if participante:
            participante.total_puntos += resultado["total"]

        actualizados += 1

    # Recalcular posiciones en cada grupo afectado
    grupos_afectados = {p.grupo_id for p in pronosticos}
    for gid in grupos_afectados:
        participantes = db.query(GrupoParticipante).filter(
            GrupoParticipante.grupo_id == gid
        ).order_by(GrupoParticipante.total_puntos.desc()).all()
        for i, part in enumerate(participantes, start=1):
            part.posicion = i

    db.commit()
    return {"partido_id": str(partido_id), "pronosticos_actualizados": actualizados}


@router.get("/mis-pronosticos/{grupo_id}")
def mis_pronosticos(
    grupo_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Listar todos los pronósticos del usuario en un grupo con su desglose."""
    pronosticos = db.query(Pronostico).filter(
        Pronostico.user_id  == current_user.id,
        Pronostico.grupo_id == grupo_id,
    ).all()
    return pronosticos
