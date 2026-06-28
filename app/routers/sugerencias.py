"""
routers/sugerencias.py
Motor de predicción estadística basado en:
  - Rankings FIFA abril 2026 (reales)
  - Promedios de goles en eliminatorias por equipo (reales por confederación)
  - Proyecciones RotoWire grupo stage
  - Distribución de Poisson para probabilidades de marcadores
  - Rendimiento real del equipo en el torneo (después de 1er partido)
  - Historial exitoso del usuario PRO (después de 3+ pronósticos acertados)
"""
import uuid
import math
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_pro_user, require_internal_api_key
from app.models.models import SugerenciaIA, Partido, Pronostico, User, EstadoPartido

router = APIRouter()

# ─── Datos estadísticos reales por equipo ────────────────────────────────
STATS_EQUIPOS: dict[str, dict] = {
    "México":           {"ranking": 15, "goles_favor": 1.75, "goles_contra": 0.90, "proj": 5.2},
    "Corea del Sur":    {"ranking": 22, "goles_favor": 1.60, "goles_contra": 0.95, "proj": 3.6},
    "República Checa":  {"ranking": 37, "goles_favor": 1.50, "goles_contra": 1.00, "proj": 4.2},
    "Sudáfrica":        {"ranking": 68, "goles_favor": 1.10, "goles_contra": 1.30, "proj": 1.8},
    "Canadá":           {"ranking": 30, "goles_favor": 2.80, "goles_contra": 1.10, "proj": 4.0},
    "Catar":            {"ranking": 57, "goles_favor": 1.30, "goles_contra": 2.40, "proj": 2.0},
    "Suiza":            {"ranking": 19, "goles_favor": 1.70, "goles_contra": 0.85, "proj": 5.2},
    "Bosnia y H.":      {"ranking": 60, "goles_favor": 1.40, "goles_contra": 1.30, "proj": 3.2},
    "Brasil":           {"ranking":  6, "goles_favor": 2.95, "goles_contra": 0.80, "proj": 7.4},
    "Marruecos":        {"ranking":  8, "goles_favor": 2.95, "goles_contra": 0.70, "proj": 5.0},
    "Escocia":          {"ranking": 39, "goles_favor": 1.55, "goles_contra": 1.15, "proj": 3.2},
    "Haití":            {"ranking":100, "goles_favor": 0.90, "goles_contra": 1.90, "proj": 1.0},
    "Estados Unidos":   {"ranking": 16, "goles_favor": 1.70, "goles_contra": 1.00, "proj": 4.5},
    "Paraguay":         {"ranking": 55, "goles_favor": 0.78, "goles_contra": 0.56, "proj": 2.8},
    "Australia":        {"ranking": 23, "goles_favor": 1.50, "goles_contra": 1.10, "proj": 3.0},
    "Turquía":          {"ranking": 28, "goles_favor": 1.60, "goles_contra": 1.05, "proj": 4.2},
    "Alemania":         {"ranking": 10, "goles_favor": 2.90, "goles_contra": 0.90, "proj": 7.9},
    "Costa de Marfil":  {"ranking": 45, "goles_favor": 1.50, "goles_contra": 1.00, "proj": 3.5},
    "Ecuador":          {"ranking": 42, "goles_favor": 0.78, "goles_contra": 0.28, "proj": 3.3},
    "Curazao":          {"ranking":115, "goles_favor": 0.80, "goles_contra": 3.50, "proj": 1.0},
    "Países Bajos":     {"ranking":  7, "goles_favor": 1.95, "goles_contra": 0.60, "proj": 5.3},
    "Japón":            {"ranking": 18, "goles_favor": 1.75, "goles_contra": 0.80, "proj": 3.9},
    "Suecia":           {"ranking": 25, "goles_favor": 1.60, "goles_contra": 0.95, "proj": 3.5},
    "Túnez":            {"ranking": 32, "goles_favor": 1.20, "goles_contra": 1.10, "proj": 2.5},
    "Bélgica":          {"ranking":  9, "goles_favor": 1.85, "goles_contra": 0.85, "proj": 6.3},
    "Irán":             {"ranking": 21, "goles_favor": 1.40, "goles_contra": 0.90, "proj": 3.3},
    "Nueva Zelanda":    {"ranking": 85, "goles_favor": 1.20, "goles_contra": 1.30, "proj": 2.0},
    "Egipto":           {"ranking": 35, "goles_favor": 1.30, "goles_contra": 1.05, "proj": 3.2},
    "España":           {"ranking":  2, "goles_favor": 2.20, "goles_contra": 0.65, "proj": 7.6},
    "Arabia Saudí":     {"ranking": 56, "goles_favor": 1.20, "goles_contra": 1.20, "proj": 2.5},
    "Uruguay":          {"ranking": 17, "goles_favor": 1.75, "goles_contra": 0.67, "proj": 4.5},
    "Cabo Verde":       {"ranking": 72, "goles_favor": 1.10, "goles_contra": 1.90, "proj": 1.8},
    "Francia":          {"ranking":  1, "goles_favor": 2.15, "goles_contra": 0.70, "proj": 7.8},
    "Senegal":          {"ranking": 14, "goles_favor": 1.75, "goles_contra": 0.85, "proj": 5.0},
    "Irak":             {"ranking": 62, "goles_favor": 1.10, "goles_contra": 1.30, "proj": 2.0},
    "Noruega":          {"ranking": 26, "goles_favor": 2.63, "goles_contra": 0.63, "proj": 5.5},
    "Argentina":        {"ranking":  3, "goles_favor": 2.72, "goles_contra": 0.61, "proj": 6.5},
    "Argelia":          {"ranking": 34, "goles_favor": 1.55, "goles_contra": 1.80, "proj": 3.5},
    "Austria":          {"ranking": 27, "goles_favor": 1.65, "goles_contra": 0.95, "proj": 4.0},
    "Jordania":         {"ranking": 79, "goles_favor": 1.10, "goles_contra": 1.60, "proj": 1.8},
    "Portugal":         {"ranking":  5, "goles_favor": 1.90, "goles_contra": 0.75, "proj": 6.2},
    "RD del Congo":     {"ranking": 50, "goles_favor": 1.30, "goles_contra": 1.50, "proj": 2.5},
    "Colombia":         {"ranking": 13, "goles_favor": 2.36, "goles_contra": 0.80, "proj": 5.0},
    "Uzbekistán":       {"ranking": 71, "goles_favor": 1.20, "goles_contra": 1.45, "proj": 2.2},
    "Inglaterra":       {"ranking":  4, "goles_favor": 2.95, "goles_contra": 0.00, "proj": 6.1},
    "Croacia":          {"ranking": 11, "goles_favor": 2.17, "goles_contra": 0.33, "proj": 4.6},
    "Ghana":            {"ranking": 58, "goles_favor": 1.40, "goles_contra": 1.20, "proj": 2.8},
    "Panamá":           {"ranking": 90, "goles_favor": 0.90, "goles_contra": 1.90, "proj": 1.5},
}

