import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_internal_api_key, tiene_pro_vigente
from app.models.models import (
    Pronostico, Partido, Grupo, GrupoParticipante,
    User, FuentePronostico,
)
from app.schemas.pronosticos import PronosticoIn, PronosticoOut

router = APIRouter()

# ─── Lógica de puntuación dinámica ───────────────────────────────────────

def calcular_puntos(
    pred_local: int,
    pred_visitante: int,
    real_local: int,
    real_visitante: int,
    fase: str,
    grupo: Grupo,
    es_prediccion_unica: bool = False,
    clasificado_local_pred: Optional[bool] = None,   # ← nuevo
    clasificado_local_real: Optional[bool] = None,   # ← nuevo
) -> dict:
    puntos = 0
    desglose = {}
        
    # Marcador exacto
    if pred_local == real_local and pred_visitante == real_visitante:
        puntos += grupo.pts_marcador_exacto
        desglose["marcador_exacto"] = grupo.pts_marcador_exacto
        # Marcador exacto también implica ganador acertado
        if real_local != real_visitante and grupo.pts_ganador > 0:
            puntos += grupo.pts_ganador
            desglose["ganador_acertado"] = grupo.pts_ganador
        elif real_local == real_visitante and grupo.pts_empate > 0:
            puntos += grupo.pts_empate
            desglose["empate_acertado"] = grupo.pts_empate
        # Goles también suman cuando el marcador es exacto
        if grupo.pts_gol > 0:
            bonus_goles = 0
            if pred_local == real_local:         bonus_goles += grupo.pts_gol
            if pred_visitante == real_visitante: bonus_goles += grupo.pts_gol
            if bonus_goles > 0:
                puntos += bonus_goles
                desglose["goles_acertados"] = bonus_goles

    else:
        # Ganador / Empate
        local_gana_pred  = pred_local > pred_visitante
        local_gana_real  = real_local > real_visitante
        visita_gana_pred = pred_local < pred_visitante
        visita_gana_real = real_local < real_visitante

        if (local_gana_pred and local_gana_real) or (visita_gana_pred and visita_gana_real):
            puntos += grupo.pts_ganador
            desglose["ganador_acertado"] = grupo.pts_ganador
        elif pred_local == pred_visitante and real_local == real_visitante:
            puntos += grupo.pts_empate
            desglose["empate_acertado"] = grupo.pts_empate

        # Goles acertados individualmente
        if grupo.pts_gol > 0:
            bonus_goles = 0
            if pred_local     == real_local:     bonus_goles += grupo.pts_gol
            if pred_visitante == real_visitante: bonus_goles += grupo.pts_gol
            if bonus_goles > 0:
                puntos += bonus_goles
                desglose["goles_acertados"] = bonus_goles

    # Predicción única
    if es_prediccion_unica and grupo.pts_prediccion_unica > 0:
        puntos += grupo.pts_prediccion_unica
        desglose["prediccion_unica"] = grupo.pts_prediccion_unica

    # Bonos por fase eliminatoria
    # En empate, el bono solo aplica si acertó el clasificado
    bonos_por_fase = {
        "dieciseisavos": grupo.bono_dieciseisavos,
        "octavos":       grupo.bono_octavos,
        "cuartos":       grupo.bono_cuartos,
        "semifinales":   grupo.bono_semifinales,
        "final":         grupo.bono_final,
    }

    bono_fase = bonos_por_fase.get(fase, 0)

    if bono_fase > 0 and puntos > 0:
        # Si fue empate, solo dar bono si acertó el clasificado
        es_empate_real = real_local == real_visitante
        if es_empate_real:
            if clasificado_local_pred is not None and clasificado_local_real is not None:
                if clasificado_local_pred == clasificado_local_real:
                    puntos += bono_fase
                    desglose[f"bono_{fase}"] = bono_fase
        else:
            # No fue empate — bono aplica normalmente
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
    otros = db.query(Pronostico).filter(
        Pronostico.partido_id    == partido_id,
        Pronostico.grupo_id      == grupo_id,
        Pronostico.user_id       != excluir_user_id,
        Pronostico.goles_local   == goles_local,
        Pronostico.goles_visitante == goles_visitante,
    ).count()
    return otros == 0


def aplicar_puntos_a_partido(db: Session, partido: Partido) -> int:
    """
    Calcula puntos de todos los pronósticos de un partido con resultado.
    Idempotente: si se vuelve a ejecutar, resta el puntaje anterior antes de sumar el nuevo.
    """
    if partido.goles_local is None or partido.goles_visitante is None:
        raise HTTPException(status_code=400, detail="Partido sin resultado oficial aún")

    pronosticos = db.query(Pronostico).filter(
        Pronostico.partido_id == partido.id
    ).all()

    procesados = 0
    for p in pronosticos:
        grupo = db.query(Grupo).filter(Grupo.id == p.grupo_id).first()
        if not grupo:
            continue

        puntos_anteriores = p.puntos_obtenidos or 0

        es_unica = (
            p.goles_local == partido.goles_local
            and p.goles_visitante == partido.goles_visitante
            and verificar_prediccion_unica(
                db, partido.id, p.grupo_id,
                p.goles_local, p.goles_visitante, p.user_id,
            )
        )

        res = calcular_puntos(
            p.goles_local, p.goles_visitante,
            partido.goles_local, partido.goles_visitante,
            partido.fase, grupo, es_unica,
            clasificado_local_pred=p.clasificado_local,
            clasificado_local_real=partido.clasificado_local,
        )
        puntos_nuevos = res["total"]
        p.puntos_obtenidos = puntos_nuevos

        participante = db.query(GrupoParticipante).filter(
            GrupoParticipante.grupo_id == p.grupo_id,
            GrupoParticipante.user_id == p.user_id,
        ).first()
        if participante:
            total = participante.total_puntos or 0
            participante.total_puntos = total - puntos_anteriores + puntos_nuevos

        procesados += 1

    grupos_afectados = {p.grupo_id for p in pronosticos}
    for gid in grupos_afectados:
        participantes_grupo = db.query(GrupoParticipante).filter(
            GrupoParticipante.grupo_id == gid
        ).order_by(GrupoParticipante.total_puntos.desc()).all()

        for i, part in enumerate(participantes_grupo, start=1):
            part.posicion = i

    db.commit()
    return procesados


