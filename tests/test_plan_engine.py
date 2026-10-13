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


def test_pace_counts_remaining_points():
    r = plan_engine.pace(FIXTURE, {"812-04-01": "known"}, days_left=60, done_today=0)
    assert r["remaining_points"] == 3           # 812 共 4 点，1 个 known
    assert abs(r["per_day"] - 3 / 60) < 1e-9
    assert r["behind"] is True                  # 今日 0 < per_day
