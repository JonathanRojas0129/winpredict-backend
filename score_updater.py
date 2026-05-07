"""
score_updater.py — Fuente de la Verdad · WinPredict
=====================================================
Extrae resultados de múltiples fuentes web, valida por consenso,
actualiza Supabase y dispara el cálculo de puntos vía FastAPI.

Uso:
    python score_updater.py              # ejecutar ahora
    python score_updater.py --dry-run   # simular sin escribir en BD

Cron (cada 10 min):
    */10 * * * * /usr/bin/python3 /ruta/score_updater.py >> /var/log/winpredict/scores.log 2>&1
"""

import os
import sys
import json
import logging
import argparse
import unicodedata
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

import httpx
from dotenv import load_dotenv
from supabase import create_client, Client
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ─── Config ──────────────────────────────────────────────────────────────────
load_dotenv(".env.score")

SUPABASE_URL      = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY      = os.getenv("SUPABASE_SERVICE_KEY", "")   # service_role key (bypasa RLS)
FASTAPI_BASE_URL  = os.getenv("BACKEND_URL", "http://localhost:8000")
FASTAPI_API_KEY   = os.getenv("INTERNAL_API_KEY", "")       # opcional — header X-Internal-Key
LOG_LEVEL         = os.getenv("LOG_LEVEL", "INFO")
HEADLESS          = os.getenv("HEADLESS", "true").lower() == "true"

# ─── Logging ──────────────────────────────────────────────────────────────────
log_fmt = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=log_fmt,
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("score_updater")

# ─── Tipos ────────────────────────────────────────────────────────────────────
@dataclass
class Marcador:
    goles_local:     int
    goles_visitante: int
    finalizado:      bool
    fuente:          str

@dataclass
class Partido:
    id:               str
    equipo_local:     str
    equipo_visitante: str
    fecha_hora:       str
    bandera_local:    Optional[str] = None
    bandera_visitante: Optional[str] = None


# ─── Normalización de nombres de equipos ──────────────────────────────────────
# Agrega aquí cualquier variante que aparezca en las fuentes web.
# Clave = variante externa → Valor = nombre exacto en tu tabla `partidos`

ALIAS: dict[str, str] = {
    # Corea del Sur
    "korea republic":       "Corea del Sur",
    "south korea":          "Corea del Sur",
    "corea del sur":        "Corea del Sur",
    "korea":                "Corea del Sur",
    "rep. of korea":        "Corea del Sur",
    # Estados Unidos
    "united states":        "Estados Unidos",
    "usa":                  "Estados Unidos",
    "u.s.a.":               "Estados Unidos",
    "us":                   "Estados Unidos",
    # Irán
    "ir iran":              "Irán",
    "iran":                 "Irán",
    # Costa de Marfil
    "ivory coast":          "Costa de Marfil",
    "côte d'ivoire":        "Costa de Marfil",
    "cote d'ivoire":        "Costa de Marfil",
    # República Checa
    "czech republic":       "República Checa",
    "czechia":              "República Checa",
    # Macedonia del Norte
    "north macedonia":      "Macedonia del Norte",
    "macedonia":            "Macedonia del Norte",
    # Resto — agrega según lo que encuentres en logs de discrepancias
    "england":              "Inglaterra",
    "scotland":             "Escocia",
    "wales":                "Gales",
    "northern ireland":     "Irlanda del Norte",
    "united arab emirates": "Emiratos Árabes Unidos",
    "uae":                  "Emiratos Árabes Unidos",
    "dpr korea":            "Corea del Norte",
    "north korea":          "Corea del Norte",
    "cape verde":           "Cabo Verde",
    "trinidad and tobago":  "Trinidad y Tobago",
    "trinidad & tobago":    "Trinidad y Tobago",
}

def normalizar(nombre: str) -> str:
    """Quita tildes, pasa a minúsculas y resuelve alias."""
    txt = unicodedata.normalize("NFKD", nombre)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.lower().strip()
    return ALIAS.get(txt, nombre.strip())   # si no hay alias, devuelve el original limpio

def equipos_coinciden(a: str, b: str) -> bool:
    return normalizar(a) == normalizar(b)


# ─── Scraper base ─────────────────────────────────────────────────────────────
class BaseScraper:
    nombre: str = "base"

    def obtener_marcador(
        self, page, equipo_local: str, equipo_visitante: str
    ) -> Optional[Marcador]:
        raise NotImplementedError


