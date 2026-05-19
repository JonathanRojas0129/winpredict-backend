from __future__ import annotations

import pytest

from tests.helpers import register_user


@pytest.mark.integration
def test_crear_grupo_y_listar_mis_grupos(client, db_available):
    if not db_available:
        pytest.skip("DATABASE_URL no accesible")

    owner = register_user(client, prefix="grupo_owner")

    crear = client.post(
        "/api/grupos/",
        headers=owner["headers"],
        json={
            "nombre": "Polla Pytest",
            "max_participantes": 10,
            "descripcion": "Grupo de prueba automatizada",
        },
    )
    assert crear.status_code == 201, crear.text
    grupo = crear.json()
    assert grupo["nombre"] == "Polla Pytest"
    assert grupo["total_participantes"] == 1
    assert len(grupo["codigo_invitacion"]) >= 6
    grupo_id = grupo["id"]

    lista = client.get("/api/grupos/mis-grupos", headers=owner["headers"])
    assert lista.status_code == 200
    ids = [g["id"] for g in lista.json()]
    assert grupo_id in ids

    detalle = client.get(f"/api/grupos/{grupo_id}", headers=owner["headers"])
    assert detalle.status_code == 200
    assert detalle.json()["codigo_invitacion"] == grupo["codigo_invitacion"]


@pytest.mark.integration
def test_unirse_a_grupo_y_ranking(client, db_available):
    if not db_available:
        pytest.skip("DATABASE_URL no accesible")

    owner = register_user(client, prefix="rank_owner")
    guest = register_user(client, prefix="rank_guest")
    outsider = register_user(client, prefix="rank_out")

    crear = client.post(
        "/api/grupos/",
        headers=owner["headers"],
        json={"nombre": "Ranking Test", "max_participantes": 20},
    )
    assert crear.status_code == 201
    grupo_id = crear.json()["id"]
    codigo = crear.json()["codigo_invitacion"]

    unirse = client.post(
        "/api/grupos/unirse",
        headers=guest["headers"],
        json={"codigo_invitacion": codigo},
    )
    assert unirse.status_code == 200
    assert unirse.json()["total_participantes"] == 2

    ranking = client.get(f"/api/ranking/{grupo_id}", headers=guest["headers"])
    assert ranking.status_code == 200
    assert len(ranking.json()) == 2
    assert any(p["es_yo"] for p in ranking.json())

    forbidden = client.get(f"/api/ranking/{grupo_id}", headers=outsider["headers"])
    assert forbidden.status_code == 403


@pytest.mark.integration
def test_no_unirse_dos_veces(client, db_available):
    if not db_available:
        pytest.skip("DATABASE_URL no accesible")

    owner = register_user(client, prefix="dup_owner")
    guest = register_user(client, prefix="dup_guest")

    crear = client.post(
        "/api/grupos/",
        headers=owner["headers"],
        json={"nombre": "Dup Test", "max_participantes": 5},
    )
    codigo = crear.json()["codigo_invitacion"]

    first = client.post(
        "/api/grupos/unirse",
        headers=guest["headers"],
        json={"codigo_invitacion": codigo},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/grupos/unirse",
        headers=guest["headers"],
        json={"codigo_invitacion": codigo},
    )
    assert second.status_code == 400
    assert "miembro" in second.json()["detail"].lower()
