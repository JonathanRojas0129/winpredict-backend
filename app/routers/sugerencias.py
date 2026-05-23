"""
routers/sugerencias.py
Motor de predicción estadística basado en:
  - Rankings FIFA abril 2026 (reales)
  - Promedios de goles en eliminatorias por equipo (reales por confederación)
  - Proyecciones RotoWire grupo stage
  - Distribución de Poisson para probabilidades de marcadores
Retorna top 3 resultados más probables con sus porcentajes.
"""
import uuid
import math
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Float, Integer, text
from app.core.database import get_db
from app.core.security import get_current_pro_user
from app.models.models import SugerenciaIA, Partido, User
from app.core.security import get_current_pro_user, require_internal_api_key

router = APIRouter()

# ─── Datos estadísticos reales por equipo ────────────────────────────────
# Fuente: FIFA Rankings abril 2026 + estadísticas eliminatorias + RotoWire
# goles_favor: promedio goles anotados por partido en eliminatorias
# goles_contra: promedio goles recibidos por partido en eliminatorias
# proj_grupo: proyección total goles en 3 partidos fase grupos (RotoWire)

STATS_EQUIPOS: dict[str, dict] = {
    # GRUPO A
    "México":           {"ranking": 15, "goles_favor": 1.75, "goles_contra": 0.90, "proj": 5.2},
    "Corea del Sur":    {"ranking": 22, "goles_favor": 1.60, "goles_contra": 0.95, "proj": 3.6},
    "República Checa":  {"ranking": 37, "goles_favor": 1.50, "goles_contra": 1.00, "proj": 4.2},
    "Sudáfrica":        {"ranking": 68, "goles_favor": 1.10, "goles_contra": 1.30, "proj": 1.8},
    # GRUPO B
    "Canadá":           {"ranking": 30, "goles_favor": 1.80, "goles_contra": 1.10, "proj": 4.0},
    "Catar":            {"ranking": 57, "goles_favor": 1.30, "goles_contra": 1.40, "proj": 2.0},
    "Suiza":            {"ranking": 19, "goles_favor": 1.70, "goles_contra": 0.85, "proj": 5.2},
    "Bosnia y H.":      {"ranking": 60, "goles_favor": 1.40, "goles_contra": 1.30, "proj": 3.2},
    # GRUPO C
    "Brasil":           {"ranking":  6, "goles_favor": 1.95, "goles_contra": 0.80, "proj": 7.4},
    "Marruecos":        {"ranking":  8, "goles_favor": 1.65, "goles_contra": 0.70, "proj": 5.0},
    "Escocia":          {"ranking": 39, "goles_favor": 1.55, "goles_contra": 1.15, "proj": 3.2},
    "Haití":            {"ranking":100, "goles_favor": 0.90, "goles_contra": 1.90, "proj": 1.0},
    # GRUPO D
    "Estados Unidos":   {"ranking": 16, "goles_favor": 1.70, "goles_contra": 1.00, "proj": 4.5},
    "Paraguay":         {"ranking": 55, "goles_favor": 0.78, "goles_contra": 0.56, "proj": 2.8},
    "Australia":        {"ranking": 23, "goles_favor": 1.50, "goles_contra": 1.10, "proj": 3.0},
    "Turquía":          {"ranking": 28, "goles_favor": 1.60, "goles_contra": 1.05, "proj": 4.2},
    # GRUPO E
    "Alemania":         {"ranking": 10, "goles_favor": 2.10, "goles_contra": 0.90, "proj": 7.9},
    "Costa de Marfil":  {"ranking": 45, "goles_favor": 1.50, "goles_contra": 1.00, "proj": 3.5},
    "Ecuador":          {"ranking": 42, "goles_favor": 0.78, "goles_contra": 0.28, "proj": 3.3},
    "Curazao":          {"ranking":115, "goles_favor": 0.80, "goles_contra": 2.50, "proj": 1.0},
    # GRUPO F
    "Países Bajos":     {"ranking":  7, "goles_favor": 1.95, "goles_contra": 0.60, "proj": 5.3},
    "Japón":            {"ranking": 18, "goles_favor": 1.75, "goles_contra": 0.80, "proj": 3.9},
    "Suecia":           {"ranking": 25, "goles_favor": 1.60, "goles_contra": 0.95, "proj": 3.5},
    "Túnez":            {"ranking": 32, "goles_favor": 1.20, "goles_contra": 1.10, "proj": 2.5},
    # GRUPO G
    "Bélgica":          {"ranking":  9, "goles_favor": 1.85, "goles_contra": 0.85, "proj": 6.3},
    "Irán":             {"ranking": 21, "goles_favor": 1.40, "goles_contra": 0.90, "proj": 3.3},
    "Nueva Zelanda":    {"ranking": 85, "goles_favor": 1.20, "goles_contra": 1.30, "proj": 2.0},
    "Egipto":           {"ranking": 35, "goles_favor": 1.30, "goles_contra": 1.05, "proj": 3.2},
    # GRUPO H
    "España":           {"ranking":  2, "goles_favor": 2.20, "goles_contra": 0.65, "proj": 7.6},
    "Arabia Saudí":     {"ranking": 56, "goles_favor": 1.20, "goles_contra": 1.20, "proj": 2.5},
    "Uruguay":          {"ranking": 17, "goles_favor": 1.45, "goles_contra": 0.67, "proj": 4.5},
    "Cabo Verde":       {"ranking": 72, "goles_favor": 1.10, "goles_contra": 1.30, "proj": 1.8},
    # GRUPO I
    "Francia":          {"ranking":  1, "goles_favor": 2.15, "goles_contra": 0.70, "proj": 7.8},
    "Senegal":          {"ranking": 14, "goles_favor": 1.75, "goles_contra": 0.85, "proj": 5.0},
    "Irak":             {"ranking": 62, "goles_favor": 1.10, "goles_contra": 1.30, "proj": 2.0},
    "Noruega":          {"ranking": 26, "goles_favor": 4.63, "goles_contra": 0.63, "proj": 5.5},
    # GRUPO J
    "Argentina":        {"ranking":  3, "goles_favor": 1.72, "goles_contra": 0.61, "proj": 6.5},
    "Argelia":          {"ranking": 34, "goles_favor": 1.55, "goles_contra": 0.90, "proj": 3.5},
    "Austria":          {"ranking": 27, "goles_favor": 1.65, "goles_contra": 0.95, "proj": 4.0},
    "Jordania":         {"ranking": 79, "goles_favor": 1.10, "goles_contra": 1.60, "proj": 1.8},
    # GRUPO K
    "Portugal":         {"ranking":  5, "goles_favor": 1.90, "goles_contra": 0.75, "proj": 6.2},
    "RD del Congo":     {"ranking": 50, "goles_favor": 1.30, "goles_contra": 1.50, "proj": 2.5},
    "Colombia":         {"ranking": 13, "goles_favor": 1.76, "goles_contra": 0.80, "proj": 5.0},
    "Uzbekistán":       {"ranking": 71, "goles_favor": 1.20, "goles_contra": 1.45, "proj": 2.2},
    # GRUPO L
    "Inglaterra":       {"ranking":  4, "goles_favor": 2.25, "goles_contra": 0.00, "proj": 6.1},
    "Croacia":          {"ranking": 11, "goles_favor": 2.17, "goles_contra": 0.33, "proj": 4.6},
    "Ghana":            {"ranking": 58, "goles_favor": 1.40, "goles_contra": 1.20, "proj": 2.8},
    "Panamá":           {"ranking": 90, "goles_favor": 0.90, "goles_contra": 1.90, "proj": 1.5},
}