# ─── Scraper 1: Google Search Scoreboard ─────────────────────────────────────
class GoogleScraper(BaseScraper):
    nombre = "Google"

    def obtener_marcador(self, page, equipo_local: str, equipo_visitante: str) -> Optional[Marcador]:
        query = f"{equipo_local} vs {equipo_visitante} resultado"
        url   = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=es"

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_timeout(2000)

            # Google muestra el marcador en un panel destacado
            # Selector del scorecard de Google (puede variar; usamos múltiples fallbacks)
            selectors_score = [
                "[data-ved] .imso_mh__lf-st",   # formato clásico
                ".imspo_mt__lt-t",
                ".imspo_mt__t-sc .imspo_mt__sc",
                "div[class*='score']",
            ]
            selectors_status = [
                ".imspo_mt__ms",
                "[class*='status']",
                "[class*='estado']",
            ]

            score_text  = None
            status_text = ""

            for sel in selectors_score:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        score_text = el.inner_text(timeout=2000).strip()
                        break
                except Exception:
                    continue

            for sel in selectors_status:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1000):
                        status_text = el.inner_text(timeout=1000).strip().lower()
                        break
                except Exception:
                    continue

            if not score_text:
                log.debug(f"[Google] No se encontró scorecard para {equipo_local} vs {equipo_visitante}")
                return None

            # Parsear "2 - 1" o "2:1"
            marcador = self._parsear_score(score_text)
            if marcador is None:
                return None

            finalizado = any(w in status_text for w in ["final", "finaliz", "terminad", "ft", "full time"])

            return Marcador(
                goles_local=     marcador[0],
                goles_visitante= marcador[1],
                finalizado=      finalizado,
                fuente=          self.nombre,
            )
        except PlaywrightTimeout:
            log.warning(f"[Google] Timeout para {equipo_local} vs {equipo_visitante}")
            return None
        except Exception as e:
            log.warning(f"[Google] Error inesperado: {e}")
            return None

    def _parsear_score(self, texto: str) -> Optional[tuple[int, int]]:
        import re
        m = re.search(r"(\d+)\s*[-:]\s*(\d+)", texto)
        if m:
            return int(m.group(1)), int(m.group(2))
        return None


# ─── Scraper 2: Flashscore ────────────────────────────────────────────────────
class FlashscoreScraper(BaseScraper):
    nombre = "Flashscore"

    def obtener_marcador(self, page, equipo_local: str, equipo_visitante: str) -> Optional[Marcador]:
        query = f"{equipo_local} {equipo_visitante}"
        url   = f"https://www.flashscore.es/buscar/?q={query.replace(' ', '%20')}"

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25_000)
            page.wait_for_timeout(3000)

            # Cerrar cookie banner si aparece
            try:
                page.locator("#onetrust-accept-btn-handler").click(timeout=3000)
                page.wait_for_timeout(500)
            except Exception:
                pass

            # Buscar el partido en los resultados de búsqueda
            # Flashscore muestra filas con clase "event__match"
            filas = page.locator(".event__match, .sportName__match").all()

            for fila in filas[:10]:   # revisar los primeros 10 resultados
                try:
                    texto_fila = fila.inner_text(timeout=2000).lower()

                    local_norm     = normalizar(equipo_local)
                    visitante_norm = normalizar(equipo_visitante)

                    if local_norm not in texto_fila and visitante_norm not in texto_fila:
                        continue

                    # Extraer equipos y score de la fila
                    home_el  = fila.locator(".event__homeParticipant, .event__participant--home").first
                    away_el  = fila.locator(".event__awayParticipant, .event__participant--away").first
                    score_el = fila.locator(".event__score, .event__scores").first

                    home_name  = home_el.inner_text(timeout=1500).strip()
                    away_name  = away_el.inner_text(timeout=1500).strip()
                    score_text = score_el.inner_text(timeout=1500).strip()

                    # Validar que los equipos coincidan (con normalización)
                    if not (equipos_coinciden(home_name, equipo_local) and
                            equipos_coinciden(away_name, equipo_visitante)):
                        continue

                    # Parsear score "2 - 1"
                    marcador = self._parsear_score(score_text)
                    if marcador is None:
                        continue

                    # Detectar estado — Flashscore pone "FT" en un badge
                    status_el   = fila.locator(".event__stage--block, .event__stage").first
                    status_text = ""
                    try:
                        status_text = status_el.inner_text(timeout=1000).strip().lower()
                    except Exception:
                        pass

                    finalizado = any(w in status_text for w in ["ft", "ap", "aet", "fin", "final"])

                    return Marcador(
                        goles_local=     marcador[0],
                        goles_visitante= marcador[1],
                        finalizado=      finalizado,
                        fuente=          self.nombre,
                    )
                except Exception as e:
                    log.debug(f"[Flashscore] Error procesando fila: {e}")
                    continue

            log.debug(f"[Flashscore] Partido no encontrado: {equipo_local} vs {equipo_visitante}")
            return None

        except PlaywrightTimeout:
            log.warning(f"[Flashscore] Timeout para {equipo_local} vs {equipo_visitante}")
            return None
        except Exception as e:
            log.warning(f"[Flashscore] Error inesperado: {e}")
            return None

    def _parsear_score(self, texto: str) -> Optional[tuple[int, int]]:
        import re
        m = re.search(r"(\d+)\s*[-:]\s*(\d+)", texto)
        if m:
            return int(m.group(1)), int(m.group(2))
        return None


