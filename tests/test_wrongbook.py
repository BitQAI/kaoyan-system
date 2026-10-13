def test_wrongbook_streak_resolves_after_two_correct():
    from app.services.wrongbook import apply_attempt

    s = apply_attempt(None, False, "t1")
    assert s == {"wrong_count": 1, "streak": 0, "resolved_at": None}
    s = apply_attempt(s, True, "t2")
    assert s["streak"] == 1 and s["resolved_at"] is None
    s = apply_attempt(s, True, "t3")
    assert s["streak"] == 2 and s["resolved_at"] == "t3"
    s = apply_attempt(s, False, "t4")
    assert s["streak"] == 0 and s["resolved_at"] is None and s["wrong_count"] == 2
    assert apply_attempt(None, True, "t5") is None  # 从未错过，不建记录
