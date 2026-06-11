"""
Recalcula puntos_obtenidos y totales de ranking para todos los partidos finalizados.
Útil tras corregir INTERNAL_API_KEY o cuando score_updater no pudo llamar a FastAPI.

Uso (desde backend/):
    python scripts/recalcular_puntos_pendientes.py
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from app.core.database import SessionLocal
from app.models.models import Partido, EstadoPartido
from app.routers.pronosticos import aplicar_puntos_a_partido


def main() -> None:
    db = SessionLocal()
    try:
        partidos = (
            db.query(Partido)
            .filter(
                Partido.estado == EstadoPartido.finalizado,
                Partido.goles_local.isnot(None),
                Partido.goles_visitante.isnot(None),
            )
            .order_by(Partido.fecha_hora)
            .all()
        )

        if not partidos:
            print("No hay partidos finalizados con marcador.")
            return

        total_pronosticos = 0
        for partido in partidos:
            n = aplicar_puntos_a_partido(db, partido)
            total_pronosticos += n
            print(
                f"  {partido.equipo_local} vs {partido.equipo_visitante}: "
                f"{n} pronóstico(s)"
            )

        print(
            f"\nListo: {len(partidos)} partido(s), "
            f"{total_pronosticos} pronóstico(s) actualizados."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
