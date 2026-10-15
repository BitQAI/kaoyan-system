"""单元级复习调度引擎：三档评分 / 考前缩放 / 队列生成（V3 Spec §3.2）。

测试先行：本文件在 unit_review_engine 实现前编写。
"""
import json

T = "2026-10-15"          # 距考试 65 天（正常期）
INS_U = "INSERT INTO unit_reviews(point_id, idx, stage, due_date, updated_at) VALUES(?,?,?,?,?)"


def _plus(today: str, days: int) -> str:
    import datetime
    return (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()

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

def test_target_k_by_kind_and_tier():
    from app.services import unit_review_engine as e

    assert e.target_k("card", 1) == 6 and e.target_k("card", 3) == 6
    assert e.target_k("unit", 1) == 4
    assert e.target_k("unit", 2) == 2 and e.target_k("unit", 3) == 2
    assert e.target_k("unit", None) == 2


def test_jitter_deterministic_and_bounded():
    from app.services import unit_review_engine as e

    assert e.jitter("A-1-01#0") == e.jitter("A-1-01#0")          # 确定性
    vals = {e.jitter(f"A-1-01#{i}") for i in range(200)}
    assert vals <= set(range(1, 22)) and len(vals) == 21          # 覆盖 [1,21]


def test_next_intervals_follows_exam_anchor():
    from app.services import unit_review_engine as e

    key = "A-1-01#0"
    j = e.jitter(key)                       # 固定值，测试用

    # T1（K=4）：k_remain 3 → 2 → 1，末次落在考前 j 天
    d0 = e.next_intervals(0, 4, 65, key)    # 学习后 stage=0 → good 推 stage=1
    assert d0["graduates"] is False and d0["again"] == 1
    assert d0["good"] == round((65 - j) / (2 ** 3 - 1))
    assert d0["hard"] == max(1, round(d0["good"] / 2))

    # stage=3 时 good 毕业（K=4）
    assert e.next_intervals(3, 4, 65, key)["good"] is None
    assert e.next_intervals(3, 4, 65, key)["graduates"] is True


def test_next_intervals_edges():
    from app.services import unit_review_engine as e

    key = "A-1-01#0"
    j = e.jitter(key)

    # 边界 1（Review Focus #1）：days_left 小于 jitter → 毕业，不崩、不负数
    r = e.next_intervals(1, 4, j - 1, key)
    assert r["good"] is None and r["graduates"] is True

    # 边界 2（Review Focus #4）：stage > k（脏数据）→ 毕业，不产生 2**负数
    assert e.next_intervals(9, 2, 65, key)["graduates"] is True

    # 边界 3：K=2 的单元，学习后 stage=0 → good 只剩 1 次，间隔 = 剩余全额
    assert e.next_intervals(0, 2, 65, key)["good"] == max(1, 65 - j)


def test_rate_transitions(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    k = 4
    j = e.jitter(e.unit_key("A-1-01", 0))

    r = e.rate(con, "A-1-01", 0, "again", k, today=T, days_left=65)
    assert (r["stage"], r["due_date"], r["graduates"]) == (0, "2026-10-16", False)

    # good：stage 0→1，k_remain = 3，间隔 = (65 − j) / 7
    r = e.rate(con, "A-1-01", 0, "good", k, today=T, days_left=65)
    assert r["stage"] == 1 and r["graduates"] is False
    assert r["due_date"] == _plus(T, round((65 - j) / 7))

    # hard：stage 不变，间隔 = 同 stage 下 good 间隔的一半
    r = e.rate(con, "A-1-01", 0, "hard", k, today=T, days_left=65)
    assert r["stage"] == 1
    assert r["due_date"] == _plus(T, max(1, round(round((65 - j) / 7) / 2)))

    e.rate(con, "A-1-01", 0, "good", k, today=T, days_left=65)      # stage 2
    r = e.rate(con, "A-1-01", 0, "good", k, today=T, days_left=65)  # stage 3
    assert r["graduates"] is False
    r = e.rate(con, "A-1-01", 0, "good", k, today=T, days_left=65)  # stage 4 = K
    assert r["graduates"] is True and r["stage"] == 4
    row = con.execute("SELECT stage FROM unit_reviews WHERE point_id='A-1-01' AND idx=0").fetchone()
    assert row["stage"] == 4                                        # 毕业：行保留

    r = e.rate(con, "A-1-01", 0, "again", k, today=T, days_left=65)
    assert (r["stage"], r["due_date"]) == (0, "2026-10-16")         # 忘了可复活


def test_rate_graduates_when_time_runs_out(tmp_path, monkeypatch):
    """剩余天数不足 jitter 时 good 直接毕业（V5 取代旧的「考前冻结」规则）。"""
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    key = e.unit_key("A-1-01", 0)
    j = e.jitter(key)
    r = e.rate(con, "A-1-01", 0, "good", 4, today=T, days_left=j - 1)
    assert r["graduates"] is True and r["stage"] == 4


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
    assert q["items"][0]["k"] == 2                                # 缺省 tier=3 → K=2


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
    assert {"items", "due_total", "shown", "days_left"} <= set(q)
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
    assert client.get("/api/settings").json()["review_n"] == 260
    client.post("/api/settings", json={"review_n": 150})
    assert client.get("/api/settings").json()["review_n"] == 150


def test_settings_review_n_clamped(client, tmp_path):
    """越界值保存后可读取，但队列使用处 clamp 到 100–300。"""
    _write_content(tmp_path)
    client.post("/api/login", json={"password": "pw"})
    client.post("/api/settings", json={"review_n": 9999})
    from app import db, settings_store

    con = db.connect()
    assert settings_store.review_n(con) == 300
    con.close()
    client.post("/api/settings", json={"review_n": 1})
    con = db.connect()
    assert settings_store.review_n(con) == 100
    con.close()


def test_review_n_default_and_clamp(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    from app import settings_store

    assert settings_store.review_n(con) == 260
    settings_store.save(con, {"review_n": 50})
    assert settings_store.review_n(con) == 100
    settings_store.save(con, {"review_n": 999})
    assert settings_store.review_n(con) == 300


def test_legacy_stage3_revives_for_tier1(tmp_path, monkeypatch):
    """V3 遗留 stage=3 行（旧「毕业」语义）在新语义下：第 1 梯队仍出卡，低梯队已毕业。"""
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    con.execute(INS_U, ("A-1-01", 0, 3, T, T))          # 旧语义 = 已毕业
    con.commit()

    def _content(tier):
        return {"subjects": [{"id": "A", "chapters": [
            {"id": "A-1", "tier": tier, "points": [{"id": "A-1-01", "units": ["u1"]}]}]}]}

    t1 = e.queue(con, _content(1), review_n=60, today=T, days_left=65)   # K=4 > 3 → 复活
    assert [i["idx"] for i in t1["items"]] == [0]
    t3 = e.queue(con, _content(3), review_n=60, today=T, days_left=65)   # K=2 ≤ 3 → 仍毕业
    assert t3["items"] == []


def test_tier_maps_unit_vs_card():
    """单元 tier 在考点级、卡片 tier 挂在章级（Review Focus #5）。"""
    from app import content as c

    data = {"subjects": [{"id": "A", "chapters": [
        {"id": "A-1", "tier": 1, "points": [{"id": "A-1-01", "units": ["u"]}],
         "cards": [{"id": "card1", "point_id": "A-1-01"}]},
        {"id": "A-2", "tier": 3, "points": [{"id": "A-2-01", "units": ["v"]}], "cards": []},
    ]}]}
    assert c.point_tier_map(data) == {"A-1-01": 1, "A-2-01": 3}
    assert c.card_tier_map(data) == {"card1": 1}


def test_unit_review_api_returns_dynamic_next(ac, tmp_path):
    """评分排出的到期日按考试日动态算出，而非固定 1/3/7 天。"""
    _write_content(tmp_path)
    from app import content as c, db
    from app.services import plan_engine, unit_review_engine as e

    c.reset_cache()
    dl = plan_engine.days_left()
    j = e.jitter("A-1-01#0")
    r = ac.post("/api/unit_review", json={"point_id": "A-1-01", "idx": 0, "rating": "good"})
    assert r.status_code == 200
    assert set(r.json()["next"]) == {"again", "hard", "good", "graduates"}

    con = db.connect()
    row = con.execute("SELECT stage, due_date FROM unit_reviews "
                      "WHERE point_id='A-1-01' AND idx=0").fetchone()
    con.close()
    # 缺省 tier=3 → K=2：首次评分后只剩 1 次，间隔 = 剩余天数全额
    assert row["stage"] == 1
    assert row["due_date"] == _plus(e._today(None), max(1, dl - j))