# Factor de ventaja local en la fase de grupos del Mundial
FACTOR_LOCAL = 1.08

# Bonus por fase eliminatoria — equipos suelen ser más cautelosos
FACTOR_FASE = {
    "grupos":        1.00,
    "dieciseisavos": 0.92,
    "octavos":       0.88,
    "cuartos":       0.85,
    "semifinales":   0.82,
    "final":         0.80,
}


def poisson(lam: float, k: int) -> float:
    """Probabilidad de Poisson P(X=k) dado lambda."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)


def calcular_lambdas(equipo_local: str, equipo_visitante: str, fase: str) -> tuple[float, float]:
    stats_l = STATS_EQUIPOS.get(equipo_local)
    stats_v = STATS_EQUIPOS.get(equipo_visitante)

    if not stats_l or not stats_v:
        factor = FACTOR_FASE.get(fase, 0.90)
        return round(1.3 * factor, 3), round(1.0 * factor, 3)

    factor = FACTOR_FASE.get(fase, 0.90)
    promedio_global = 1.7  # ← subir de 1.5

    # ── Factor de ranking ──────────────────────────────────────────
    diff = stats_v["ranking"] - stats_l["ranking"]  # positivo = local mejor rankeado
    factor_ranking_l = max(0.75, min(1.50, 1.0 + (diff * 0.008)))
    factor_ranking_v = max(0.75, min(1.50, 1.0 - (diff * 0.008)))
    # ───────────────────────────────────────────────────────────────

    lambda_local = (stats_l["goles_favor"] / promedio_global) * \
                (stats_v["goles_contra"] / promedio_global) * \
                promedio_global * FACTOR_LOCAL * factor * 1.3 * factor_ranking_l  # ← × factor_ranking

    lambda_visit = (stats_v["goles_favor"] / promedio_global) * \
                (stats_l["goles_contra"] / promedio_global) * \
                promedio_global * factor * 1.3 * factor_ranking_v  # ← × factor_ranking

    return max(0.5, min(4.5, lambda_local)), max(0.3, min(3.8, lambda_visit))  # ← clamp más alto

def top3_resultados(lambda_l: float, lambda_v: float, max_goles: int = 6) -> list[dict]:
    # ─── Top 3 resultados ────────────────────────────────────────────
    """
    Retorna el marcador más probable de cada categoría:
    1. Victoria local más probable
    2. Empate más probable  
    3. Victoria visitante más probable
    """
    victorias_l = []
    empates     = []
    victorias_v = []

    for g_l in range(max_goles + 1):
        for g_v in range(max_goles + 1):
            prob = poisson(lambda_l, g_l) * poisson(lambda_v, g_v)
            entry = {"goles_local": g_l, "goles_visitante": g_v, "probabilidad": round(prob * 100, 2)}
            if g_l > g_v:
                victorias_l.append(entry)
            elif g_l == g_v:
                empates.append(entry)
            else:
                victorias_v.append(entry)

    mejor_l = max(victorias_l, key=lambda x: x["probabilidad"])
    mejor_e = max(empates,     key=lambda x: x["probabilidad"])
    mejor_v = max(victorias_v, key=lambda x: x["probabilidad"])

    # Ordenar por probabilidad — el más probable va primero
    return sorted([mejor_l, mejor_e, mejor_v], key=lambda x: x["probabilidad"], reverse=True)


def calcular_1x2(lambda_l: float, lambda_v: float, max_goles: int = 10) -> dict:
    """
    Calcula probabilidades de: Local gana, Empate, Visitante gana.
    """
    p_local = p_empate = p_visita = 0.0
    for g_l in range(max_goles + 1):
        for g_v in range(max_goles + 1):
            prob = poisson(lambda_l, g_l) * poisson(lambda_v, g_v)
            if g_l > g_v:
                p_local += prob
            elif g_l == g_v:
                p_empate += prob
            else:
                p_visita += prob

    total = p_local + p_empate + p_visita
    return {
        "local":    round((p_local  / total) * 100, 1),
        "empate":   round((p_empate / total) * 100, 1),
        "visitante": round((p_visita / total) * 100, 1),
    }

# ─── Endpoint todas las sugerencias─────────────────────────────────────────────────────────────
@router.get("/")
def obtener_todas_las_sugerencias(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_pro_user),
):
    sugerencias = db.query(SugerenciaIA).join(Partido).all()
    resultado = []
    for s in sugerencias:
        lambda_l, lambda_v = calcular_lambdas(
            s.partido.equipo_local,
            s.partido.equipo_visitante,
            s.partido.fase,
        )
        top3     = top3_resultados(lambda_l, lambda_v)
        prob_1x2 = calcular_1x2(lambda_l, lambda_v)
        resultado.append({
            "partido_id":      str(s.partido_id),
            "goles_local":     s.goles_local,
            "goles_visitante": s.goles_visitante,
            "confianza":       s.confianza,
            "top3":            top3,
            "probabilidades":  {
                "Local":     prob_1x2["local"],
                "Empate":    prob_1x2["empate"],
                "Visitante": prob_1x2["visitante"],
            },
        })
    return resultado


# ─── Endpoint ─────────────────────────────────────────────────────────────

@router.get("/{partido_id}")
def obtener_sugerencia_ia(
    partido_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_pro_user),  # 🔒 Solo PRO
):
    """
    Retorna predicción estadística para un partido:
    - Top 3 marcadores más probables con % real (Poisson)
    - Probabilidades 1X2 (local/empate/visitante)
    - Basado en ranking FIFA abril 2026 + promedios eliminatorias reales
    """
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    # Calcular lambdas con datos reales
    lambda_l, lambda_v = calcular_lambdas(
        partido.equipo_local,
        partido.equipo_visitante,
        partido.fase,
    )

    # Top 3 resultados más probables
    top3 = top3_resultados(lambda_l, lambda_v)

    # Probabilidades 1X2
    prob_1x2 = calcular_1x2(lambda_l, lambda_v)

    # El resultado #1 es la sugerencia principal
    principal = top3[0]

    # Guardar/actualizar en BD para referencia
    sugerencia = db.query(SugerenciaIA).filter(SugerenciaIA.partido_id == partido_id).first()
    if not sugerencia:
        sugerencia = SugerenciaIA(
            partido_id=     partido_id,
            goles_local=    principal["goles_local"],
            goles_visitante=principal["goles_visitante"],
            confianza=      principal["probabilidad"] / 100,
        )
        db.add(sugerencia)
        db.commit()
        db.refresh(sugerencia)

    return {
        "partido_id":       str(partido_id),
        "equipo_local":     partido.equipo_local,
        "equipo_visitante": partido.equipo_visitante,
        # Sugerencia principal (resultado más probable)
        "goles_local":      principal["goles_local"],
        "goles_visitante":  principal["goles_visitante"],
        "confianza":        principal["probabilidad"],
        # Top 3 marcadores más probables
        "top3": top3,
        # Probabilidades 1X2
        "probabilidades": {
            "Local":     prob_1x2["local"],
            "Empate":    prob_1x2["empate"],
            "Visitante": prob_1x2["visitante"],
        },
        # Lambdas para transparencia
        "goles_esperados": {
            "local":     round(lambda_l, 2),
            "visitante": round(lambda_v, 2),
        },
    }


# ─── POST /precalcular — Genera sugerencias para todos los partidos de grupos ──

@router.post("/precalcular")
def precalcular_sugerencias(
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_api_key),
):
    """
    Precalcula y guarda sugerencias para todos los partidos
    de fase de grupos que aún no tienen sugerencia guardada.
    """
    from app.core.security import require_internal_api_key

    partidos = db.query(Partido).filter(
        Partido.fase == 'grupos'
    ).all()

    generados = 0
    actualizados = 0

    for partido in partidos:
        lambda_l, lambda_v = calcular_lambdas(
            partido.equipo_local,
            partido.equipo_visitante,
            partido.fase,
        )
        top3    = top3_resultados(lambda_l, lambda_v)
        principal = top3[0]

        sugerencia = db.query(SugerenciaIA).filter(
            SugerenciaIA.partido_id == partido.id
        ).first()

        if not sugerencia:
            sugerencia = SugerenciaIA(
                partido_id=      partido.id,
                goles_local=     principal["goles_local"],
                goles_visitante= principal["goles_visitante"],
                confianza=       principal["probabilidad"] / 100,
            )
            db.add(sugerencia)
            generados += 1
        else:
            sugerencia.goles_local     = principal["goles_local"]
            sugerencia.goles_visitante = principal["goles_visitante"]
            sugerencia.confianza       = principal["probabilidad"] / 100
            actualizados += 1

    db.commit()
    return {
        "status":      "ok",
        "generados":   generados,
        "actualizados": actualizados,
        "total":       generados + actualizados,
    }