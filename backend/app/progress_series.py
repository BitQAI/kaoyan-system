"""把累计完成数与预测结果组装成前端曲线点。"""
from datetime import date, timedelta


def actual_series(per_day: dict[str, int], start: date, today: date,
                  total: int) -> tuple[list[dict], int]:
    series: list[dict] = []
    acc = sum(n for day, n in per_day.items() if date.fromisoformat(day) < start)
    for i in range((today - start).days + 1):
        d = start + timedelta(days=i)
        acc += per_day.get(d.isoformat(), 0)
        series.append({"date": d.isoformat(), "done": acc,
                       "percent": round(acc / total * 100, 2) if total else 0,
                       "actual": True})
    return series, acc


def linear_series(per_day: dict[str, int], start: date, today: date, total: int,
                  pace: float, pace_low: float, pace_high: float,
                  finish: date | None, exam: date) -> list[dict]:
    series, acc = actual_series(per_day, start, today, total)
    proj_end = min(finish or exam, exam)
    if proj_end > today + timedelta(days=180):
        proj_end = today + timedelta(days=180)
    if pace > 0 and total:
        for i in range(1, (proj_end - today).days + 1):
            d = today + timedelta(days=i)
            n = min(acc + round(pace * i), total)
            low = min(acc + round(pace_low * i), total)
            high = min(acc + round(pace_high * i), total)
            series.append({"date": d.isoformat(), "done": n,
                           "percent": round(n / total * 100, 2),
                           "actual": False,
                           "low_pct": round(min(low, high) / total * 100, 2),
                           "high_pct": round(max(low, high) / total * 100, 2)})
    return series


def _value_at(series: list[tuple[date, int]], day: date, done0: int,
              total: int, finished: bool) -> int:
    if not series:
        return total if finished else done0
    if day < series[0][0]:
        return done0
    if day > series[-1][0]:
        return total if finished else series[-1][1]
    lo, hi = 0, len(series) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if series[mid][0] <= day:
            lo = mid
        else:
            hi = mid - 1
    return series[lo][1]


def load_series(per_day: dict[str, int], start: date, today: date, total: int,
                done0: int, mid, fast, slow, exam: date) -> list[dict]:
    series, _ = actual_series(per_day, start, today, total)
    end = min(slow.finish or exam, exam)
    day = today + timedelta(days=1)
    while day <= end:
        n = _value_at(mid.series, day, done0, total, mid.finish is not None)
        lo = _value_at(slow.series, day, done0, total, slow.finish is not None)
        hi = _value_at(fast.series, day, done0, total, fast.finish is not None)
        n = min(n, total)
        series.append({
            "date": day.isoformat(), "done": n,
            "percent": round(n / total * 100, 2) if total else 0,
            "actual": False,
            "low_pct": round(min(lo, hi, total) / total * 100, 2) if total else 0,
            "high_pct": round(min(max(lo, hi), total) / total * 100, 2) if total else 0,
        })
        day += timedelta(days=1)
    return series
