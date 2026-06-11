"""
score_updater.py — Fuente de la Verdad · WinPredict
=====================================================
Lee resultados desde Google Sheets y actualiza Supabase.
Luego dispara el cálculo de puntos vía FastAPI.
"""

import os
import sys
import logging
import argparse
import csv
import io
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

# ─── Config ──────────────────────────────────────────────────────────────────
load_dotenv(".env.score")

SUPABASE_URL     = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY     = os.getenv("SUPABASE_SERVICE_KEY", "")
FASTAPI_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FASTAPI_API_KEY  = os.getenv("INTERNAL_API_KEY", "")
LOG_LEVEL        = os.getenv("LOG_LEVEL", "INFO")
SHEETS_CSV_URL   = os.getenv("SHEETS_CSV_URL", "")

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("score_updater")


# ─── Leer Google Sheets ───────────────────────────────────────────────────────
def leer_resultados_sheets() -> list[dict]:
    if not SHEETS_CSV_URL:
        log.error("SHEETS_CSV_URL no configurada")
        return []
    try:
        res = httpx.get(SHEETS_CSV_URL, timeout=15, follow_redirects=True)
        res.raise_for_status()
        reader = csv.DictReader(io.StringIO(res.text))
        resultados = []
        for row in reader:
            partido_id  = row.get("partido_id", "").strip()
            finalizado  = row.get("finalizado", "").strip().upper()
            goles_local = row.get("goles_local", "").strip()
            goles_vis   = row.get("goles_visitante", "").strip()

            if not partido_id or finalizado != "SI":
                continue
            if not goles_local.isdigit() or not goles_vis.isdigit():
                continue

            resultados.append({
                "partido_id":      partido_id,
                "goles_local":     int(goles_local),
                "goles_visitante": int(goles_vis),
            })
        log.info(f"Resultados listos en Sheets: {len(resultados)}")
        return resultados
    except Exception as e:
        log.error(f"Error leyendo Google Sheets: {e}")
        return []


# ─── Actualizar partido en Supabase ──────────────────────────────────────────
def actualizar_partido(sb: Client, partido_id: str, goles_local: int, goles_visitante: int, dry_run: bool) -> bool:
    # Verificar si ya está finalizado
    res = sb.table("partidos").select("estado, equipo_local, equipo_visitante").eq("id", partido_id).single().execute()
    if not res.data:
        log.warning(f"Partido {partido_id} no encontrado en BD")
        return False

    if res.data["estado"] == "finalizado":
        log.debug(f"Partido {res.data['equipo_local']} vs {res.data['equipo_visitante']} ya finalizado — saltando")
        return False

    if dry_run:
        log.info(f"[DRY-RUN] {res.data['equipo_local']} {goles_local}-{goles_visitante} {res.data['equipo_visitante']}")
        return True

    sb.table("partidos").update({
        "goles_local":     goles_local,
        "goles_visitante": goles_visitante,
        "estado":          "finalizado",
    }).eq("id", partido_id).execute()

    log.info(f"✅ {res.data['equipo_local']} {goles_local}-{goles_visitante} {res.data['equipo_visitante']}")
    return True


# ─── Disparar cálculo de puntos ───────────────────────────────────────────────
def disparar_calculo_puntos(partido_id: str, dry_run: bool) -> bool:
    if dry_run:
        log.info(f"[DRY-RUN] POST calcular-puntos/{partido_id}")
        return True

    url     = f"{FASTAPI_BASE_URL}/api/pronosticos/calcular-puntos/{partido_id}"
    headers = {"Content-Type": "application/json"}
    if FASTAPI_API_KEY:
        headers["X-Internal-Key"] = FASTAPI_API_KEY

    try:
        res = httpx.post(url, headers=headers, timeout=15)
        if res.status_code in (200, 201, 204):
            log.info(f"🎯 Puntos calculados para {partido_id}")
            return True
        else:
            log.warning(f"⚠️ FastAPI {res.status_code} para {partido_id}: {res.text[:200]}")
            return False
    except httpx.RequestError as e:
        log.error(f"❌ Error conectando FastAPI: {e}")
        return False


# ─── Loop principal ───────────────────────────────────────────────────────────
def run(dry_run: bool = False):
    log.info("=" * 60)
    log.info(f"🚀 score_updater iniciado — {'DRY-RUN' if dry_run else 'PRODUCCIÓN'}")
    log.info(f"   Hora UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("SUPABASE_URL / SUPABASE_SERVICE_KEY no configuradas")
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    resultados = leer_resultados_sheets()
    if not resultados:
        log.info("Sin resultados nuevos en Sheets.")
    else:
        actualizados = 0
        for r in resultados:
            ok = actualizar_partido(sb, r["partido_id"], r["goles_local"], r["goles_visitante"], dry_run)
            if ok:
                disparar_calculo_puntos(r["partido_id"], dry_run)
                actualizados += 1
        log.info(f"Partidos actualizados: {actualizados}/{len(resultados)}")

    log.info("=" * 60)


# ─── Entrypoint ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)