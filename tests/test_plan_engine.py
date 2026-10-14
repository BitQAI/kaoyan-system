import json
import pathlib

from app.services import plan_engine

FIXTURE = json.loads((pathlib.Path(__file__).parent / "fixtures" / "content_small.json").read_text())


def test_listen_priority_first_tier_first():
    p = plan_engine.build_plan(FIXTURE, {}, wrong_ids=set(),
                               cfg={"listen_minutes": 2, "look_n": 2, "quiz_n": 5})
    assert p["listen"][0].startswith("812-04")  # 权重 23 的章节先于权重 6 的
    assert "812-04-02-p2" in p["listen"] or "812-04-02-p1" in p["listen"]


def test_listen_skips_visual_points():
    content = {"subjects": [{"id": "x", "chapters": [{
        "id": "x-01", "weight_center": 10, "points": [
            {"id": "x-01-01", "media": [{"type": "diagram", "src": "m.svg"}],
             "audio": [{"src": "audio/x-01-01.mp3", "dur": 100}], "listen_ok": True},
            {"id": "x-01-02", "media": [], "audio": [{"src": "audio/x-01-02.mp3", "dur": 100}], "listen_ok": True},
        ], "quiz": [], "cards": []}]}]}
    p = plan_engine.build_plan(content, {}, wrong_ids=set(),
                               cfg={"listen_minutes": 5, "look_n": 0, "quiz_n": 0})
    assert p["listen"] == ["x-01-02"]


def test_look_includes_half_and_new_by_weight():
    states = {"812-04-01": "half"}
    p = plan_engine.build_plan(FIXTURE, states, wrong_ids=set(),
                               cfg={"listen_minutes": 0, "look_n": 2, "quiz_n": 0})
    assert p["look"][0] == "812-04-01"          # half 优先复习
    assert len(p["look"]) == 2


def test_listen_prefers_chapter_clips_when_present():
    content = {"subjects": [{"id": "x", "chapters": [{
        "id": "x-01", "weight_center": 10, "points": [
            {"id": "x-01-01", "media": [], "audio": [], "listen_ok": True},
            {"id": "x-01-02", "media": [], "audio": [], "listen_ok": True}],
        "listen": [{"src": "audio/x-01-c1.mp3", "dur": 40, "point_ids": ["x-01-01", "x-01-02"]},
                   {"src": "audio/x-01-c2.mp3", "dur": 30, "point_ids": ["x-01-02"]}],
        "quiz": [], "cards": []}]}]}
    p = plan_engine.build_plan(content, {}, wrong_ids=set(),
                               cfg={"listen_minutes": 5, "look_n": 0, "quiz_n": 0})
    assert p["listen"] == ["x-01-c1", "x-01-c2"]


def test_listen_skips_fully_studied_chapter_clips():
    content = {"subjects": [{"id": "x", "chapters": [{
        "id": "x-01", "weight_center": 10,
        "points": [{"id": "x-01-01", "media": [], "audio": [], "listen_ok": True}],
        "listen": [{"src": "audio/x-01-c1.mp3", "dur": 40, "point_ids": ["x-01-01"]}],
        "quiz": [], "cards": []}]}]}
    p = plan_engine.build_plan(content, {"x-01-01": "known"}, wrong_ids=set(),
                               cfg={"listen_minutes": 5, "look_n": 0, "quiz_n": 0})
    assert p["listen"] == []


def test_due_reviews_come_first_in_look():
    p = plan_engine.build_plan(FIXTURE, {"812-04-01": "half"}, wrong_ids=set(),
                               cfg={"listen_minutes": 0, "look_n": 2, "quiz_n": 0},
                               due_review={"812-04-02"})
    assert p["look"][0] == "812-04-02"
    assert "812-04-01" in p["look"]


def test_pace_counts_remaining_points():
    r = plan_engine.pace(FIXTURE, {"812-04-01": "known"}, days_left=60, done_today=0)
    assert r["remaining_points"] == 3           # 812 共 4 点，1 个 known
    assert abs(r["per_day"] - 3 / 60) < 1e-9
    assert r["behind"] is True                  # 今日 0 < per_day


def test_look_fresh_caps_three_points_per_chapter():
    content = {"subjects": [{"id": "x", "chapters": [
        {"id": "x-01", "weight_center": 20, "points": [
            {"id": f"x-01-{i:02d}", "media": [], "audio": [], "listen_ok": False}
            for i in range(1, 7)], "quiz": [], "cards": []},
        {"id": "x-02", "weight_center": 10, "points": [
            {"id": f"x-02-{i:02d}", "media": [], "audio": [], "listen_ok": False}
            for i in range(1, 4)], "quiz": [], "cards": []},
    ]}]}
    p = plan_engine.build_plan(content, {}, wrong_ids=set(),
                               cfg={"listen_minutes": 0, "look_n": 5, "quiz_n": 0})
    # 高权重章最多 3 个，其余名额让给下一章
    assert sum(1 for x in p["look"] if x.startswith("x-01")) == 3
    assert sum(1 for x in p["look"] if x.startswith("x-02")) == 2
