"""错题本状态机：错 → 入本；连对 2 次 → 出本；再错 → 重新入本。"""


def apply_attempt(state: dict | None, correct: bool, now: str) -> dict | None:
    if not correct:
        prev = state or {}
        return {"wrong_count": prev.get("wrong_count", 0) + 1, "streak": 0, "resolved_at": None}
    if state is None:
        return None
    streak = state.get("streak", 0) + 1
    return {
        "wrong_count": state.get("wrong_count", 1),
        "streak": streak,
        "resolved_at": now if streak >= 2 else None,
    }
