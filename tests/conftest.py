import pytest

from shop_agent import db


@pytest.fixture(autouse=True)
def shop_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOP_DB", str(tmp_path / "shop.db"))
    monkeypatch.setenv("SHOP_TODAY", "2026-11-14")


@pytest.fixture
def conn():
    c = db.connect()
    yield c
    c.close()
