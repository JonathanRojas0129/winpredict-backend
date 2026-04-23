# app/routers/sugerencias.py
# Sugerencias de IA por partido — solo visibles para usuarios PRO
# crafted by JR ♥

import uuid
import random
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, get_current_pro_user
from app.models.models import (
    SugerenciaIA, Partido, EstadoPartido, User
)

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────

class SugerenciaOut(BaseModel):
    id:              uuid.UUID
    partido_id:      uuid.UUID
    goles_local:     int
    goles_visitante: int
    confianza:       float
    generado_en:     datetime

    class Config:
        from_attributes = True


class EfectividadOut(BaseModel):
    total_sugerencias:   int
    partidos_evaluados:  int
    aciertos_exactos:    int
    aciertos_ganador:    int
    pct_exacto:          float   # % marcador exacto
    pct_ganador:         float   # % ganador/empate acertado


# ─── Lógica de generación ─────────────────────────────────────────────────

# Marcadores típicos por fase — base para la sugerencia
MARCADORES_POR_FASE = {
    "grupos":        [(1, 0), (1, 1), (2, 1), (2, 0), (0, 0), (3, 1)],
    "dieciseisavos": [(1, 0), (2, 1), (1, 1), (2, 0)],
    "octavos":       [(1, 0), (2, 1), (1, 1), (2, 0)],
    "cuartos":       [(1, 0), (2, 1), (1, 0), (1, 1)],
    "semifinal":     [(1, 0), (2, 1), (1, 0)],
    "tercer_puesto": [(2, 1), (3, 2), (1, 0)],
    "final":         [(1, 0), (1, 1), (2, 1)],
}

def generar_sugerencia_para(partido: Partido) -> tuple[int, int, float]:
    """
    Genera un marcador sugerido y nivel de confianza para un partido.
    Lógica base: pool de marcadores por fase + confianza aleatoria.
    Reemplaza esta función con tu modelo real cuando esté listo.
    """
    pool = MARCADORES_POR_FASE.get(partido.fase.value, [(1, 0)])
    local, visitante = random.choice(pool)
    confianza = round(random.uniform(0.55, 0.85), 2)
    return local, visitante, confianza


# ─── Endpoints ───────────────────────────────────────────────────────────

@router.post(
    "/generar/{partido_id}",
    response_model=SugerenciaOut,
    status_code=201,
    summary="Generar o regenerar sugerencia IA para un partido",
)
def generar_sugerencia(
    partido_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),   # cualquier usuario autenticado puede dispararlo (admin)
):
    """
    Genera y guarda la sugerencia IA para un partido.
    Si ya existe, la sobreescribe (permite regenerar).
    Llamar antes del cierre de pronósticos.
    """
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    if partido.estado == EstadoPartido.finalizado:
        raise HTTPException(
            status_code=400,
            detail="El partido ya finalizó, no se puede generar sugerencia",
        )

    local, visitante, confianza = generar_sugerencia_para(partido)

    # Si ya existe → actualizar
    existente = db.query(SugerenciaIA).filter(
        SugerenciaIA.partido_id == partido_id
    ).first()

    if existente:
        existente.goles_local      = local
        existente.goles_visitante  = visitante
        existente.confianza        = confianza
        existente.generado_en      = datetime.utcnow()
        db.commit()
        db.refresh(existente)
        return existente

    sugerencia = SugerenciaIA(
        partido_id=partido_id,
        goles_local=local,
        goles_visitante=visitante,
        confianza=confianza,
    )
    db.add(sugerencia)
    db.commit()
    db.refresh(sugerencia)
    return sugerencia


@router.post(
    "/generar-todas",
    summary="Generar sugerencias IA para todos los partidos pendientes",
)
def generar_todas(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Genera sugerencias para todos los partidos que aún no tienen una.
    Útil para poblar la tabla de una sola vez.
    """
    partidos_sin_sugerencia = (
        db.query(Partido)
        .outerjoin(SugerenciaIA, Partido.id == SugerenciaIA.partido_id)
        .filter(
            SugerenciaIA.id == None,
            Partido.estado != EstadoPartido.finalizado,
        )
        .all()
    )

    generadas = 0
    for partido in partidos_sin_sugerencia:
        local, visitante, confianza = generar_sugerencia_para(partido)
        sugerencia = SugerenciaIA(
            partido_id=partido.id,
            goles_local=local,
            goles_visitante=visitante,
            confianza=confianza,
        )
        db.add(sugerencia)
        generadas += 1

    db.commit()
    return {
        "mensaje": f"{generadas} sugerencias generadas exitosamente",
        "total":   generadas,
    }


@router.get(
    "/{partido_id}",
    response_model=SugerenciaOut,
    summary="Ver sugerencia IA de un partido (solo PRO)",
)
def ver_sugerencia(
    partido_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_pro_user),   # 🔒 solo PRO
):
    """
    Retorna la sugerencia IA para un partido.
    Solo accesible para usuarios con WinPredict PRO.
    """
    sugerencia = db.query(SugerenciaIA).filter(
        SugerenciaIA.partido_id == partido_id
    ).first()

    if not sugerencia:
        raise HTTPException(
            status_code=404,
            detail="Aún no hay sugerencia generada para este partido",
        )

    return sugerencia


@router.get(
    "/",
    response_model=list[SugerenciaOut],
    summary="Listar todas las sugerencias IA (solo PRO)",
)
def listar_sugerencias(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_pro_user),   # 🔒 solo PRO
):
    """
    Retorna todas las sugerencias IA generadas.
    Útil para la tabla de seguimiento de efectividad.
    """
    return db.query(SugerenciaIA).order_by(SugerenciaIA.generado_en.desc()).all()


@router.get(
    "/efectividad/resumen",
    response_model=EfectividadOut,
    summary="Estadísticas de efectividad de la IA",
)
def efectividad(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Compara las sugerencias guardadas contra los resultados reales
    de los partidos ya finalizados.
    Calcula % de acierto exacto y % de acierto de ganador/empate.
    """
    # Solo partidos finalizados con sugerencia
    sugerencias = (
        db.query(SugerenciaIA)
        .join(Partido, SugerenciaIA.partido_id == Partido.id)
        .filter(Partido.estado == EstadoPartido.finalizado)
        .all()
    )

    total             = db.query(SugerenciaIA).count()
    evaluados         = len(sugerencias)
    aciertos_exactos  = 0
    aciertos_ganador  = 0

    for s in sugerencias:
        partido = db.query(Partido).filter(Partido.id == s.partido_id).first()
        if partido.goles_local is None or partido.goles_visitante is None:
            continue

        # Marcador exacto
        if s.goles_local == partido.goles_local and s.goles_visitante == partido.goles_visitante:
            aciertos_exactos += 1

        # Ganador o empate acertado
        def resultado(l, v):
            if l > v: return "local"
            if l < v: return "visitante"
            return "empate"

        if resultado(s.goles_local, s.goles_visitante) == resultado(partido.goles_local, partido.goles_visitante):
            aciertos_ganador += 1

    pct_exacto  = round((aciertos_exactos / evaluados * 100), 1) if evaluados else 0.0
    pct_ganador = round((aciertos_ganador  / evaluados * 100), 1) if evaluados else 0.0

    return EfectividadOut(
        total_sugerencias  = total,
        partidos_evaluados = evaluados,
        aciertos_exactos   = aciertos_exactos,
        aciertos_ganador   = aciertos_ganador,
        pct_exacto         = pct_exacto,
        pct_ganador        = pct_ganador,
    )