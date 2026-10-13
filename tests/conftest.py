import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("KY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("KY_CONTENT_DIR", str(tmp_path / "content"))
    from app import auth

    monkeypatch.setenv("KY_PASSWORD_HASH", auth.hash_password("pw"))
    monkeypatch.setenv("KY_SESSION_SECRET", "s")
    from app.config import get_settings

    get_settings.cache_clear()
    from app import content as content_mod

    content_mod.reset_cache()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()
    content_mod.reset_cache()


@pytest.fixture
def ac(client):
    """已登录客户端。"""
    r = client.post("/api/login", json={"password": "pw"})
    assert r.status_code == 200
    return client
