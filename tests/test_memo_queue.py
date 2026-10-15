"""memo 队列引擎：合并/范围/筛选/新卡（V4 Spec §3.2）。测试先行。"""
import json

T = "2026-10-15"
Y = "2026-10-14"          # 昨天（已到期）
INS_U = "INSERT INTO unit_reviews(point_id, idx, stage, due_date, updated_at) VALUES(?,?,?,?,?)"
INS_C = "INSERT INTO card_reviews(card_id, stage, due_date, updated_at) VALUES(?,?,?,?)"

CONTENT = {"subjects": [
    {"id": "A", "name": "科目A", "chapters": [
        {"id": "A-1", "name": "章一", "tier": 1, "points": [
            {"id": "A-1-01", "units": ["u1", "u2"], "tags": ["易错"]},
            {"id": "A-1-02", "units": ["x1"], "tags": ["基础"]},
        ], "cards": [
            {"id": "cA101", "point_id": "A-1-01", "kind": "名解", "front": "f", "back": "b"},
        ]},
        {"id": "A-2", "name": "章二", "tier": 3, "points": [
            {"id": "A-2-01", "units": ["z1"], "tags": []},
        ], "cards": []},
    ]},
    {"id": "B", "name": "科目B", "chapters": [
        {"id": "B-1", "name": "章一", "tier": 2, "points": [
            {"id": "B-1-01", "units": ["y1"], "tags": ["高频"]},
        ], "cards": [
            {"id": "cB101", "point_id": "B-1-01", "kind": "简答", "front": "f2", "back": "b2"},
        ]},
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


def _keys(q):
    return [(i["kind"], i["point_id"], i.get("idx", i.get("card_id"))) for i in q["items"]]


def test_due_merges_units_and_cards_interleaved(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    con.execute(INS_U, ("A-1-01", 0, 0, Y, T))
    con.execute(INS_C, ("cB101", 0, T, T))
    con.commit()
    from app.services import unit_review_engine as e

    q = e.memo_queue(con, CONTENT, review_n=60, today=T, days_left=65)
    assert _keys(q) == [("unit", "A-1-01", 0), ("card", "B-1-01", "cB101")]
    assert (q["total"], q["units_total"], q["cards_total"], q["est_min"]) == (2, 1, 1, 1)
    assert q["items"][0]["next"]["again"] == 1


def test_due_caps_but_scope_does_not(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    con.execute(INS_U, ("A-1-01", 0, 0, T, T))
    con.execute(INS_U, ("A-1-01", 1, 0, T, T))
    con.commit()
    from app.services import unit_review_engine as e

    q = e.memo_queue(con, CONTENT, review_n=1, today=T, days_left=65)
    assert q["shown"] == 1 and q["total"] == 2

    con.execute("DELETE FROM unit_reviews")
    con.commit()
    q2 = e.memo_queue(con, CONTENT, review_n=1, chapters=["A-1"], today=T, days_left=65)
    assert q2["shown"] == 4 and q2["total"] == 4          # 显式范围不截断


def test_scope_includes_new_units_and_cards(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    q = e.memo_queue(con, CONTENT, review_n=60, chapters=["A-1"], today=T, days_left=65)
    got = {(i["kind"], i["point_id"], i.get("idx", i.get("card_id"))) for i in q["items"]}
    assert got == {("unit", "A-1-01", 0), ("unit", "A-1-01", 1),
                   ("card", "A-1-01", "cA101"), ("unit", "A-1-02", 0)}
    assert all(i["stage"] == 0 for i in q["items"])


def test_scope_by_subject_and_points(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    q = e.memo_queue(con, CONTENT, review_n=60, subjects=["B"], today=T, days_left=65)
    assert {i["point_id"] for i in q["items"]} == {"B-1-01"}

    q2 = e.memo_queue(con, CONTENT, review_n=60, points=["A-1-02"], today=T, days_left=65)
    assert _keys(q2) == [("unit", "A-1-02", 0)]


def test_filter_weak_and_due(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    con.execute(INS_U, ("A-1-01", 0, 1, "2026-11-01", T))   # 已评级 stage1，未到期
    con.execute(INS_U, ("A-1-02", 0, 0, Y, T))              # 已评级 stage0，已到期
    con.commit()
    from app.services import unit_review_engine as e

    weak = e.memo_queue(con, CONTENT, review_n=60, chapters=["A-1"], filter=["weak"],
                        today=T, days_left=65)
    assert _keys(weak) == [("unit", "A-1-02", 0), ("unit", "A-1-01", 0)]   # stage 升序

    due = e.memo_queue(con, CONTENT, review_n=60, chapters=["A-1"], filter=["due"],
                       today=T, days_left=65)
    assert _keys(due) == [("unit", "A-1-02", 0)]            # 未评级不算「到期」


def test_filter_hot(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    q = e.memo_queue(con, CONTENT, review_n=60, subjects=["A", "B"], filter=["hot"],
                     today=T, days_left=65)
    pids = {i["point_id"] for i in q["items"]}
    assert pids == {"A-1-01", "B-1-01"}                     # 易错/高频


def test_quick_fav_and_today_look(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    con.execute("INSERT INTO favorites(type, ref_id, created_at) VALUES('point','A-1-02',?)", (T,))
    con.commit()
    from app.services import unit_review_engine as e

    q = e.memo_queue(con, CONTENT, review_n=60, quick="fav", today=T, days_left=65)
    assert _keys(q) == [("unit", "A-1-02", 0)]

    q2 = e.memo_queue(con, CONTENT, review_n=60, quick="today_look", look_points=["B-1-01"],
                      today=T, days_left=65)
    assert {i["kind"] for i in q2["items"]} == {"unit", "card"}
    assert {i["point_id"] for i in q2["items"]} == {"B-1-01"}


def test_memo_queue_api(client, tmp_path):
    _write_content(tmp_path)
    client.post("/api/login", json={"password": "pw"})
    q = client.get("/api/memo/queue", params={"chapters": "A-1"}).json()
    assert q["total"] == 4 and {"items", "total", "est_min", "shown"} <= set(q)
    client.post("/api/favorite", json={"type": "point", "ref_id": "A-1-02", "action": "add"})
    qf = client.get("/api/memo/queue", params={"quick": "fav"}).json()
    assert [i["point_id"] for i in qf["items"]] == ["A-1-02"]
    assert client.get("/api/memo/queue", params={"quick": "nope"}).status_code == 422


def test_plan_today_counts_cards(client, tmp_path):
    _write_content(tmp_path)
    client.post("/api/login", json={"password": "pw"})
    from app import db

    con = db.connect()
    con.execute(INS_C, ("cA101", 0, Y, Y))
    con.commit()
    con.close()
    t = client.get("/api/plan/today").json()
    assert t["review_cards_due"] == 1 and t["review_units_due"] == 0


# ---------- V5：梯队分档与队列优先级 ----------

def test_queue_sorts_by_tier_first(tmp_path, monkeypatch):
    """高梯队优先于低梯队，即使低梯队更早到期（排序即分配策略）。"""
    con = _db(tmp_path, monkeypatch)
    con.execute(INS_U, ("A-2-01", 0, 0, Y, T))          # tier3，更早到期
    con.execute(INS_U, ("A-1-01", 0, 1, T, T))          # tier1，当天到期
    con.commit()
    from app.services import unit_review_engine as e

    ids = [i["point_id"] for i in
           e.memo_queue(con, CONTENT, review_n=60, today=T, days_left=65)["items"]]
    assert ids.index("A-1-01") < ids.index("A-2-01")


def test_queue_items_expose_tier_and_k(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    con.execute(INS_U, ("A-1-01", 0, 0, T, T))
    con.execute(INS_C, ("cB101", 0, T, T))
    con.commit()
    from app.services import unit_review_engine as e

    got = {(i["kind"], i["tier"], i["k"]) for i in
           e.memo_queue(con, CONTENT, review_n=60, today=T, days_left=65)["items"]}
    assert ("unit", 1, 4) in got        # 第 1 梯队单元 K=4
    assert ("card", 2, 6) in got        # 背题卡恒 K=6，tier 取所属章节


def test_jitter_spreads_same_day_items():
    """同日条目不应全部撞在同一天到期（Review Focus #3）。"""
    from app.services import unit_review_engine as e

    dues = {e.next_intervals(0, 4, 65, e.unit_key(f"A-1-0{i}", 0))["good"]
            for i in range(1, 9)}
    assert len(dues) > 1