FACTOR_LOCAL = 1.08
FACTOR_FASE = {
    "grupos":        1.00,
    "dieciseisavos": 0.92,
    "octavos":       0.88,
    "cuartos":       0.85,
    "semifinales":   0.82,
    "final":         0.80,
}


# ─── Poisson ─────────────────────────────────────────────────────────────────
def poisson(lam: float, k: int) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)


# ─── Variable 1: Rendimiento real del equipo en el torneo ────────────────────
def calcular_rendimiento_real(db: Session, equipo: str, cache: dict | None = None) -> dict | None:
    """
    Calcula promedio real de goles anotados/recibidos del equipo
    basado en partidos finalizados en el torneo.
    Retorna None si no hay partidos finalizados aún.
    Usa cache opcional para evitar recalcular el mismo equipo varias veces.
    """
    if cache is not None and equipo in cache:
        return cache[equipo]

    try:
        partidos_local = db.query(Partido).filter(
            Partido.equipo_local == equipo,
            Partido.estado == EstadoPartido.finalizado,
            Partido.goles_local.isnot(None),
        ).all()

        partidos_visita = db.query(Partido).filter(
            Partido.equipo_visitante == equipo,
            Partido.estado == EstadoPartido.finalizado,
            Partido.goles_visitante.isnot(None),
        ).all()

        total_partidos = len(partidos_local) + len(partidos_visita)
        if total_partidos == 0:
            if cache is not None:
                cache[equipo] = None
            return None

        goles_favor = sum(p.goles_local for p in partidos_local) + \
                      sum(p.goles_visitante for p in partidos_visita)
        goles_contra = sum(p.goles_visitante for p in partidos_local) + \
                       sum(p.goles_local for p in partidos_visita)

        resultado = {
            "goles_favor":  goles_favor / total_partidos,
            "goles_contra": goles_contra / total_partidos,
            "partidos":     total_partidos,
        }
        if cache is not None:
            cache[equipo] = resultado
        return resultado
    except Exception:
        if cache is not None:
            cache[equipo] = None
        return None

