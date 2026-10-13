import json
import pathlib

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "content_small.json"


def _login(c):
    from app import auth

    r = c.post("/api/login", json={"password": "pw"})
    assert r.status_code == 200


def _client_with_content(tmp_path, monkeypatch, *extra_env):
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("KY_DATA_DIR", str(tmp_path))
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "content.json").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("KY_CONTENT_DIR", str(content_dir))
    from app import auth

    monkeypatch.setenv("KY_PASSWORD_HASH", auth.hash_password("pw"))
    monkeypatch.setenv("KY_SESSION_SECRET", "s")
    from app.config import get_settings

    get_settings.cache_clear()
    from app import content as content_mod

    content_mod.reset_cache()
    from fastapi.testclient import TestClient

    from app.main import app
    from contextlib import contextmanager

    @contextmanager
    def cm():
        with TestClient(app) as c:
            yield c

    return cm()


def test_content_requires_auth(client):
    assert client.get("/api/content").status_code == 401


def test_content_and_progress_roundtrip(tmp_path, monkeypatch):
    with _client_with_content(tmp_path, monkeypatch) as c:
        _login(c)
        r = c.get("/api/content")
        assert r.status_code == 200
        assert r.json()["version"] == "test-1"
        assert c.get("/api/progress").json()["states"] == {}
        assert c.post("/api/progress", json={"point_id": "812-04-01", "state": "known"}).status_code == 200
        assert c.post("/api/progress", json={"point_id": "812-04-02", "state": "bogus"}).status_code == 422
        data = c.get("/api/progress").json()
        assert data["states"] == {"812-04-01": "known"}
        rep = {r["id"]: r for r in data["reports"]}
        assert rep["812"]["chapters"][1]["completion"] > 0
    from app.config import get_settings

    get_settings.cache_clear()


def test_reset_state_deletes_row(tmp_path, monkeypatch):
    with _client_with_content(tmp_path, monkeypatch) as c:
        _login(c)
        c.post("/api/progress", json={"point_id": "812-01-01", "state": "half"})
        assert c.get("/api/progress").json()["states"] == {"812-01-01": "half"}
        c.post("/api/progress", json={"point_id": "812-01-01", "state": "new"})
        assert c.get("/api/progress").json()["states"] == {}
    from app.config import get_settings

    get_settings.cache_clear()


def test_content_missing_503(tmp_path, monkeypatch):
    with _client_with_content(tmp_path, monkeypatch) as c:
        _login(c)
        (tmp_path / "content" / "content.json").unlink()
        from app import content as content_mod

        content_mod.reset_cache()
        assert c.get("/api/content").status_code == 503
    from app.config import get_settings

    get_settings.cache_clear()
