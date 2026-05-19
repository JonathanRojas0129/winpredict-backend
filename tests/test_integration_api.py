from __future__ import annotations

import uuid

import pytest


@pytest.mark.integration
def test_partidos_requiere_auth(client, db_available):
    if not db_available:
        pytest.skip("DATABASE_URL no accesible")

    r = client.get("/api/partidos/")
    assert r.status_code == 403


@pytest.mark.integration
def test_partidos_listado_con_token(client, db_available):
    if not db_available:
        pytest.skip("DATABASE_URL no accesible")

    uid = uuid.uuid4().hex[:12]
    email = f"pytest_partidos_{uid}@example.com"
    reg = client.post(
        "/api/auth/registro",
        json={"email": email, "password": "TestPass123!", "nombre": "Tester"},
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]

    r = client.get(
        "/api/partidos/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.integration
def test_partidos_estado_invalido(client, db_available):
    if not db_available:
        pytest.skip("DATABASE_URL no accesible")

    uid = uuid.uuid4().hex[:12]
    reg = client.post(
        "/api/auth/registro",
        json={
            "email": f"pytest_estado_{uid}@example.com",
            "password": "TestPass123!",
            "nombre": "Tester",
        },
    )
    token = reg.json()["access_token"]

    r = client.get(
        "/api/partidos/?estado=no_valido",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
