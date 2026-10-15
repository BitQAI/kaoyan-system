"""单元级复习调度引擎：三档评分 / 考前缩放 / 队列生成（V3 Spec §3.2）。

测试先行：本文件在 unit_review_engine 实现前编写。
"""
import json

T = "2026-10-15"          # 距考试 65 天（正常期）
INS_U = "INSERT INTO unit_reviews(point_id, idx, stage, due_date, updated_at) VALUES(?,?,?,?,?)"

CONTENT = {"subjects": [
    {"id": "A", "name": "科目A", "chapters": [
        {"id": "A-1", "name": "章一", "points": [
            {"id": "A-1-01", "units": ["u1", "u2", "u3"]},
            {"id": "A-1-02", "units": ["x1"]},
        ]},
    ]},
    {"id": "B", "name": "科目B", "chapters": [
        {"id": "B-1", "name": "章一", "points": [{"id": "B-1-01", "units": ["y1", "y2"]}]},
    ]},
]}


def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    from app import db

    db.init_db()
    return db.connect()


def _write_content(tmp_path):
    d = tmp_path / "content"
    d.mkdir(exist_ok=True)
    (d / "content.json").write_text(json.dumps(CONTENT, ensure_ascii=False), encoding="utf-8")


# ---------- 间隔规则与缩放 ----------

def test_next_intervals_matrix():
    from app.services import unit_review_engine as e

    assert e.next_intervals(0, 65) == {"again": 1, "hard": 3, "good": 3, "graduates": False}
    assert e.next_intervals(1, 65) == {"again": 1, "hard": 3, "good": 7, "graduates": False}
    assert e.next_intervals(2, 65) == {"again": 1, "hard": 3, "good": None, "graduates": True}

    assert e.next_intervals(0, 22)["good"] == 3          # 正常期最后一天
    assert e.next_intervals(1, 21) == {"again": 1, "hard": 3, "good": 3, "graduates": False}
    assert e.next_intervals(2, 21) == {"again": 1, "hard": 3, "good": 3, "graduates": False}
    assert e.next_intervals(1, 8)["good"] == 3           # ≤21：上限 3
    assert e.next_intervals(0, 7) == {"again": 1, "hard": 1, "good": 1, "graduates": False}
    assert e.next_intervals(2, 0) == {"again": 1, "hard": 1, "good": 1, "graduates": False}


