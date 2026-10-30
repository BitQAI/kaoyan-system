def test_progress_stats_all(client):
    got = client.get("/api/stats/progress").json()
    assert got["points"]["total"] == 538
    assert got["cards"]["total"] == 3171
    assert got["listen"]["total"] == 3171
    assert got["listen"]["heard"] <= got["listen"]["total"]
    assert len(got["chapters"]) == 74


def test_progress_stats_by_subject(client):
    got = client.get("/api/stats/progress", params={"sid": "812"}).json()
    assert got["points"]["total"] == 130
    assert all(c["total"] >= 0 for c in got["chapters"])


def test_custom_cards_scope_by_chapter(client):
    chapters = client.get("/api/subjects/812/chapters").json()["items"]
    cid = chapters[0]["id"]
    got = client.post("/api/queue/custom", json={
        "mode": "memo", "chapters": [cid], "limit": 50}).json()
    assert got["items"]
    assert all(item["chapter_id"] == cid for item in got["items"])


def test_custom_cards_respects_scope_subject(client):
    got = client.post("/api/queue/custom", json={
        "mode": "memo", "subjects": ["204"], "limit": 20}).json()
    assert all(item["subject_id"] == "204" for item in got["items"])


def test_custom_cards_exclude(client):
    first = client.post("/api/queue/custom", json={"mode": "memo", "limit": 5}).json()
    ids = [i["card_id"] for i in first["items"]]
    second = client.post("/api/queue/custom", json={
        "mode": "memo", "limit": 5, "exclude": ids}).json()
    assert not set(ids) & {i["card_id"] for i in second["items"]}


def test_custom_listen_carries_card_id(client):
    got = client.post("/api/queue/custom", json={"mode": "listen", "limit": 3}).json()
    assert got["items"]
    assert got["items"][0]["card_id"], "听学条目要能定位到题目，供按题归档 AI 历史"


def test_grade_updates_stats(client):
    before = client.get("/api/stats/progress").json()["cards"]["seen"]
    queue = client.post("/api/queue/custom", json={"mode": "memo", "limit": 1}).json()
    card_id = queue["items"][0]["card_id"]
    client.post("/api/progress/card", json={"card_id": card_id, "result": "秒答"})
    after = client.get("/api/stats/progress").json()["cards"]["seen"]
    assert after == before + 1


def test_today_summary(client):
    got = client.get("/api/stats/today").json()
    assert "date" in got and "cards_seen" in got


def test_listen_queue_is_card_level(client):
    got = client.post("/api/queue/custom", json={"mode": "listen", "limit": 3}).json()
    item = got["items"][0]
    assert {"card_id", "question", "analysis", "title"} <= set(item)
    assert "options" not in item, "听不读选项"


def test_mark_listened_by_card(client, conn):
    item = client.post("/api/queue/custom", json={"mode": "listen", "limit": 1}).json()["items"][0]
    res = client.post("/api/progress/listen", json={"card_id": item["card_id"]})
    assert res.status_code == 200
    row = conn.execute("SELECT listen_count FROM card_listen WHERE card_id = ?",
                       (item["card_id"],)).fetchone()
    assert row is not None and row["listen_count"] == 1


def test_forecast_covers_four_subjects(client):
    got = client.get("/api/stats/forecast").json()
    assert len(got["subjects"]) == 4
    assert got["exam_date"]
    for s in got["subjects"]:
        assert s["total"] > 0 and s["remaining"] == s["total"] - s["seen"]
        assert "pace" in s and "eta" in s


def test_timeline_shape(client):
    got = client.get("/api/stats/timeline").json()
    assert set(got["dimensions"]) == {"memo", "listen"}
    memo = got["dimensions"]["memo"]
    assert memo["label"] == "记" and memo["total"] == 3171
    assert memo["series"] and memo["series"][0]["actual"] is True
    assert {"total", "done", "percent", "pace", "status", "status_text"} <= set(memo)
    listen = got["dimensions"]["listen"]
    assert listen["label"] == "听" and listen["total"] == 3171
    assert listen["series"] and listen["series"][0]["actual"] is True
    assert got["exam_date"] and got["days_left"] >= 0
    assert len(got["subjects"]) == 4
    assert {"id", "name", "memo", "listen"} <= set(got["subjects"][0])
    # 预测点只能出现在今天之后
    today = got["today"]
    for dim in got["dimensions"].values():
        assert all(p["date"] >= today for p in dim["series"] if not p["actual"])


def test_timeline_marks_derived_data(client):
    got = client.get("/api/stats/timeline").json()
    for dim in got["dimensions"].values():
        q = dim["data_quality"]
        assert q["recorded_cards"] + q["derived_cards"] == dim["done"]


def test_timeline_listen_matches_listen_records(client, conn):
    got = client.get("/api/stats/timeline").json()
    assert got["dimensions"]["listen"]["done"] == conn.execute(
        "SELECT COUNT(*) FROM card_listen").fetchone()[0]
    assert got["dimensions"]["memo"]["done"] == conn.execute(
        "SELECT COUNT(*) FROM card_progress").fetchone()[0]