# ─── POST / — Registrar o actualizar pronóstico ───────────────────────────

@router.post("/", response_model=PronosticoOut, status_code=201)
def registrar_pronostico(
    data: PronosticoIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Obtener el partido ────────────────────────────────────────
    partido = db.query(Partido).filter(Partido.id == data.partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    # ── 2. Verificar cierre de pronósticos ──────────────────────────
    ahora_utc = datetime.now(timezone.utc)

    # Asegurar que fecha_hora tenga timezone (puede venir naive de la BD)
    fecha_partido = partido.fecha_hora
    if fecha_partido.tzinfo is None:
        fecha_partido = fecha_partido.replace(tzinfo=timezone.utc)

    limite_free = fecha_partido - timedelta(minutes=15)
    limite_pro  = fecha_partido - timedelta(minutes=5)

    if not tiene_pro_vigente(current_user) and ahora_utc >= limite_free:
        raise HTTPException(
            status_code=403,
            detail="Debes registrar tu pronóstico al menos 15 minutos antes del partido.",
        )
    if tiene_pro_vigente(current_user) and ahora_utc >= limite_pro:
        raise HTTPException(
            status_code=403,
            detail="El tiempo límite PRO (5 minutos antes) ha expirado.",
        )

    # ── 3. Verificar participación en el grupo ───────────────────────
    participante = db.query(GrupoParticipante).filter(
        GrupoParticipante.grupo_id == data.grupo_id,
        GrupoParticipante.user_id  == current_user.id,
    ).first()
    if not participante:
        raise HTTPException(status_code=403, detail="No eres parte de este grupo")

    # ── 4. Actualizar si ya existe ───────────────────────────────────
    existente = db.query(Pronostico).filter(
        Pronostico.user_id    == current_user.id,
        Pronostico.partido_id == data.partido_id,
        Pronostico.grupo_id   == data.grupo_id,
    ).first()

    if existente:
        if tiene_pro_vigente(current_user):
            existente.goles_local     = data.goles_local
            existente.goles_visitante = data.goles_visitante
            existente.registrado_en   = ahora_utc
            db.commit()
            db.refresh(existente)
            return existente
        else:
            raise HTTPException(
                status_code=403,
                detail="Ya registraste un pronóstico. Solo los usuarios PRO pueden editarlo.",
            )

    # ── 5. Crear nuevo pronóstico ────────────────────────────────────
    nuevo = Pronostico(
        user_id=          current_user.id,
        partido_id=       data.partido_id,
        grupo_id=         data.grupo_id,
        goles_local=      data.goles_local,
        goles_visitante=  data.goles_visitante,
        clasificado_local= data.clasificado_local,
        fuente=           FuentePronostico.manual,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


# ─── GET /mis-pronosticos/{grupo_id} ─────────────────────────────────────

@router.get("/mis-pronosticos/{grupo_id}")
def mis_pronosticos(
    grupo_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pronosticos = db.query(Pronostico).filter(
        Pronostico.user_id  == current_user.id,
        Pronostico.grupo_id == grupo_id,
    ).all()
    return pronosticos


# ─── GET /mis-pronosticos-global ─────────────────────────────────────────

@router.get("/mis-pronosticos-global")
def mis_pronosticos_global(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pronosticos = db.query(Pronostico).filter(
        Pronostico.user_id == current_user.id,
    ).all()

    total     = len(pronosticos)
    exactos   = sum(
        1 for p in pronosticos
        if p.puntos_obtenidos is not None and p.puntos_obtenidos >= 5
    )
    correctos = sum(
        1 for p in pronosticos
        if p.puntos_obtenidos is not None and p.puntos_obtenidos > 0
    )

    return {"total": total, "exactos": exactos, "correctos": correctos}


# ─── POST /calcular-puntos/{partido_id} ──────────────────────────────────
# Llamado por score_updater.py tras actualizar el resultado en Supabase

@router.post("/calcular-puntos/{partido_id}")
def calcular_puntos_partido(
    partido_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_api_key),
):
    """
    Calcula y asigna puntos a todos los pronósticos de un partido finalizado.
    Uso interno: requiere header ``X-Internal-Key`` igual a ``INTERNAL_API_KEY``
    (obligatorio si ``DEBUG`` es False). ``score_updater`` ya puede enviarlo.
    """
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    procesados = aplicar_puntos_a_partido(db, partido)
    return {"status": "success", "procesados": procesados}
