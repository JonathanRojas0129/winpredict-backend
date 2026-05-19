from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.core.security import tiene_pro_vigente


def test_tiene_pro_sin_bandera_es_pro():
    u = SimpleNamespace(es_pro=False, pro_expira_en=None)
    assert tiene_pro_vigente(u) is False


def test_tiene_pro_activo_sin_fecha_expiracion():
    u = SimpleNamespace(es_pro=True, pro_expira_en=None)
    assert tiene_pro_vigente(u) is True


def test_tiene_pro_activo_fecha_futura():
    futuro = datetime.now(timezone.utc) + timedelta(days=30)
    u = SimpleNamespace(es_pro=True, pro_expira_en=futuro)
    assert tiene_pro_vigente(u) is True


def test_tiene_pro_expirado():
    pasado = datetime.now(timezone.utc) - timedelta(days=1)
    u = SimpleNamespace(es_pro=True, pro_expira_en=pasado)
    assert tiene_pro_vigente(u) is False


def test_tiene_pro_fecha_naive_se_trata_como_utc():
    pasado = datetime.utcnow() - timedelta(days=1)
    u = SimpleNamespace(es_pro=True, pro_expira_en=pasado)
    assert tiene_pro_vigente(u) is False