def test_rate_transitions(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    r = e.rate(con, "A-1-01", 0, "again", today=T, days_left=65)
    assert (r["stage"], r["due_date"], r["graduates"]) == (0, "2026-10-16", False)

    r = e.rate(con, "A-1-01", 0, "good", today=T, days_left=65)
    assert (r["stage"], r["due_date"]) == (1, "2026-10-18")     # 0→1 +3

    r = e.rate(con, "A-1-01", 0, "hard", today=T, days_left=65)
    assert (r["stage"], r["due_date"]) == (1, "2026-10-18")     # stage 不变 +3

    r = e.rate(con, "A-1-01", 0, "good", today=T, days_left=65)
    assert (r["stage"], r["due_date"]) == (2, "2026-10-22")     # 1→2 +7

    r = e.rate(con, "A-1-01", 0, "good", today=T, days_left=65)
    assert r["stage"] == 3 and r["graduates"] is True           # 毕业：行保留
    row = con.execute("SELECT stage FROM unit_reviews WHERE point_id='A-1-01' AND idx=0").fetchone()
    assert row["stage"] == 3

    r = e.rate(con, "A-1-01", 0, "again", today=T, days_left=65)
    assert (r["stage"], r["due_date"]) == (0, "2026-10-16")     # 忘了可复活


def test_rate_frozen_never_graduates(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    e.rate(con, "A-1-01", 0, "good", today=T, days_left=14)
    e.rate(con, "A-1-01", 0, "good", today=T, days_left=14)
    r = e.rate(con, "A-1-01", 0, "good", today=T, days_left=14)   # 冻结：停在 2
    assert r["stage"] == 2 and r["graduates"] is False
    assert r["due_date"] == "2026-10-18"                          # +3 天（压缩）


# ---------- 队列生成 ----------

def test_queue_due_units_interleaved(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    con.execute(INS_U, ("A-1-01", 0, 0, "2026-10-14", T))         # A 过期 stage0
    con.execute(INS_U, ("A-1-01", 1, 1, T, T))                    # A 到期 stage1
    con.execute(INS_U, ("B-1-01", 0, 0, T, T))                    # B 到期 stage0
    con.execute(INS_U, ("B-1-01", 1, 2, "2026-11-01", T))         # 未到期
    con.commit()
    from app.services import unit_review_engine as e

    q = e.queue(con, CONTENT, review_n=60, today=T, days_left=65)
    assert [(i["point_id"], i["idx"]) for i in q["items"]] == \
        [("A-1-01", 0), ("B-1-01", 0), ("A-1-01", 1)]             # 科目轮转 A,B,A
    assert q["due_total"] == 3 and q["shown"] == 3
    assert q["items"][0]["next"]["again"] == 1
    assert q["frozen_graduation"] is False


def test_queue_expands_due_point_without_due_units(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    con.execute("INSERT INTO reviews(point_id, stage, due_date, updated_at) VALUES('A-1-01',0,?,?)", (T, T))
    con.commit()
    from app.services import unit_review_engine as e

    q = e.queue(con, CONTENT, review_n=60, today=T, days_left=65)
    assert {(i["point_id"], i["idx"]) for i in q["items"]} == \
        {("A-1-01", 0), ("A-1-01", 1), ("A-1-01", 2)}


def test_queue_due_point_skipped_when_units_due(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    con.execute("INSERT INTO reviews(point_id, stage, due_date, updated_at) VALUES('A-1-01',0,?,?)", (T, T))
    con.execute(INS_U, ("A-1-01", 0, 0, T, T))
    con.commit()
    from app.services import unit_review_engine as e

    q = e.queue(con, CONTENT, review_n=60, today=T, days_left=65)
    assert [(i["point_id"], i["idx"]) for i in q["items"]] == [("A-1-01", 0)]   # 不展开整点


def test_queue_all_graduated_point_skipped(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    con.execute("INSERT INTO reviews(point_id, stage, due_date, updated_at) VALUES('A-1-02',0,?,?)", (T, T))
    con.execute(INS_U, ("A-1-02", 0, 3, T, T))
    con.commit()
    from app.services import unit_review_engine as e

    q = e.queue(con, CONTENT, review_n=60, today=T, days_left=65)
    assert q["items"] == [] and q["due_total"] == 0


def test_queue_cap_keeps_due_total(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    con.execute(INS_U, ("A-1-01", 0, 0, T, T))
    con.execute(INS_U, ("A-1-01", 1, 0, T, T))
    con.execute(INS_U, ("B-1-01", 0, 0, T, T))
    con.commit()
    from app.services import unit_review_engine as e

    q = e.queue(con, CONTENT, review_n=2, today=T, days_left=65)
    assert len(q["items"]) == 2 and q["shown"] == 2 and q["due_total"] == 3


def test_queue_point_mode_not_capped(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    q = e.queue(con, CONTENT, review_n=2, today=T, days_left=65, point_id="A-1-01")
    assert [i["idx"] for i in q["items"]] == [0, 1, 2]
    assert all(i["stage"] == 0 for i in q["items"])


# ---------- API ----------

def test_unit_review_api_links_state(client, tmp_path):
    _write_content(tmp_path)
    client.post("/api/login", json={"password": "pw"})
    r = client.post("/api/unit_review", json={"point_id": "A-1-01", "idx": 0, "rating": "good"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["next"]["again"] == 1

    prog = client.get("/api/progress").json()
    assert prog["unit_states"]["A-1-01#0"] == "known"

    from app import db

    con = db.connect()
    assert con.execute("SELECT stage FROM unit_reviews WHERE point_id='A-1-01' AND idx=0"
                       ).fetchone()["stage"] == 1
    assert con.execute("SELECT COUNT(*) c FROM unit_ratings").fetchone()["c"] == 1
    assert con.execute("SELECT review_n FROM daily_log WHERE date=date('now','localtime')"
                       ).fetchone()["review_n"] == 1
    con.close()


def test_unit_review_api_all_units(client, tmp_path):
    _write_content(tmp_path)
    client.post("/api/login", json={"password": "pw"})
    r = client.post("/api/unit_review", json={"point_id": "A-1-01", "rating": "good", "all": True})
    assert r.status_code == 200
    prog = client.get("/api/progress").json()
    assert prog["unit_states"] == {"A-1-01#0": "known", "A-1-01#1": "known", "A-1-01#2": "known"}
    assert prog["states"]["A-1-01"] == "known"          # 全会 → 考点 known

    from app import db

    con = db.connect()
    assert con.execute("SELECT COUNT(*) c FROM unit_ratings").fetchone()["c"] == 3
    assert con.execute("SELECT review_n FROM daily_log WHERE date=date('now','localtime')"
                       ).fetchone()["review_n"] == 3
    row = con.execute("SELECT stage FROM reviews WHERE point_id='A-1-01'").fetchone()
    assert row is not None and row["stage"] == 1        # 考点链：known 无记录 → +3 天
    con.close()


def test_unit_review_api_validation(client, tmp_path):
    _write_content(tmp_path)
    client.post("/api/login", json={"password": "pw"})
    assert client.post("/api/unit_review", json={"point_id": "NOPE", "idx": 0,
                                                 "rating": "good"}).status_code == 404
    assert client.post("/api/unit_review", json={"point_id": "A-1-01",
                                                 "rating": "good"}).status_code == 422
    assert client.post("/api/unit_review", json={"point_id": "A-1-01", "idx": 9,
                                                 "rating": "good"}).status_code == 422


def test_review_queue_api_shape(client, tmp_path):
    _write_content(tmp_path)
    client.post("/api/login", json={"password": "pw"})
    q = client.get("/api/review/queue").json()
    assert {"items", "due_total", "shown", "days_left", "frozen_graduation"} <= set(q)
    q2 = client.get("/api/review/queue", params={"point": "A-1-01"}).json()
    assert [i["idx"] for i in q2["items"]] == [0, 1, 2]


def test_stats_ratings_7d(client, tmp_path):
    """近 7 日评分分布（我的页记忆统计）。"""
    _write_content(tmp_path)
    client.post("/api/login", json={"password": "pw"})
    client.post("/api/unit_review", json={"point_id": "A-1-01", "idx": 0, "rating": "good"})
    client.post("/api/unit_review", json={"point_id": "A-1-01", "idx": 1, "rating": "again"})
    s = client.get("/api/stats").json()
    assert s["ratings_7d"] == {"again": 1, "hard": 0, "good": 1}


def test_settings_review_n_roundtrip(client, tmp_path):
    _write_content(tmp_path)
    client.post("/api/login", json={"password": "pw"})
    assert client.get("/api/settings").json()["review_n"] == 60
    client.post("/api/settings", json={"review_n": 80})
    assert client.get("/api/settings").json()["review_n"] == 80


def test_settings_review_n_clamped(client, tmp_path):
    """越界值保存后可读取，但队列使用处 clamp 到 10–200。"""
    _write_content(tmp_path)
    client.post("/api/login", json={"password": "pw"})
    client.post("/api/settings", json={"review_n": 9999})
    from app import db, settings_store

    con = db.connect()
    assert settings_store.review_n(con) == 200
    con.close()
    client.post("/api/settings", json={"review_n": 1})
    con = db.connect()
    assert settings_store.review_n(con) == 10
    con.close()
