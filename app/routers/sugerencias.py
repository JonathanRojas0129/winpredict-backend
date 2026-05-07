import uuid
import math
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_pro_user
from app.models.models import SugerenciaIA, Partido, User
from app.schemas.sugerencias import SugerenciaOut

router = APIRouter()

# ─── Motor Matemático de la IA ──────────────────────────────────────────

def calcular_poisson(lambda_goles: float, k: int) -> float:
    """Calcula la probabilidad de que ocurran k goles dado un promedio (lambda)."""
    return (math.exp(-lambda_goles) * (lambda_goles**k)) / math.factorial(k)

def generar_prediccion_inteligente(partido: Partido):
    """
    Simula el resultado basado en el 'Rating' de los equipos.
    Rating sugerido: Usar ranking FIFA o promedio de goles.
    """
    # Por ahora simulamos lambdas (promedio de goles esperado)
    # En una fase avanzada, estos valores vendrían de una tabla de 'EstadisticasEquipo'
    lambda_local = 1.6  # El local suele marcar más
    lambda_visitante = 1.2
    
    # Calculamos el marcador más probable (Moda de la distribución)
    goles_l = math.floor(lambda_local)
    goles_v = math.floor(lambda_visitante)
    
    # Calculamos confianza basada en la probabilidad del resultado exacto
    prob_exacta = calcular_poisson(lambda_local, goles_l) * calcular_poisson(lambda_visitante, goles_v)
    confianza = round(prob_exacta * 100, 2) + 40 # Offset base de inteligencia
    
    return goles_l, goles_v, min(confianza, 99.0)

# ─── Endpoints ───────────────────────────────────────────────────────────

@router.get("/{partido_id}", response_model=SugerenciaOut)
def obtener_sugerencia_ia(
    partido_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_pro_user) # 🔒 Solo PRO
):
    """
    Retorna la sugerencia inteligente para un partido.
    Si no existe, la genera en tiempo real y la guarda.
    """
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    sugerencia = db.query(SugerenciaIA).filter(SugerenciaIA.partido_id == partido_id).first()

    if not sugerencia:
        goles_l, goles_v, conf = generar_prediccion_inteligente(partido)
        sugerencia = SugerenciaIA(
            partido_id=partido_id,
            goles_local=goles_l,
            goles_visitante=goles_v,
            confianza=conf / 100 # Guardamos como decimal 0.0 - 1.0
        )
        db.add(sugerencia)
        db.commit()
        db.refresh(sugerencia)

    # Preparar respuesta con el formato del Schema
    return {
        "partido_id": sugerencia.partido_id,
        "goles_local": sugerencia.goles_local,
        "goles_visitante": sugerencia.goles_visitante,
        "confianza": sugerencia.confianza * 100,
        "probabilidades": {
            "Local": 45.0, # Valores ejemplo, se pueden calcular con Poisson
            "Empate": 25.0,
            "Visitante": 30.0
        },
        "generado_en": sugerencia.generado_en
    }