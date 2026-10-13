def test_token_roundtrip_and_expiry():
    from app import auth

    t = auth.create_token("s3cret", days=90, now=1000)
    assert auth.verify_token(t, "s3cret", now=1000)
    assert auth.verify_token(t, "s3cret", now=1000 + 90 * 86400)       # 未过期边界
    assert not auth.verify_token(t, "s3cret", now=1000 + 90 * 86400 + 1)
    assert not auth.verify_token(t + "x", "s3cret", now=1000)          # 篡改
    assert not auth.verify_token(t, "other-secret", now=1000)          # 错密钥


def test_password_hash_unique_salt():
    from app import auth

    h1, h2 = auth.hash_password("pw"), auth.hash_password("pw")
    assert h1 != h2
    assert auth.verify_password("pw", h1)
    assert not auth.verify_password("bad", h1)
    assert not auth.verify_password("pw", "garbage")


def test_login_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("KY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("KY_CONTENT_DIR", str(tmp_path / "content"))
    from app import auth

    monkeypatch.setenv("KY_PASSWORD_HASH", auth.hash_password("pw"))
    monkeypatch.setenv("KY_SESSION_SECRET", "s3cret")
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        assert c.get("/api/me").status_code == 401
        assert c.post("/api/login", json={"password": "bad"}).status_code == 401
        r = c.post("/api/login", json={"password": "pw"})
        assert r.status_code == 200
        assert "ky_session" in r.cookies
        assert c.get("/api/me").status_code == 200
        assert c.post("/api/logout").status_code == 200
        assert c.get("/api/me").status_code == 401
    get_settings.cache_clear()
