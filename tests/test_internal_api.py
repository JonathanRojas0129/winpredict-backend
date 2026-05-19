from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def internal_key_on(monkeypatch):
    import app.core.config as cfg

    monkeypatch.setattr(cfg.settings, "INTERNAL_API_KEY", "clave-interna-test-exacta", raising=False)
    monkeypatch.setattr(cfg.settings, "DEBUG", False, raising=False)
    yield
    monkeypatch.setattr(cfg.settings, "INTERNAL_API_KEY", "", raising=False)


def test_calcular_puntos_rechaza_sin_header(client: TestClient, internal_key_on):
    pid = str(uuid.uuid4())
    r = client.post(f"/api/pronosticos/calcular-puntos/{pid}")
    assert r.status_code == 401


def test_calcular_puntos_rechaza_clave_incorrecta(client: TestClient, internal_key_on):
    pid = str(uuid.uuid4())
    r = client.post(
        f"/api/pronosticos/calcular-puntos/{pid}",
        headers={"X-Internal-Key": "mala-clave"},
    )
    assert r.status_code == 401


def test_calcular_puntos_acepta_clave_correcta(client: TestClient, internal_key_on):
    pid = str(uuid.uuid4())
    r = client.post(
        f"/api/pronosticos/calcular-puntos/{pid}",
        headers={"X-Internal-Key": "clave-interna-test-exacta"},
    )
    assert r.status_code == 404
    assert "no encontrado" in r.json().get("detail", "").lower()
