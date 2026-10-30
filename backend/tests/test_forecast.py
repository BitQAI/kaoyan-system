from datetime import date, timedelta

import pytest

from app import forecast

TODAY = date(2026, 10, 30)


def per_day(values: list[int]) -> dict[str, int]:
    """values[0] 是今天，values[1] 是昨天，以此类推。"""
    return {(TODAY - timedelta(days=i)).isoformat(): n for i, n in enumerate(values)}


def test_smoothed_pace_steady():
    pace, trend = forecast.smoothed_pace(per_day([10] * 28), TODAY)
    assert pace == pytest.approx(10, abs=0.01)
    assert trend == "flat"


def test_smoothed_pace_stops_after_seven_empty_days():
    pace, trend = forecast.smoothed_pace(per_day([0] * 7 + [20] * 21), TODAY)
    assert pace == 0
    assert trend == "flat"


def test_smoothed_pace_detects_acceleration():
    pace, trend = forecast.smoothed_pace(per_day([20] * 7 + [0] * 21), TODAY)
    assert pace > 10
    assert trend == "up"


def test_pace_band_has_a_minimum_width():
    low, high = forecast.pace_band(per_day([10] * 14), TODAY, 10)
    assert low == pytest.approx(8)
    assert high == pytest.approx(12)


def card(interval: int, due_in: int, stage: int = 2, difficulty: int = 2,
         lapses: int = 0, reviews: int = 1) -> forecast.CardState:
    return forecast.CardState(interval, TODAY + timedelta(days=due_in),
                              stage, difficulty, lapses, reviews)


def test_project_load_complete_immediately():
    p = forecast.project_load([], done0=100, remaining=0, capacity=30, new_pace=10,
                              today=TODAY, horizon=TODAY + timedelta(days=30))
    assert p.finish == TODAY
    assert p.series == []


def test_project_load_backlog_blocks_new_cards():
    cards = [card(1, 0) for _ in range(50)]
    p = forecast.project_load(cards, done0=50, remaining=100, capacity=30,
                              new_pace=20, today=TODAY,
                              horizon=TODAY + timedelta(days=10))
    assert p.series[0] == (TODAY + timedelta(days=1), 50)
    assert p.finish is None


def test_project_load_never_exceeds_observed_new_pace():
    p = forecast.project_load([], done0=0, remaining=100, capacity=100,
                              new_pace=5, today=TODAY,
                              horizon=TODAY + timedelta(days=30))
    assert p.series[0] == (TODAY + timedelta(days=1), 5)


def test_project_load_handles_fractional_pace():
    p = forecast.project_load([], done0=0, remaining=100, capacity=100,
                              new_pace=0.5, today=TODAY,
                              horizon=TODAY + timedelta(days=4))
    assert p.series[-1] == (TODAY + timedelta(days=4), 2)


def test_project_load_does_not_burst_after_backlog():
    cards = [card(1, 0) for _ in range(200)]
    p = forecast.project_load(cards, done0=200, remaining=500, capacity=20,
                              new_pace=5, today=TODAY,
                              horizon=TODAY + timedelta(days=20))
    prev = 200
    daily = []
    for _, cum in p.series:
        daily.append(cum - prev)
        prev = cum
    assert max(daily) <= 5


def test_project_load_finishes_earlier_with_more_capacity():
    cards = [card(10, 5) for _ in range(20)]
    low = forecast.project_load(cards, 20, 100, capacity=10, new_pace=10,
                                today=TODAY, horizon=TODAY + timedelta(days=365))
    high = forecast.project_load(cards, 20, 100, capacity=40, new_pace=10,
                                 today=TODAY, horizon=TODAY + timedelta(days=365))
    assert low.finish and high.finish and high.finish < low.finish


def test_steady_review_load_uses_interval_reciprocal():
    cards = [card(10, 0), card(50, 0), card(0, 0)]
    assert forecast.steady_review_load(cards) == pytest.approx(1 / 10 + 1 / 50 + 1)


def test_capacity_uses_median_of_active_days():
    assert forecast.capacity_from_actions([0, 10, 20, 30, 0], pace=5, steady=2) == 20


def test_capacity_falls_back_when_no_activity():
    assert forecast.capacity_from_actions([0] * 14, pace=5, steady=2) == 7


EXAM = TODAY + timedelta(days=50)


def test_status_stalled():
    s, text = forecast.status(50, 100, 0, None, None, None, EXAM, 1, True, 10)
    assert s == "stalled" and "近 7 天" in text


def test_status_risk_when_latest_misses_exam():
    s, text = forecast.status(50, 100, 2, TODAY + timedelta(days=40),
                              TODAY + timedelta(days=35),
                              TODAY + timedelta(days=55), EXAM, 1, False, 10)
    assert s == "risk" and "最晚" in text


def test_status_ok_when_latest_has_buffer():
    s, _ = forecast.status(50, 100, 2, TODAY + timedelta(days=40),
                           TODAY + timedelta(days=35),
                           TODAY + timedelta(days=45), EXAM, 1, False, 10)
    assert s == "ok"


def test_status_empty_and_insufficient():
    assert forecast.status(0, 100, 0, None, None, None, EXAM, None, False, 10)[0] == "empty"
    assert forecast.status(5, 100, 2, None, None, None, EXAM, 1, False, 2)[0] == "insufficient"


def test_status_ok_when_all_cards_seen():
    s, text = forecast.status(100, 100, 0, TODAY, None, None, EXAM, 0, False, 10)
    assert s == "ok" and "都" in text


def test_confidence_levels():
    assert forecast.confidence_level(14, 100) == "high"
    assert forecast.confidence_level(7, 30) == "medium"
    assert forecast.confidence_level(6, 29) == "low"


def test_project_load_zero_capacity_never_finishes():
    p = forecast.project_load([], 0, 10, capacity=0, new_pace=5,
                              today=TODAY, horizon=TODAY + timedelta(days=30))
    assert p.finish is None and p.series == []


def test_project_load_horizon_caps_projection():
    p = forecast.project_load([], 0, 1000, capacity=10, new_pace=10,
                              today=TODAY, horizon=TODAY + timedelta(days=5))
    assert p.finish is None and len(p.series) == 5


def test_status_late_when_finish_after_exam():
    s, _ = forecast.status(50, 100, 2, EXAM + timedelta(days=1), None, None,
                           EXAM, 1, False, 10)
    assert s == "late"
