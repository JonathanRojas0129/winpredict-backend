"""
Configuración global de pytest.

Carga `.env` del backend antes de importar la app para usar Supabase/Postgres real.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_ROOT / ".env")

# Solo defaults si faltan tras cargar .env
os.environ.setdefault("SECRET_KEY", "pytest-secret-key-minimum-32-characters!")

import pytest
from fastapi.testclient import TestClient


def _db_reachable() -> bool:
    """Comprueba conexión a la BD configurada en DATABASE_URL."""
    try:
        from sqlalchemy import text
        from app.core.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def db_available() -> bool:
    return _db_reachable()


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    return TestClient(app)
