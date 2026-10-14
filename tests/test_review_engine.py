import datetime


def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    from app import db

    db.init_db()
    return db.connect()


def _get(con, pid):
    r = con.execute("SELECT * FROM reviews WHERE point_id = ?", (pid,)).fetchone()
    return dict(r) if r else None


def test_review_rule_matrix(tmp_path, monkeypatch):
    from app.services import review_engine as re

    con = _db(tmp_path, monkeypatch)
    t = "2026-10-14"

    # schedule：stage0, +1 天
    re.schedule(con, "p1", t)
    assert _get(con, "p1")["stage"] == 0
    assert _get(con, "p1")["due_date"] == "2026-10-15"

    # advance：0→1(+7) / 1→2(+15) / 2→毕业删除
    re.advance(con, "p1", "2026-10-15")
    assert _get(con, "p1")["stage"] == 1
    assert _get(con, "p1")["due_date"] == "2026-10-22"
    re.advance(con, "p1", "2026-10-22")
    assert _get(con, "p1")["due_date"] == "2026-11-06"
    re.advance(con, "p1", "2026-11-06")
    assert _get(con, "p1") is None

    # on_state_change：half 重置 / known 有记录推进 / known 无记录建档 / new 删除
    re.on_state_change(con, "p2", "half", t)
    assert _get(con, "p2")["due_date"] == "2026-10-15"
    re.on_state_change(con, "p2", "known", t)
    assert _get(con, "p2")["stage"] == 1
    re.on_state_change(con, "p3", "known", t)
    assert _get(con, "p3")["stage"] == 1
    assert _get(con, "p3")["due_date"] == "2026-10-17"

    # due_points 边界（p2 已 advance 到 due=10-21；p3 due=10-17）
    assert "p2" not in re.due_points(con, "2026-10-20")
    assert "p2" in re.due_points(con, "2026-10-21")
    assert "p3" in re.due_points(con, "2026-10-17")

    re.on_state_change(con, "p2", "new", t)
    assert _get(con, "p2") is None


def test_progress_hook_schedules_review(client):
    """状态变更端点挂钩：标 half → reviews 建档；标 known（首次）→ +3 天；标 new → 清除。"""
    from app import db

    client.post("/api/login", json={"password": "pw"})
    client.post("/api/progress", json={"point_id": "812-04-01", "state": "half"})
    con = db.connect()
    row = con.execute("SELECT * FROM reviews WHERE point_id = '812-04-01'").fetchone()
    assert row is not None and row["stage"] == 0
    client.post("/api/progress", json={"point_id": "812-04-01", "state": "known"})
    row = con.execute("SELECT * FROM reviews WHERE point_id = '812-04-01'").fetchone()
    assert row["stage"] == 1
    client.post("/api/progress", json={"point_id": "812-04-01", "state": "new"})
    assert con.execute("SELECT * FROM reviews WHERE point_id = '812-04-01'").fetchone() is None
    con.close()


def test_reviews_api_due_and_advance(client):
    """GET /api/reviews/due 返回到期项；POST advance 推进并标记 known。"""
    import datetime as dt

    from app import db

    client.post("/api/login", json={"password": "pw"})
    today = dt.date.today().isoformat()
    con = db.connect()
    con.execute("INSERT INTO reviews(point_id, stage, due_date, updated_at) VALUES('812-04-01',0,?,?)",
                (today, today))
    con.commit()
    con.close()
    items = client.get("/api/reviews/due").json()["items"]
    assert items and items[0]["point_id"] == "812-04-01"
    assert client.post("/api/reviews/812-04-01/advance").status_code == 200
    assert client.get("/api/progress").json()["states"]["812-04-01"] == "known"
    assert client.get("/api/reviews/due").json()["items"] == []      # 已推进（due+7）
    con = db.connect()
    row = con.execute("SELECT stage FROM reviews WHERE point_id='812-04-01'").fetchone()
    assert row["stage"] == 1
    con.close()


def test_wrong_attempt_schedules_review(tmp_path, monkeypatch):
    """答错 → 关联考点进入复习（stage0）。"""
    import json
    import pathlib

    fixture = json.loads((pathlib.Path(__file__).parent / "fixtures" / "content_small.json").read_text())
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("KY_DATA_DIR", str(tmp_path))
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "content.json").write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
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

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        wrong = (1 + 1) % 4  # q8120101 answer=3 → 选 2 为错
        c.post("/api/quiz/attempt", json={"quiz_id": "q8120101", "chosen": wrong})
        from app import db

        con = db.connect()
        row = con.execute("SELECT * FROM reviews WHERE point_id = '812-01-01'").fetchone()
        assert row is not None and row["stage"] == 0
        con.close()
    get_settings.cache_clear()
    content_mod.reset_cache()
