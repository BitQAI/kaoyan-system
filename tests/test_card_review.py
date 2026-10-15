"""背题卡级复习调度（V4 Spec §3.2）：规则与单元一致、与考点状态解耦。

测试先行：本文件在 rate_card 实现前编写。
"""
import json

T = "2026-10-15"          # 距考试 65 天（正常期）

CONTENT = {"subjects": [
    {"id": "A", "name": "科目A", "chapters": [
        {"id": "A-1", "name": "章一", "points": [
            {"id": "A-1-01", "text": "考点一", "units": ["u1", "u2"]},
        ], "cards": [
            {"id": "cA101", "point_id": "A-1-01", "kind": "名解",
             "front": "名词解释：考点一", "back": "答案一"},
            {"id": "cA102", "point_id": "A-1-01", "kind": "简答",
             "front": "简述考点一", "back": "答案二"},
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


def test_rate_card_transitions(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    r = e.rate_card(con, "cA101", "again", today=T, days_left=65)
    assert (r["stage"], r["due_date"], r["graduates"]) == (0, "2026-10-16", False)

    r = e.rate_card(con, "cA101", "good", today=T, days_left=65)
    assert (r["stage"], r["due_date"]) == (1, "2026-10-18")        # 0→1 +3
    r = e.rate_card(con, "cA101", "hard", today=T, days_left=65)
    assert (r["stage"], r["due_date"]) == (1, "2026-10-18")        # stage 不变 +3
    r = e.rate_card(con, "cA101", "good", today=T, days_left=65)
    assert (r["stage"], r["due_date"]) == (2, "2026-10-22")        # 1→2 +7
    r = e.rate_card(con, "cA101", "good", today=T, days_left=65)
    assert r["stage"] == 3 and r["graduates"] is True              # 毕业保留行

    # 只写 card_reviews，不碰单元表
    assert con.execute("SELECT COUNT(*) c FROM unit_reviews").fetchone()["c"] == 0


def test_rate_card_frozen(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    e.rate_card(con, "cA101", "good", today=T, days_left=14)
    e.rate_card(con, "cA101", "good", today=T, days_left=14)
    r = e.rate_card(con, "cA101", "good", today=T, days_left=14)   # 冻结：停在 2
    assert r["stage"] == 2 and r["graduates"] is False
    assert r["due_date"] == "2026-10-18"


def test_card_review_api_decoupled(client, tmp_path):
    """评分落 card_reviews + daily.cards；不改考点/单元状态。"""
    _write_content(tmp_path)
    client.post("/api/login", json={"password": "pw"})
    r = client.post("/api/card_review", json={"card_id": "cA101", "rating": "good"})
    assert r.status_code == 200
    assert r.json()["next"]["again"] == 1

    from app import db

    con = db.connect()
    assert con.execute("SELECT stage FROM card_reviews WHERE card_id='cA101'"
                       ).fetchone()["stage"] == 1
    assert con.execute("SELECT COUNT(*) c FROM progress").fetchone()["c"] == 0
    assert con.execute("SELECT COUNT(*) c FROM unit_progress").fetchone()["c"] == 0
    assert con.execute("SELECT cards FROM daily_log WHERE date=date('now','localtime')"
                       ).fetchone()["cards"] == 1
    con.close()


def test_card_review_api_validation(client, tmp_path):
    _write_content(tmp_path)
    client.post("/api/login", json={"password": "pw"})
    assert client.post("/api/card_review", json={"card_id": "nope",
                                                 "rating": "good"}).status_code == 404
    assert client.post("/api/card_review", json={"card_id": "cA101",
                                                 "rating": "meh"}).status_code == 422
