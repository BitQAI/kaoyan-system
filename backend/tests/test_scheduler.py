from datetime import date

from app import scheduler


TODAY = date(2026, 10, 28)


def test_good_grows_interval():
    s = scheduler.next_state(0, 0, 0, 0, scheduler.GOOD, 2, TODAY)
    assert s["stage"] == 1 and s["interval"] == 1
    s2 = scheduler.next_state(s["stage"], s["interval"], 0, 1, scheduler.GOOD, 2, TODAY)
    assert s2["interval"] > 1


def test_fuzzy_halves_interval():
    s = scheduler.next_state(3, 20, 0, 5, scheduler.FUZZY, 2, TODAY)
    assert s["interval"] == 10 and s["stage"] == 3


def test_bad_resets_stage():
    s = scheduler.next_state(3, 20, 1, 5, scheduler.BAD, 2, TODAY)
    assert s["stage"] == 0 and s["interval"] == 1 and s["lapses"] == 2
    assert s["due_at"] == "2026-10-29"


def test_interval_capped():
    s = scheduler.next_state(9, 500, 0, 20, scheduler.GOOD, 3, TODAY)
    assert s["interval"] <= scheduler.MAX_INTERVAL


def test_difficulty_defaults():
    assert scheduler.initial_difficulty("定义", None) == 1
    assert scheduler.initial_difficulty("辨析", None) == 3
    assert scheduler.initial_difficulty("原理", None) == 2
    assert scheduler.initial_difficulty("定义", 3) == 3


def test_unknown_result_rejected():
    import pytest
    with pytest.raises(ValueError):
        scheduler.next_state(0, 0, 0, 0, "还行", 2, TODAY)
