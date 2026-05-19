from __future__ import annotations

import pytest

from tests.helpers import get_partido_abierto_id, register_user


@pytest.mark.integration
def test_pronostico_en_partido_futuro(client, db_available):
    if not db_available:
        pytest.skip("DATABASE_URL no accesible")

    partido_id = get_partido_abierto_id()
    if not partido_id:
        pytest.skip("No hay partidos pendientes con fecha >20 min en la BD")

    user = register_user(client, prefix="pron_user")

    grupo = client.post(
        "/api/grupos/",
        headers=user["headers"],
        json={"nombre": "Pronosticos Test", "max_participantes": 10},
    )
    assert grupo.status_code == 201
    grupo_id = grupo.json()["id"]

    pron = client.post(
        "/api/pronosticos/",
        headers=user["headers"],
        json={
            "partido_id": partido_id,
            "grupo_id": grupo_id,
            "goles_local": 2,
            "goles_visitante": 1,
        },
    )
    assert pron.status_code == 201, pron.text
    body = pron.json()
    assert body["goles_local"] == 2
    assert body["goles_visitante"] == 1
    assert body["grupo_id"] == grupo_id

    lista = client.get(
        f"/api/pronosticos/mis-pronosticos/{grupo_id}",
        headers=user["headers"],
    )
    assert lista.status_code == 200
    assert len(lista.json()) >= 1


@pytest.mark.integration
def test_pronostico_requiere_ser_miembro_del_grupo(client, db_available):
    if not db_available:
        pytest.skip("DATABASE_URL no accesible")

    partido_id = get_partido_abierto_id()
    if not partido_id:
        pytest.skip("No hay partidos pendientes con fecha >20 min en la BD")

    owner = register_user(client, prefix="pron_owner")
    outsider = register_user(client, prefix="pron_out")

    grupo = client.post(
        "/api/grupos/",
        headers=owner["headers"],
        json={"nombre": "Grupo cerrado pron", "max_participantes": 5},
    )
    grupo_id = grupo.json()["id"]

    r = client.post(
        "/api/pronosticos/",
        headers=outsider["headers"],
        json={
            "partido_id": partido_id,
            "grupo_id": grupo_id,
            "goles_local": 1,
            "goles_visitante": 0,
        },
    )
    assert r.status_code == 403
    assert "grupo" in r.json()["detail"].lower()


@pytest.mark.integration
def test_no_duplicar_pronostico_usuario_free(client, db_available):
    if not db_available:
        pytest.skip("DATABASE_URL no accesible")

    partido_id = get_partido_abierto_id()
    if not partido_id:
        pytest.skip("No hay partidos pendientes con fecha >20 min en la BD")

    user = register_user(client, prefix="pron_dup")
    grupo = client.post(
        "/api/grupos/",
        headers=user["headers"],
        json={"nombre": "Dup Pron", "max_participantes": 5},
    )
    grupo_id = grupo.json()["id"]
    payload = {
        "partido_id": partido_id,
        "grupo_id": grupo_id,
        "goles_local": 1,
        "goles_visitante": 1,
    }

    first = client.post("/api/pronosticos/", headers=user["headers"], json=payload)
    assert first.status_code == 201

    second = client.post("/api/pronosticos/", headers=user["headers"], json=payload)
    assert second.status_code == 403
    assert "PRO" in second.json()["detail"] or "pronóstico" in second.json()["detail"].lower()
