"""进度预测的纯函数：稳健速度、完成日区间、负载推演与状态判定。

零 IO、无全局状态；日期统一到天，便于单测与跨维度复用。
"""
from dataclasses import dataclass
from datetime import date, timedelta
import heapq
import math
import statistics

ALPHA = 0.3
PACE_DAYS = 28
TREND_DAYS = 14
BAND_DAYS = 14
Z80 = 1.28
MIN_HALF_RATIO = 0.2
MAX_INTERVAL = 120
DEFAULT_LAPSE = 0.12
LAPSE_MIN = 0.05
LAPSE_MAX = 0.30


@dataclass(frozen=True)
class CardState:
    interval: int
    due: date
    stage: int
    difficulty: int
    lapses: int
    reviews: int


@dataclass(frozen=True)
class Projection:
    finish: date | None
    series: list[tuple[date, int]]
    review_load: float


def _count(per_day: dict[str, int], day: date) -> int:
    return per_day.get(day.isoformat(), 0)


def smoothed_pace(per_day: dict[str, int], today: date) -> tuple[float, str]:
    """最近 28 天首次完成数的指数平滑，返回 (pace, trend)。

    近 7 天全为 0 视为停滞，直接归零；否则用 α=0.3 的简单指数平滑，
    避免单日突击被 7 天窗口放大成假速度。
    """
    recent = [_count(per_day, today - timedelta(days=i)) for i in range(7)]
    if not any(recent):
        return 0.0, "flat"

    level = 0.0
    values: list[int] = []
    for i in range(PACE_DAYS - 1, -1, -1):
        n = _count(per_day, today - timedelta(days=i))
        level = ALPHA * n + (1 - ALPHA) * level
        values.append(n)

    mean = sum(values[-TREND_DAYS:]) / TREND_DAYS
    if mean <= 0:
        return level, "flat"
    diff = (level - mean) / mean
    if diff > 0.1:
        return level, "up"
    if diff < -0.1:
        return level, "down"
    return level, "flat"


def pace_band(per_day: dict[str, int], today: date, pace: float) -> tuple[float, float]:
    """完成日区间的速度上下界，至少 ±20%，数据越波动越宽。"""
    counts = [_count(per_day, today - timedelta(days=i)) for i in range(BAND_DAYS)]
    mean = sum(counts) / BAND_DAYS
    var = sum((n - mean) ** 2 for n in counts) / BAND_DAYS
    se = (var / BAND_DAYS) ** 0.5
    half = max(1.0, Z80 * se, MIN_HALF_RATIO * pace)
    return max(0.0, pace - half), pace + half


def steady_review_load(cards: list[CardState]) -> float:
    """Anki 口径的稳态每日复习量：每张卡 1 / 间隔。"""
    return sum(1 / max(1, c.interval) for c in cards)


def capacity_from_actions(actions: list[int], pace: float, steady: float) -> int:
    """每日总动作容量：取有记录日的中位数，无记录时按速度 + 复习量兜底。"""
    active = [a for a in actions if a > 0]
    if active:
        return max(1, int(statistics.median(active)))
    return max(1, math.ceil(pace + steady))


def _lapse_probability(cards: list[CardState]) -> float:
    reviews = sum(c.reviews for c in cards if c.reviews > 0)
    if not reviews:
        return DEFAULT_LAPSE
    return min(LAPSE_MAX, max(LAPSE_MIN, sum(c.lapses for c in cards) / reviews))


def project_load(cards: list[CardState], done0: int, remaining: int,
                 capacity: int, new_pace: float, today: date,
                 horizon: date) -> Projection:
    """按「到期优先 + 每日容量」逐日推演新卡完成曲线。

    复习永远优先占用容量；新卡速度同时受观测速度与剩余容量限制。
    遗忘按比例分摊到当天复习的卡上，保持确定性、不做随机抽样。
    """
    if remaining <= 0:
        return Projection(today, [], 0.0)
    days = max(0, (horizon - today).days)
    if days <= 0 or capacity <= 0 or new_pace <= 0:
        return Projection(None, [], 0.0)

    interval = [max(1, c.interval) for c in cards]
    stage = [c.stage for c in cards]
    difficulty = [c.difficulty for c in cards]
    p_lapse = _lapse_probability(cards)

    heap = [(max(0, (c.due - today).days), i) for i, c in enumerate(cards)]
    heapq.heapify(heap)

    series: list[tuple[date, int]] = []
    cum = done0
    rem = remaining
    review_total = 0
    new_budget = 0.0
    daily_cap = max(1, math.ceil(new_pace))
    finish: date | None = None

    for d in range(1, days + 1):
        reviews = 0
        popped: list[int] = []
        while heap and heap[0][0] <= d and reviews < capacity:
            _, i = heapq.heappop(heap)
            popped.append(i)
            reviews += 1
        review_total += reviews

        lapse_n = round(reviews * p_lapse)
        for pos, i in enumerate(popped):
            if pos < lapse_n:
                stage[i] = 0
                interval[i] = 1
                heapq.heappush(heap, (d + 1, i))
            else:
                stage[i] += 1
                if stage[i] <= 1:
                    interval[i] = 1
                else:
                    interval[i] = min(
                        MAX_INTERVAL,
                        round(max(interval[i], 1) * (1.6 + 0.3 * difficulty[i])),
                    )
                heapq.heappush(heap, (d + interval[i], i))

        new_budget += new_pace
        new = min(max(0, capacity - reviews), rem, daily_cap, int(new_budget))
        if new > 0:
            new_budget -= new
            rem -= new
            cum += new
            for _ in range(new):
                idx = len(interval)
                interval.append(1)
                stage.append(0)
                difficulty.append(2)
                heapq.heappush(heap, (d + 1, idx))

        series.append((today + timedelta(days=d), cum))
        if rem <= 0:
            finish = today + timedelta(days=d)
            break

    return Projection(finish, series, review_total / max(1, len(series)))


def confidence_level(span_days: int, events: int) -> str:
    if span_days >= 14 and events >= 100:
        return "high"
    if span_days >= 7 and events >= 30:
        return "medium"
    return "low"


def status(done: int, total: int, pace: float, finish: date | None,
           earliest: date | None, latest: date | None, exam: date,
           required: float | None, stalled: bool, span_days: int) -> tuple[str, str]:
    """预测状态与可行动文案；用最晚完成日做保守判定。"""
    if done == 0:
        return "empty", "还没有学习记录"
    if done >= total:
        return "ok", "所有卡片都已学过一遍"
    if span_days < 3:
        return "insufficient", "学习记录不足 3 天，暂不做预测"
    if stalled or pace <= 0:
        return "stalled", "近 7 天没有新增，先恢复学习节奏"
    if finish is None:
        return "risk", "数据不足"
    if finish > exam:
        return "late", "按当前速度无法在初试前学完"
    if latest is not None and latest > exam:
        return "risk", f"能赶上，但最晚可能晚 {(latest - exam).days} 天"
    if required is not None and required > pace * 1.2:
        return "risk", f"能赶上但余量很薄，每天还差 {math.ceil(required - pace)} 张"
    if (exam - finish).days < 7:
        return "risk", "能赶上，但几乎没有缓冲"
    return "ok", "按当前速度可以在初试前学完"
