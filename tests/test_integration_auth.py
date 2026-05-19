from __future__ import annotations

import uuid

import pytest


@pytest.mark.integration
def test_registro_login_y_me(client, db_available):
    if not db_available:
        pytest.skip("DATABASE_URL no accesible — revisa .env y que Supabase esté activo")

    uid = uuid.uuid4().hex[:12]
    email = f"pytest_{uid}@example.com"
    password = "TestPass123!"
    nombre = "Usuario Pytest"

    reg = client.post(
        "/api/auth/registro",
        json={"email": email, "password": password, "nombre": nombre},
    )
    assert reg.status_code == 201, reg.text
    data = reg.json()
    assert "access_token" in data
    assert data["user"]["email"] == email
    token = data["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["nombre"] == nombre

    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    assert login.json()["access_token"]


@pytest.mark.integration
def test_login_credenciales_invalidas(client, db_available):
    if not db_available:
        pytest.skip("DATABASE_URL no accesible")

    r = client.post(
        "/api/auth/login",
        json={"email": "noexiste_pytest@example.com", "password": "wrongpass99"},
    )
    assert r.status_code == 401
