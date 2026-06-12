"""
auto_complete_pro.py — WinPredict
==================================
Autocompleta pronósticos para usuarios PRO que no registraron
su marcador antes del cierre del partido.
Asigna automáticamente la sugerencia IA (top1) como pronóstico.
Solo aplica a usuarios PRO con suscripción vigente.
Usa el mismo motor estadístico de sugerencias.py.

Cron: cada 5 minutos
"""

import sys
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv
load_dotenv(BACKEND_ROOT / ".env")

from app.core.database import SessionLocal
from app.models.models import (
    User, Partido, Pronostico, GrupoParticipante,
    EstadoPartido, FuentePronostico,
)
from app.routers.sugerencias import calcular_lambdas, top3_resultados
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("auto_complete_pro")


def calcular_sugerencia(db: Session, equipo_local: str, equipo_visitante: str, fase: str) -> tuple[int, int]:
    """
    Usa el mismo motor de sugerencias.py para consistencia.
    Incluye rendimiento real del torneo si hay partidos finalizados.
    """
    try:
        lambda_l, lambda_v = calcular_lambdas(equipo_local, equipo_visitante, fase, db=db)
        top3 = top3_resultados(lambda_l, lambda_v)
        return top3[0]["goles_local"], top3[0]["goles_visitante"]
    except Exception as e:
        log.warning(f"Error calculando sugerencia para {equipo_local} vs {equipo_visitante}: {e}")
        return 1, 0


def autocompletar_pronosticos(db: Session) -> int:
    ahora = datetime.now(timezone.utc)
    ventana_fin = ahora + timedelta(minutes=15)

    # ── 1. Partidos próximos a cerrar (próximos 15 min) ──────────────
    partidos_proximos = db.query(Partido).filter(
        Partido.estado == EstadoPartido.pendiente,
        Partido.cierre_pronosticos > ahora,
        Partido.cierre_pronosticos <= ventana_fin,
    ).all()

    # ── 2. Partidos ya cerrados o en vivo sin pronóstico ─────────────
    partidos_cerrados = db.query(Partido).filter(
        Partido.estado.in_([EstadoPartido.pendiente, EstadoPartido.vivo]),
        Partido.cierre_pronosticos <= ahora,
    ).all()

    # Unir evitando duplicados
    partidos = list({p.id: p for p in partidos_proximos + partidos_cerrados}.values())

    if not partidos:
        log.info("Sin partidos para autocompletar.")
        return 0

    log.info(f"Partidos a procesar: {len(partidos)} "
             f"({len(partidos_proximos)} próximos, {len(partidos_cerrados)} cerrados/vivos)")

    total_autocompletados = 0

    for partido in partidos:
        log.info(f"── Procesando: {partido.equipo_local} vs {partido.equipo_visitante}")

        # Calcular sugerencia IA usando el mismo motor de sugerencias.py
        gl, gv = calcular_sugerencia(db, partido.equipo_local, partido.equipo_visitante, partido.fase)
        log.info(f"   Sugerencia IA: {gl}-{gv}")

        # Obtener todos los grupos activos
        grupos_ids = db.query(GrupoParticipante.grupo_id).filter(
            GrupoParticipante.estado_participante == "aprobado"
        ).distinct().all()
        grupos_ids = [g[0] for g in grupos_ids]

        for grupo_id in grupos_ids:

            # ── Solo usuarios PRO vigentes en este grupo ──────────────
            participantes_pro = db.query(GrupoParticipante).join(
                User, User.id == GrupoParticipante.user_id
            ).filter(
                GrupoParticipante.grupo_id == grupo_id,
                GrupoParticipante.estado_participante == "aprobado",
                User.es_pro == True,
                User.pro_expira_en > ahora,
            ).all()

            if not participantes_pro:
                continue

            for participante in participantes_pro:
                user_id = participante.user_id

                # Verificar si ya tiene pronóstico para este partido/grupo
                existe = db.query(Pronostico).filter(
                    Pronostico.user_id    == user_id,
                    Pronostico.partido_id == partido.id,
                    Pronostico.grupo_id   == grupo_id,
                ).first()

                if existe:
                    continue

                # Crear pronóstico automático con sugerencia IA
                nuevo = Pronostico(
                    user_id=            user_id,
                    partido_id=         partido.id,
                    grupo_id=           grupo_id,
                    goles_local=        gl,
                    goles_visitante=    gv,
                    fuente=             FuentePronostico.ia,
                    fue_autocompletado= True,
                )
                db.add(nuevo)
                total_autocompletados += 1
                log.info(f"  ✅ PRO autocompletado: user {user_id} | grupo {grupo_id} | {gl}-{gv}")

    db.commit()
    log.info(f"Total autocompletados: {total_autocompletados}")
    return total_autocompletados


def main():
    log.info("=" * 60)
    log.info(f"🤖 auto_complete_pro iniciado — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    log.info("=" * 60)
    db = SessionLocal()
    try:
        autocompletar_pronosticos(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()