def mezclar_stats(estatico: dict, real: dict | None) -> dict:
    """
    Mezcla stats estáticas con rendimiento real según partidos jugados.
    1 partido   → 50% estático + 50% real
    2 partidos  → 20% estático + 80% real
    3+ partidos → 100% real
    """
    if real is None:
        return estatico

    n = real["partidos"]
    if n == 1:
        peso_real = 0.50
    elif n == 2:
        peso_real = 0.80
    else:
        peso_real = 1.00
    peso_est = 1.0 - peso_real

    return {
        "ranking":      estatico["ranking"],
        "goles_favor":  round(estatico["goles_favor"] * peso_est + real["goles_favor"] * peso_real, 3),
        "goles_contra": round(estatico["goles_contra"] * peso_est + real["goles_contra"] * peso_real, 3),
        "proj":         estatico.get("proj", 3.0),
    }


# ─── Variable 2: Historial exitoso del usuario PRO ───────────────────────────
def calcular_perfil_usuario(db: Session, user_id: uuid.UUID) -> dict | None:
    """
    Analiza los pronósticos exitosos del usuario PRO.
    Retorna su tendencia: prefiere marcadores bajos, medios o altos.
    Retorna None si no hay suficiente historial (< 3 aciertos).
    """
    try:
        pronosticos_exitosos = db.query(Pronostico).filter(
            Pronostico.user_id == user_id,
            Pronostico.puntos_obtenidos > 0,
        ).all()

        if len(pronosticos_exitosos) < 3:
            return None

        total_goles = [
            (p.goles_local + p.goles_visitante) for p in pronosticos_exitosos
        ]
        promedio_goles = sum(total_goles) / len(total_goles)

        # Exactos: pronósticos donde acertó el marcador exacto
        exactos = [p for p in pronosticos_exitosos if p.puntos_obtenidos >= 10]
        tasa_exactos = len(exactos) / len(pronosticos_exitosos)

        # Preferencia de diferencia de goles
        diffs = [abs(p.goles_local - p.goles_visitante) for p in pronosticos_exitosos]
        promedio_diff = sum(diffs) / len(diffs)

        return {
            "promedio_goles_total": round(promedio_goles, 2),
            "tasa_exactos":         round(tasa_exactos, 2),
            "promedio_diff":        round(promedio_diff, 2),
            "total_aciertos":       len(pronosticos_exitosos),
        }
    except Exception:
        return None


def ajustar_top3_por_usuario(
    top3: list[dict],
    perfil: dict | None,
    lambda_l: float,
    lambda_v: float,
    max_goles: int = 6,
) -> list[dict]:
    """
    Ajusta el top3 basándose en el perfil del usuario.
    Si no hay perfil → retorna el top3 original sin cambios.
    """
    if perfil is None:
        return top3

    try:
        promedio_goles = perfil["promedio_goles_total"]
        promedio_diff  = perfil["promedio_diff"]

        # Generar todos los marcadores posibles
        candidatos = []
        for g_l in range(max_goles + 1):
            for g_v in range(max_goles + 1):
                total = g_l + g_v
                diff  = abs(g_l - g_v)
                prob_poisson = poisson(lambda_l, g_l) * poisson(lambda_v, g_v)

                # Factor de afinidad con el estilo del usuario
                # Penaliza marcadores muy alejados del estilo del usuario
                factor_total = max(0.5, 1.0 - abs(total - promedio_goles) * 0.15)
                factor_diff  = max(0.5, 1.0 - abs(diff  - promedio_diff)  * 0.10)
                prob_ajustada = prob_poisson * factor_total * factor_diff

                candidatos.append({
                    "goles_local":     g_l,
                    "goles_visitante": g_v,
                    "probabilidad":    round(prob_ajustada * 100, 2),
                    "prob_original":   round(prob_poisson * 100, 2),
                })

        # Tomar el mejor de cada categoría (local gana, empate, visita gana)
        victorias_l = [c for c in candidatos if c["goles_local"] > c["goles_visitante"]]
        empates     = [c for c in candidatos if c["goles_local"] == c["goles_visitante"]]
        victorias_v = [c for c in candidatos if c["goles_local"] < c["goles_visitante"]]

        mejor_l = max(victorias_l, key=lambda x: x["probabilidad"])
        mejor_e = max(empates,     key=lambda x: x["probabilidad"])
        mejor_v = max(victorias_v, key=lambda x: x["probabilidad"])

        # Usar probabilidad original para el display (no confundir al usuario)
        for item in [mejor_l, mejor_e, mejor_v]:
            item["probabilidad"] = item.pop("prob_original")
            item.pop("prob_original", None)

        return sorted([mejor_l, mejor_e, mejor_v],
                      key=lambda x: x["probabilidad"], reverse=True)
    except Exception:
        return top3