def test_listen_event_recorded_on_mark(conn):
    from app import service
    service.mark_card_listened(conn, "c8120001-1")
    rows = conn.execute("SELECT COUNT(*) FROM listen_event WHERE card_id = ?",
                        ("c8120001-1",)).fetchone()[0]
    assert rows >= 1


def test_progress_stats_listen_counts_cards(client, conn):
    got = client.get("/api/stats/progress").json()
    assert got["listen"]["total"] == got["cards"]["total"] == 3171
    assert got["listen"]["heard"] == conn.execute(
        "SELECT COUNT(*) FROM card_listen").fetchone()[0]


def test_timeline_records_events(client, conn):
    item = client.post("/api/queue/custom", json={"mode": "memo", "limit": 1}).json()["items"][0]
    client.post("/api/progress/card", json={"card_id": item["card_id"], "result": "忘了"})
    rows = conn.execute("SELECT result FROM card_event WHERE card_id = ?",
                        (item["card_id"],)).fetchall()
    assert rows and rows[-1]["result"] == "忘了"


def test_timeline_insufficient_on_first_day(client):
    got = client.get("/api/stats/timeline").json()["dimensions"]["memo"]
    if got["done"] > 0 and got["total"] > 0:
        assert got["status"] in {"insufficient", "late", "risk", "ok", "empty"}


def test_timeline_has_streak_and_daily(client):
    got = client.get("/api/stats/timeline").json()
    assert isinstance(got["streak"], int) and got["streak"] >= 0
    d = got["daily"]
    assert {"goal", "cards", "listened", "read"} <= set(d)
    assert d["goal"] >= 1


def test_streak_counts_today(conn):
    from app import progress
    conn.execute("INSERT INTO card_event (card_id, ts, result) VALUES (?,?,?)",
                 ("c8120001-1", __import__("datetime").datetime.now().isoformat(timespec="seconds"), "秒答"))
    conn.commit()
    assert progress.streak(conn) >= 1


def test_weekly_comparison(client):
    got = client.get("/api/stats/timeline").json()["weekly"]
    assert got["this_week"] >= 0 and got["last_week"] >= 0
    assert "week_start" in got
    if got["last_week"] == 0:
        assert got["delta_pct"] is None


def test_milestones_shape(client):
    got = client.get("/api/stats/timeline").json()["milestones"]
    assert isinstance(got["items"], list)
    assert got["count"] >= len(got["items"])
    if got["next"]:
        assert got["next"]["current"] < got["next"]["target"]
        assert 0 <= got["next"]["pct"] <= 100


def test_timeline_forecast_fields(client):
    got = client.get("/api/stats/timeline").json()
    for key in ("memo", "listen"):
        dim = got["dimensions"][key]
        assert {"pace_trend", "finish_earliest", "finish_latest", "mode",
                "confidence", "capacity"} <= set(dim)
        assert dim["mode"] in {"load_aware", "linear"}
        assert dim["confidence"] in {"high", "medium", "low"}
    assert got["dimensions"]["listen"]["mode"] == "linear"
    assert got["dimensions"]["listen"]["capacity"] is None


def test_timeline_series_band_shape(client):
    got = client.get("/api/stats/timeline").json()
    for dim in got["dimensions"].values():
        actual = [p for p in dim["series"] if p["actual"]]
        forecast = [p for p in dim["series"] if not p["actual"]]
        assert all("low_pct" not in p for p in actual)
        assert all(p["low_pct"] <= p["high_pct"] for p in forecast)
        assert all(p["percent"] <= 100 for p in dim["series"])


def test_timeline_review_load_shape(client):
    got = client.get("/api/stats/timeline").json()
    assert {"due_today", "steady_load"} <= set(got["review_load"])
    assert got["review_load"]["due_today"] >= 0
    assert got["review_load"]["steady_load"] >= 0


def test_timeline_insufficient_has_no_forecast(client):
    dim = client.get("/api/stats/timeline").json()["dimensions"]["memo"]
    if dim["status"] == "insufficient":
        assert dim["finish_date"] is None
        assert not [p for p in dim["series"] if not p["actual"]]


def test_timeline_keeps_legacy_fields(client):
    dim = client.get("/api/stats/timeline").json()["dimensions"]["memo"]
    assert {"total", "done", "percent", "pace", "pace_window", "required_pace",
            "finish_date", "status", "status_text", "series"} <= set(dim)


def test_subjects_have_forecast_fields(client):
    got = client.get("/api/stats/timeline").json()
    for s in got["subjects"]:
        for key in ("memo", "listen"):
            assert {"finish_earliest", "finish_latest", "mode", "confidence"} <= set(s[key])


def test_load_series_extends_to_pessimistic_finish():
    from datetime import date, timedelta
    from app.forecast import Projection
    from app.progress_series import load_series

    today = date(2026, 10, 30)
    mid = Projection(today + timedelta(days=10), [], 0)
    fast = Projection(today + timedelta(days=8), [], 0)
    slow = Projection(today + timedelta(days=15), [], 0)
    series = load_series({}, today, today, 100, 0, mid, fast, slow,
                         today + timedelta(days=20))
    forecast = [p for p in series if not p["actual"]]
    assert forecast[0]["date"] == (today + timedelta(days=1)).isoformat()
    assert forecast[-1]["date"] == (today + timedelta(days=15)).isoformat()
