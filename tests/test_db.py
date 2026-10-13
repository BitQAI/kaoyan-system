TABLES = {"progress", "audio_pos", "quiz_attempts", "wrong_book", "favorites",
          "ai_threads", "ai_messages", "daily_log", "settings"}


def test_init_db_creates_tables(tmp_path, monkeypatch):
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    from app import db

    db.init_db()
    con = db.connect()
    names = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert TABLES <= names
    con.close()
    get_settings.cache_clear()


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}
