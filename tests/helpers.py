"""Utilidades compartidas para tests de integración."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi.testclient import TestClient


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_user(
    client: TestClient,
    *,
    prefix: str = "pytest",
    nombre: str | None = None,
) -> dict[str, Any]:
    """Registra un usuario único y devuelve token, email e id."""
    uid = uuid.uuid4().hex[:10]
    email = f"{prefix}_{uid}@example.com"
    password = "TestPass123!"
    nombre = nombre or f"Test {prefix}"

    r = client.post(
        "/api/auth/registro",
        json={"email": email, "password": password, "nombre": nombre},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    return {
        "token": data["access_token"],
        "email": email,
        "password": password,
        "user_id": data["user"]["id"],
        "headers": auth_headers(data["access_token"]),
    }


def get_partido_abierto_id() -> str | None:
    """UUID de un partido pendiente con ventana >15 min para pronosticar (free)."""
    from app.core.database import SessionLocal
    from app.models.models import EstadoPartido, Partido

    now = datetime.now(timezone.utc)
    limite = now + timedelta(minutes=20)

    db = SessionLocal()
    try:
        partidos = (
            db.query(Partido)
            .filter(Partido.estado == EstadoPartido.pendiente)
            .order_by(Partido.fecha_hora)
            .all()
        )
        for p in partidos:
            fh = p.fecha_hora
            if fh.tzinfo is None:
                fh = fh.replace(tzinfo=timezone.utc)
            if fh > limite:
                return str(p.id)
    finally:
        db.close()
    return None