# ─── Lambdas ─────────────────────────────────────────────────────────────────
def calcular_lambdas(
    equipo_local: str,
    equipo_visitante: str,
    fase: str,
    db: Session | None = None,
    cache: dict | None = None,
) -> tuple[float, float]:
    stats_l_base = STATS_EQUIPOS.get(equipo_local)
    stats_v_base = STATS_EQUIPOS.get(equipo_visitante)

    if db is not None and stats_l_base and stats_v_base:
        real_l = calcular_rendimiento_real(db, equipo_local, cache)
        real_v = calcular_rendimiento_real(db, equipo_visitante, cache)
        stats_l = mezclar_stats(stats_l_base, real_l)
        stats_v = mezclar_stats(stats_v_base, real_v)
    else:
        stats_l = stats_l_base
        stats_v = stats_v_base

    if not stats_l or not stats_v:
        factor = FACTOR_FASE.get(fase, 0.90)
        return round(1.3 * factor, 3), round(1.0 * factor, 3)

    factor = FACTOR_FASE.get(fase, 0.90)
    promedio_global = 1.7

    diff = stats_v["ranking"] - stats_l["ranking"]
    factor_ranking_l = max(0.75, min(1.50, 1.0 + (diff * 0.008)))
    factor_ranking_v = max(0.75, min(1.50, 1.0 - (diff * 0.008)))

    lambda_local = (stats_l["goles_favor"] / promedio_global) * \
                   (stats_v["goles_contra"] / promedio_global) * \
                   promedio_global * FACTOR_LOCAL * factor * 1.3 * factor_ranking_l

    lambda_visit = (stats_v["goles_favor"] / promedio_global) * \
                   (stats_l["goles_contra"] / promedio_global) * \
                   promedio_global * factor * 1.3 * factor_ranking_v

    return max(0.5, min(4.5, lambda_local)), max(0.3, min(3.8, lambda_visit))


def top3_resultados(lambda_l: float, lambda_v: float, max_goles: int = 6) -> list[dict]:
    victorias_l, empates, victorias_v = [], [], []
    for g_l in range(max_goles + 1):
        for g_v in range(max_goles + 1):
            prob  = poisson(lambda_l, g_l) * poisson(lambda_v, g_v)
            entry = {"goles_local": g_l, "goles_visitante": g_v, "probabilidad": round(prob * 100, 2)}
            if g_l > g_v:   victorias_l.append(entry)
            elif g_l == g_v: empates.append(entry)
            else:            victorias_v.append(entry)

    mejor_l = max(victorias_l, key=lambda x: x["probabilidad"])
    mejor_e = max(empates,     key=lambda x: x["probabilidad"])
    mejor_v = max(victorias_v, key=lambda x: x["probabilidad"])
    return sorted([mejor_l, mejor_e, mejor_v], key=lambda x: x["probabilidad"], reverse=True)


def calcular_1x2(lambda_l: float, lambda_v: float, max_goles: int = 10) -> dict:
    p_local = p_empate = p_visita = 0.0
    for g_l in range(max_goles + 1):
        for g_v in range(max_goles + 1):
            prob = poisson(lambda_l, g_l) * poisson(lambda_v, g_v)
            if g_l > g_v:    p_local  += prob
            elif g_l == g_v: p_empate += prob
            else:             p_visita += prob
    total = p_local + p_empate + p_visita
    return {
        "local":     round((p_local  / total) * 100, 1),
        "empate":    round((p_empate / total) * 100, 1),
        "visitante": round((p_visita / total) * 100, 1),
    }