# ─── Consenso ─────────────────────────────────────────────────────────────────
def validar_consenso(
    marcadores: list[Optional[Marcador]],
    partido: Partido,
) -> Optional[Marcador]:
    """
    Devuelve un Marcador si y solo si:
    - Al menos 2 fuentes tienen resultado
    - Todas las fuentes disponibles coinciden en el marcador
    - Todas las fuentes dicen que el partido está finalizado
    """
    validos = [m for m in marcadores if m is not None]

    if len(validos) < 2:
        fuentes_con_dato = [m.fuente for m in validos] if validos else ["ninguna"]
        log.warning(
            f"[CONSENSO FALLIDO] {partido.equipo_local} vs {partido.equipo_visitante} — "
            f"solo {len(validos)} fuente(s) con dato: {fuentes_con_dato}"
        )
        return None

    # Verificar que todos están finalizados
    if not all(m.finalizado for m in validos):
        no_fin = [m.fuente for m in validos if not m.finalizado]
        log.info(
            f"[EN CURSO] {partido.equipo_local} vs {partido.equipo_visitante} — "
            f"fuentes sin 'finalizado': {no_fin}"
        )
        return None

    # Verificar que todos coinciden en el marcador
    referencia = validos[0]
    for m in validos[1:]:
        if m.goles_local != referencia.goles_local or m.goles_visitante != referencia.goles_visitante:
            log.warning(
                f"[DISCREPANCIA] {partido.equipo_local} vs {partido.equipo_visitante} — "
                f"{referencia.fuente}: {referencia.goles_local}-{referencia.goles_visitante} | "
                f"{m.fuente}: {m.goles_local}-{m.goles_visitante}"
            )
            return None

    log.info(
        f"[CONSENSO OK] {partido.equipo_local} vs {partido.equipo_visitante} → "
        f"{referencia.goles_local}-{referencia.goles_visitante} "
        f"(fuentes: {[m.fuente for m in validos]})"
    )
    return referencia


# ─── Supabase ─────────────────────────────────────────────────────────────────
def obtener_partidos_pendientes(sb: Client) -> list[Partido]:
    """
    Lee partidos con estado='pendiente' cuya fecha_hora ya pasó (en UTC).
    Incluye un margen de 105 min (90 min partido + 15 min extra).
    """
    ahora_utc = datetime.now(timezone.utc).isoformat()

    res = (
        sb.table("partidos")
        .select("id, equipo_local, equipo_visitante, fecha_hora, bandera_local, bandera_visitante")
        .eq("estado", "pendiente")
        .lt("fecha_hora", ahora_utc)
        .execute()
    )

    partidos = []
    for row in (res.data or []):
        partidos.append(Partido(
            id=               row["id"],
            equipo_local=     row["equipo_local"],
            equipo_visitante= row["equipo_visitante"],
            fecha_hora=       row["fecha_hora"],
            bandera_local=    row.get("bandera_local"),
            bandera_visitante= row.get("bandera_visitante"),
        ))

    log.info(f"Partidos pendientes de verificar: {len(partidos)}")
    return partidos


def actualizar_partido(sb: Client, partido: Partido, marcador: Marcador, dry_run: bool) -> bool:
    if dry_run:
        log.info(
            f"[DRY-RUN] UPDATE partidos SET goles_local={marcador.goles_local}, "
            f"goles_visitante={marcador.goles_visitante}, estado='finalizado' "
            f"WHERE id='{partido.id}'"
        )
        return True

    try:
        sb.table("partidos").update({
            "goles_local":     marcador.goles_local,
            "goles_visitante": marcador.goles_visitante,
            "estado":          "finalizado",
            "actualizado_en":  datetime.now(timezone.utc).isoformat(),
        }).eq("id", partido.id).execute()

        log.info(f"✅ BD actualizada: {partido.equipo_local} {marcador.goles_local}-{marcador.goles_visitante} {partido.equipo_visitante}")
        return True
    except Exception as e:
        log.error(f"❌ Error actualizando BD para partido {partido.id}: {e}")
        return False


