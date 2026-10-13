import pathlib

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "content_small.json"


def _boot(tmp_path, monkeypatch):
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("KY_DATA_DIR", str(tmp_path))
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "content.json").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("KY_CONTENT_DIR", str(content_dir))
    env_file = tmp_path / ".env"
    env_file.write_text("KY_PASSWORD_HASH=REPLACED_BY_TEST\n", encoding="utf-8")
    monkeypatch.setenv("KY_ENV_FILE", str(env_file))
    from app import auth

    monkeypatch.setenv("KY_PASSWORD_HASH", auth.hash_password("pw"))
    monkeypatch.setenv("KY_SESSION_SECRET", "s")
    from app.config import get_settings

    get_settings.cache_clear()
    from app import content as content_mod

    content_mod.reset_cache()
    return env_file


def _teardown():
    from app.config import get_settings

    get_settings.cache_clear()


def test_plan_today_and_stats(tmp_path, monkeypatch):
    _boot(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        r = c.get("/api/plan/today").json()
        assert "plan" in r and "pace" in r and "logs_30d" in r
        assert r["plan"]["listen"][0].startswith("812-04")
        s = c.get("/api/stats").json()
        assert s["ring"] and s["ring"][0]["id"] == "812"
        assert "streak_days" in s
    _teardown()


def test_settings_roundtrip(tmp_path, monkeypatch):
    _boot(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        s = c.get("/api/settings").json()
        assert s["listen_minutes"] == 40 and s["quiz_n"] == 15
        c.post("/api/settings", json={"listen_minutes": 25})
        assert c.get("/api/settings").json()["listen_minutes"] == 25
    _teardown()


def test_password_change(tmp_path, monkeypatch):
    _boot(tmp_path, monkeypatch)
    from app import auth

    env_file = pathlib.Path(tmp_path / ".env")
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        assert c.post("/api/settings/password", json={"old": "bad", "new": "newpw123"}).status_code == 401
        assert c.post("/api/settings/password", json={"old": "pw", "new": "newpw123"}).status_code == 200
    # 模拟重启：清除环境变量与缓存后按 .env 重新加载
    monkeypatch.delenv("KY_PASSWORD_HASH")
    from app.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert auth.verify_password("newpw123", s.password_hash)
    get_settings.cache_clear()
