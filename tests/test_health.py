from __future__ import annotations


def test_health_root(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "app" in data
    assert "version" in data
    assert "status" in data
    assert "online" in str(data["status"]).lower()
