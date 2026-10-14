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


def test_init_db_migrates_old_quiz_attempts_schema(tmp_path, monkeypatch):
    """旧库（chosen NOT NULL、无 response）→ init_db 后：数据保留 + 允许 NULL chosen（多选/填空）。"""
    import sqlite3

    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    con = sqlite3.connect(tmp_path / "t.db")
    con.executescript(
        "CREATE TABLE quiz_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, quiz_id TEXT NOT NULL,"
        " chosen INTEGER NOT NULL, correct INTEGER NOT NULL, ts TEXT NOT NULL);")
    con.execute("INSERT INTO quiz_attempts(quiz_id, chosen, correct, ts) VALUES('q1', 1, 1, 't')")
    con.commit()
    con.close()

    from app import db

    db.init_db()
    con = db.connect()
    assert con.execute("SELECT COUNT(*) c FROM quiz_attempts").fetchone()["c"] == 1   # 旧数据保留
    con.execute("INSERT INTO quiz_attempts(quiz_id, chosen, correct, ts, response) "
                "VALUES('q2', NULL, 0, 't', '[0,2]')")                              # NULL chosen 允许
    con.commit()
    db.init_db()                                                                     # 幂等
    assert con.execute("SELECT COUNT(*) c FROM quiz_attempts").fetchone()["c"] == 2
    con.close()