# ─── Webhook FastAPI ───────────────────────────────────────────────────────────
def disparar_calculo_puntos(partido_id: str, dry_run: bool) -> bool:
    if dry_run:
        log.info(f"[DRY-RUN] POST {FASTAPI_BASE_URL}/api/pronosticos/calcular-puntos/{partido_id}")
        return True

    url     = f"{FASTAPI_BASE_URL}/api/pronosticos/calcular-puntos/{partido_id}"
    headers = {"Content-Type": "application/json"}
    if FASTAPI_API_KEY:
        headers["X-Internal-Key"] = FASTAPI_API_KEY

    try:
        res = httpx.post(url, headers=headers, timeout=15)
        if res.status_code in (200, 201, 204):
            log.info(f"🎯 Puntos calculados para partido {partido_id}")
            return True
        else:
            log.warning(f"⚠️ FastAPI respondió {res.status_code} para partido {partido_id}: {res.text[:200]}")
            return False
    except httpx.RequestError as e:
        log.error(f"❌ No se pudo conectar con FastAPI para partido {partido_id}: {e}")
        return False


# ─── Loop principal ───────────────────────────────────────────────────────────
def run(dry_run: bool = False):
    log.info("=" * 60)
    log.info(f"🚀 score_updater iniciado — {'DRY-RUN' if dry_run else 'PRODUCCIÓN'}")
    log.info(f"   Hora UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    # Validar config
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("SUPABASE_URL / SUPABASE_SERVICE_KEY no configuradas en .env")
        sys.exit(1)

    # Conectar Supabase
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Obtener partidos a verificar
    partidos = obtener_partidos_pendientes(sb)
    if not partidos:
        log.info("Sin partidos pendientes. Fin.")
        return

    # Inicializar scrapers
    scrapers = [GoogleScraper(), FlashscoreScraper()]

    stats = {"verificados": 0, "actualizados": 0, "discrepancias": 0, "sin_dato": 0}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="es-ES",
            viewport={"width": 1280, "height": 800},
        )

        for partido in partidos:
            log.info(f"\n── Verificando: {partido.equipo_local} vs {partido.equipo_visitante} ──")
            stats["verificados"] += 1

            marcadores: list[Optional[Marcador]] = []

            for scraper in scrapers:
                page = context.new_page()
                try:
                    marcador = scraper.obtener_marcador(
                        page,
                        partido.equipo_local,
                        partido.equipo_visitante,
                    )
                    marcadores.append(marcador)
                    if marcador:
                        log.debug(
                            f"   [{scraper.nombre}] "
                            f"{marcador.goles_local}-{marcador.goles_visitante} "
                            f"{'✓ Final' if marcador.finalizado else '⏳ En curso'}"
                        )
                    else:
                        log.debug(f"   [{scraper.nombre}] Sin dato")
                except Exception as e:
                    log.warning(f"   [{scraper.nombre}] Excepción: {e}")
                    marcadores.append(None)
                finally:
                    page.close()

            # Validar consenso
            resultado = validar_consenso(marcadores, partido)

            if resultado is None:
                validos = [m for m in marcadores if m is not None]
                if len(validos) < 2:
                    stats["sin_dato"] += 1
                else:
                    stats["discrepancias"] += 1
                continue

            # Actualizar BD
            ok_bd = actualizar_partido(sb, partido, resultado, dry_run)
            if not ok_bd:
                continue

            # Disparar cálculo de puntos
            disparar_calculo_puntos(partido.id, dry_run)
            stats["actualizados"] += 1

        context.close()
        browser.close()

    # Resumen final
    log.info("\n" + "=" * 60)
    log.info("📊 RESUMEN DE EJECUCIÓN")
    log.info(f"   Partidos verificados : {stats['verificados']}")
    log.info(f"   Actualizados en BD   : {stats['actualizados']}")
    log.info(f"   Discrepancias        : {stats['discrepancias']}")
    log.info(f"   Sin dato suficiente  : {stats['sin_dato']}")
    log.info("=" * 60)


# ─── Entrypoint ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WinPredict — Actualizador de resultados")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la ejecución sin escribir en BD ni llamar a FastAPI",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)