# ─── Endpoint GET / ───────────────────────────────────────────────────────────
@router.get("/")
def obtener_todas_las_sugerencias(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_pro_user),
):
    sugerencias = db.query(SugerenciaIA).join(Partido).filter(
        Partido.estado != EstadoPartido.finalizado
    ).all()
    perfil = calcular_perfil_usuario(db, current_user.id)
    cache_rendimiento: dict = {}
    resultado = []
    for s in sugerencias:
        try:
            lambda_l, lambda_v = calcular_lambdas(
                s.partido.equipo_local,
                s.partido.equipo_visitante,
                s.partido.fase,
                db=db,
                cache=cache_rendimiento,
            )
            top3     = top3_resultados(lambda_l, lambda_v)
            top3     = ajustar_top3_por_usuario(top3, perfil, lambda_l, lambda_v)
            prob_1x2 = calcular_1x2(lambda_l, lambda_v)
            resultado.append({
                "partido_id":      str(s.partido_id),
                "goles_local":     top3[0]["goles_local"],
                "goles_visitante": top3[0]["goles_visitante"],
                "confianza":       top3[0]["probabilidad"],
                "top3":            top3,
                "probabilidades": {
                    "Local":     prob_1x2["local"],
                    "Empate":    prob_1x2["empate"],
                    "Visitante": prob_1x2["visitante"],
                },
            })
        except Exception:
            resultado.append({
                "partido_id":      str(s.partido_id),
                "goles_local":     s.goles_local,
                "goles_visitante": s.goles_visitante,
                "confianza":       s.confianza,
                "top3":            [],
                "probabilidades":  {"Local": 33.3, "Empate": 33.3, "Visitante": 33.3},
            })
    return resultado


# ─── Endpoint GET /{partido_id} ───────────────────────────────────────────────
@router.get("/{partido_id}")
def obtener_sugerencia_ia(
    partido_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_pro_user),
):
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    try:
        lambda_l, lambda_v = calcular_lambdas(
            partido.equipo_local,
            partido.equipo_visitante,
            partido.fase,
            db=db,
        )
        perfil = calcular_perfil_usuario(db, current_user.id)
        top3   = top3_resultados(lambda_l, lambda_v)
        top3   = ajustar_top3_por_usuario(top3, perfil, lambda_l, lambda_v)
    except Exception:
        lambda_l, lambda_v = calcular_lambdas(
            partido.equipo_local,
            partido.equipo_visitante,
            partido.fase,
        )
        top3 = top3_resultados(lambda_l, lambda_v)

    prob_1x2  = calcular_1x2(lambda_l, lambda_v)
    principal = top3[0]

    sugerencia = db.query(SugerenciaIA).filter(SugerenciaIA.partido_id == partido_id).first()
    if not sugerencia:
        sugerencia = SugerenciaIA(
            partido_id=      partido_id,
            goles_local=     principal["goles_local"],
            goles_visitante= principal["goles_visitante"],
            confianza=       principal["probabilidad"] / 100,
        )
        db.add(sugerencia)
        db.commit()
        db.refresh(sugerencia)

    return {
        "partido_id":       str(partido_id),
        "equipo_local":     partido.equipo_local,
        "equipo_visitante": partido.equipo_visitante,
        "goles_local":      principal["goles_local"],
        "goles_visitante":  principal["goles_visitante"],
        "confianza":        principal["probabilidad"],
        "top3":             top3,
        "probabilidades": {
            "Local":     prob_1x2["local"],
            "Empate":    prob_1x2["empate"],
            "Visitante": prob_1x2["visitante"],
        },
        "goles_esperados": {
            "local":     round(lambda_l, 2),
            "visitante": round(lambda_v, 2),
        },
    }


# ─── POST /precalcular ────────────────────────────────────────────────────────
@router.post("/precalcular")
def precalcular_sugerencias(
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_api_key),
):
    partidos  = db.query(Partido).filter(Partido.fase.in_(["grupos", "dieciseisavos"])).all()
    cache_rendimiento: dict = {}
    generados = actualizados = 0

    for partido in partidos:
        try:
            lambda_l, lambda_v = calcular_lambdas(
                partido.equipo_local,
                partido.equipo_visitante,
                partido.fase,
                db=db,
                cache=cache_rendimiento,
            )
            top3      = top3_resultados(lambda_l, lambda_v)
            principal = top3[0]
        except Exception:
            continue

        sugerencia = db.query(SugerenciaIA).filter(
            SugerenciaIA.partido_id == partido.id
        ).first()

        if not sugerencia:
            db.add(SugerenciaIA(
                partido_id=      partido.id,
                goles_local=     principal["goles_local"],
                goles_visitante= principal["goles_visitante"],
                confianza=       principal["probabilidad"] / 100,
            ))
            generados += 1
        else:
            sugerencia.goles_local     = principal["goles_local"]
            sugerencia.goles_visitante = principal["goles_visitante"]
            sugerencia.confianza       = principal["probabilidad"] / 100
            actualizados += 1

    db.commit()
    return {"status": "ok", "generados": generados, "actualizados": actualizados}