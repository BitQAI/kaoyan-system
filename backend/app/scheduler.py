"""卡片间隔调度（纯函数，零 IO，可单测）。

三档评分沿用原型：秒答 / 吃力 / 忘了。
- 秒答：stage+1，间隔按难度膨胀
- 吃力：间隔折半，stage 不动
- 忘了：stage 归零，次日重来，lapses+1
"""
from datetime import date, timedelta

GOOD, FUZZY, BAD = "秒答", "吃力", "忘了"
RESULTS = (GOOD, FUZZY, BAD)
MAX_INTERVAL = 120


def initial_difficulty(card_type: str = "", stored: int | None = None) -> int:
    """difficulty 缺失时按卡片类型估：定义/记忆 −1，综合/论述 +1，夹在 1–3。"""
    if stored:
        return max(1, min(3, int(stored)))
    if any(k in (card_type or "") for k in ("定义", "记忆")):
        return 1
    if any(k in (card_type or "") for k in ("辨析", "易错", "应用")):
        return 3
    return 2


def next_state(stage: int, interval: int, lapses: int, reviews: int,
               result: str, difficulty: int, today: date | None = None) -> dict:
    today = today or date.today()
    if result not in RESULTS:
        raise ValueError(f"未知评分：{result}")
    if result == GOOD:
        stage += 1
        interval = 1 if stage <= 1 else round(max(interval, 1) * (1.6 + 0.3 * difficulty))
    elif result == FUZZY:
        interval = max(1, max(interval, 2) // 2)
    else:
        stage = 0
        lapses += 1
        interval = 1
    interval = max(1, min(interval, MAX_INTERVAL))
    return {
        "stage": stage,
        "interval": interval,
        "lapses": lapses,
        "reviews": reviews + 1,
        "last_result": result,
        "due_at": (today + timedelta(days=interval)).isoformat(),
    }
