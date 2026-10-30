"""进度统计与预测：记 / 听 双维度。

完成口径：
- 记：卡片至少复习过一次（card_progress 有记录），事件源 card_event。
- 听：卡片至少听完一次（card_listen 有记录），事件源 listen_event。

两个维度都以全部卡片为分母，百分比可直接横向对比。
速度口径固定为「最近 7 天新增 / 7」；不足 7 天时按统计跨度摊平，
避免第一天的集中复习被放大成假速度。
"""
from datetime import date, timedelta
import math

from app import config, forecast
from app.progress_series import linear_series, load_series

PACE_WINDOW = forecast.PACE_DAYS
UNIT = "张"


def _scope_total(conn, sid: str | None) -> int:
    if sid:
        return conn.execute(
            "SELECT COUNT(*) FROM card c JOIN point p ON p.id=c.point_id "
            "WHERE p.subject_id = ?", (sid,)).fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM card").fetchone()[0]


def _completion_first_ts(conn, sid: str | None) -> list[tuple[str, str, int]]:
    """每张已复习卡的首次完成时间。

    优先用 card_event 的首条事件；没有事件的（历史数据）回落到
    card_progress.updated_at，并在返回值里标记 derived=1。
    """
    sub = " AND p.subject_id = ?" if sid else ""
    params = [sid] if sid else []
    rows = conn.execute(f"""
        SELECT cp.card_id,
               MIN(e.ts) AS first_event,
               cp.updated_at AS last_touch
        FROM card_progress cp
        JOIN card c ON c.card_id = cp.card_id
        JOIN point p ON p.id = c.point_id
        LEFT JOIN card_event e ON e.card_id = cp.card_id
        WHERE 1=1{sub}
        GROUP BY cp.card_id, cp.updated_at
    """, params).fetchall()
    out = []
    for r in rows:
        if r["first_event"]:
            out.append((r["card_id"], r["first_event"][:10], 0))
        elif r["last_touch"]:
            out.append((r["card_id"], r["last_touch"][:10], 1))
    return out


def _listen_first_ts(conn, sid: str | None) -> list[tuple[str, str, int]]:
    """每张已听卡的首次完成时间。

    listen_event 上线前的记录只有 card_listen.updated_at（最近一次），
    只能当作首次完成日推算，标记 derived=1。
    """
    sub = " AND p.subject_id = ?" if sid else ""
    params = [sid] if sid else []
    rows = conn.execute(f"""
        SELECT cl.card_id,
               MIN(e.ts) AS first_event,
               cl.updated_at AS last_touch
        FROM card_listen cl
        JOIN card c ON c.card_id = cl.card_id
        JOIN point p ON p.id = c.point_id
        LEFT JOIN listen_event e ON e.card_id = cl.card_id
        WHERE 1=1{sub}
        GROUP BY cl.card_id, cl.updated_at
    """, params).fetchall()
    out = []
    for r in rows:
        if r["first_event"]:
            out.append((r["card_id"], r["first_event"][:10], 0))
        elif r["last_touch"]:
            out.append((r["card_id"], r["last_touch"][:10], 1))
    return out


def _load_cards(conn, sid: str | None, today: date) -> list[forecast.CardState]:
    sub = " AND p.subject_id = ?" if sid else ""
    params = [sid] if sid else []
    rows = conn.execute(f"""
        SELECT cp.interval, cp.due_at, cp.stage, cp.ease, cp.lapses, cp.reviews
        FROM card_progress cp
        JOIN card c ON c.card_id = cp.card_id
        JOIN point p ON p.id = c.point_id
        WHERE 1=1{sub}
    """, params).fetchall()
    out = []
    for r in rows:
        try:
            due = date.fromisoformat((r["due_at"] or "")[:10])
        except ValueError:
            due = today
        out.append(forecast.CardState(
            interval=max(1, r["interval"] or 1), due=due,
            stage=r["stage"] or 0, difficulty=r["ease"] or 2,
            lapses=r["lapses"] or 0, reviews=r["reviews"] or 0))
    return out


def _daily_actions(conn, sid: str | None, today: date, days: int = 14) -> list[int]:
    sub = " AND p.subject_id = ?" if sid else ""
    params: list = [sid] if sid else []
    start = (today - timedelta(days=days - 1)).isoformat()
    rows = conn.execute(f"""
        SELECT substr(e.ts,1,10) AS d, COUNT(*) AS n
        FROM card_event e
        JOIN card c ON c.card_id = e.card_id
        JOIN point p ON p.id = c.point_id
        WHERE e.ts >= ?{sub}
        GROUP BY d
    """, [start, *params]).fetchall()
    by_day = {r["d"]: r["n"] for r in rows}
    return [by_day.get((today - timedelta(days=i)).isoformat(), 0)
            for i in range(days - 1, -1, -1)]


def _event_count(conn, table: str, sid: str | None) -> int:
    sub = " AND p.subject_id = ?" if sid else ""
    params = [sid] if sid else []
    return conn.execute(
        f"SELECT COUNT(*) FROM {table} e JOIN card c ON c.card_id = e.card_id "
        f"JOIN point p ON p.id = c.point_id WHERE 1=1{sub}", params).fetchone()[0]


def _due_today(conn, sid: str | None = None) -> int:
    if sid:
        return conn.execute(
            "SELECT COUNT(*) FROM card_progress cp "
            "JOIN card c ON c.card_id = cp.card_id "
            "JOIN point p ON p.id = c.point_id "
            "WHERE cp.due_at <= ? AND p.subject_id = ?",
            (date.today().isoformat(), sid)).fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM card_progress WHERE due_at <= ?",
                        (date.today().isoformat(),)).fetchone()[0]


def _span(firsts, today: date) -> int:
    if not firsts:
        return 0
    earliest = min(date.fromisoformat(f[1]) for f in firsts)
    return max(1, (today - earliest).days + 1)


def _per_day(firsts: list[tuple[str, str, int]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for _, day, _derived in firsts:
        out[day] = out.get(day, 0) + 1
    return out


def _metrics(total: int, firsts, start: date, today: date, exam: date,
             days_left: int, with_series: bool, *, load=None,
             events: int = 0) -> dict:
    done = len(firsts)
    derived = sum(1 for *_rest, d in firsts if d)
    per_day = _per_day(firsts)
    span = _span(firsts, today)
    pace, trend = forecast.smoothed_pace(per_day, today)
    pace_low, pace_high = forecast.pace_band(per_day, today, pace)
    remaining = max(0, total - done)
    required = (remaining / days_left) if days_left > 0 else None
    confidence = forecast.confidence_level(span, events)
    stalled = pace == 0 and remaining > 0 and done > 0
    can_forecast = done > 0 and span >= 3 and pace > 0 and remaining > 0

    mode = "linear"
    capacity = None
    finish = earliest = latest = None
    series: list[dict] = []

    if load and confidence != "low" and can_forecast:
        cards, actions, steady = load
        cap = forecast.capacity_from_actions(actions, pace, steady)
        cap_low = max(1, int(cap * 0.8))
        cap_high = max(cap_low + 1, math.ceil(cap * 1.2))
        horizon = min(exam + timedelta(days=30), today + timedelta(days=365))
        mid = forecast.project_load(cards, done, remaining, cap, pace, today, horizon)
        fast = forecast.project_load(cards, done, remaining, cap_high, pace, today, horizon)
        slow = forecast.project_load(cards, done, remaining, cap_low, pace, today, horizon)
        mode = "load_aware"
        capacity = {"daily_actions": cap, "review_load": round(steady, 1),
                    "new_pace": round(min(pace, max(0, cap - steady)), 1)}
        finish, earliest, latest = mid.finish, fast.finish, slow.finish
        if with_series:
            series = load_series(per_day, start, today, total, done,
                                 mid, fast, slow, exam)

    if mode == "linear":
        if remaining == 0:
            finish = today
        elif can_forecast:
            finish = today + timedelta(days=round(remaining / pace))
            if pace_high > 0:
                earliest = today + timedelta(days=math.ceil(remaining / pace_high))
            if pace_low > 0:
                latest = today + timedelta(days=math.ceil(remaining / pace_low))
        if with_series:
            series = linear_series(per_day, start, today, total,
                                   pace if can_forecast else 0.0,
                                   pace_low, pace_high,
                                   finish if can_forecast else None, exam)

    status, status_text = forecast.status(
        done, total, pace, finish, earliest, latest, exam, required, stalled, span)
    if mode == "load_aware" and finish is None and not stalled and remaining > 0:
        status, status_text = "late", "按当前复习与新卡节奏，初试前学不完"
    if capacity and capacity["daily_actions"] < capacity["review_load"]:
        status = "risk" if status in {"ok", "risk"} else status
        status_text = "复习已占满，新卡推不动"

    out = {
        "total": total, "done": done,
        "percent": round(done / total * 100, 2) if total else 0,
        "status": status, "status_text": status_text,
        "pace": round(pace, 2), "pace_window": PACE_WINDOW,
        "pace_trend": trend,
        "required_pace": round(required, 2) if required is not None else None,
        "finish_date": finish.isoformat() if finish else None,
        "finish_earliest": earliest.isoformat() if earliest else None,
        "finish_latest": latest.isoformat() if latest else None,
        "mode": mode, "confidence": confidence, "capacity": capacity,
        "derived": derived,
    }
    if with_series:
        out["series"] = series
    return out


def _dimension(label: str, metrics: dict) -> dict:
    derived = metrics.pop("derived")
    return {
        "label": label, "unit": UNIT, **metrics,
        "data_quality": {"derived_cards": derived,
                         "recorded_cards": metrics["done"] - derived},
    }


def timeline(conn, sid: str | None = None, days: int = 21) -> dict:
    """按天的累计完成曲线 + 负载感知预测，记 / 听 两个维度。"""
    today = date.today()
    try:
        exam = date.fromisoformat(config.EXAM_DATE)
    except ValueError:
        exam = today + timedelta(days=60)
    days_left = max(0, (exam - today).days)

    days = max(7, min(int(days or 21), 60))
    start = today - timedelta(days=days - 1)

    memo_firsts = _completion_first_ts(conn, sid)
    listen_firsts = _listen_first_ts(conn, sid)
    all_firsts = [*memo_firsts, *listen_firsts]
    if all_firsts:
        earliest = min(date.fromisoformat(f[1]) for f in all_firsts)
        if earliest > start:
            start = earliest       # 不画没有数据的历史

    total = _scope_total(conn, sid)
    memo_cards = _load_cards(conn, sid, today)
    memo_actions = _daily_actions(conn, sid, today)
    steady = forecast.steady_review_load(memo_cards)

    dimensions = {
        "memo": _dimension("记", _metrics(
            total, memo_firsts, start, today, exam, days_left, True,
            load=(memo_cards, memo_actions, steady),
            events=_event_count(conn, "card_event", sid))),
        "listen": _dimension("听", _metrics(
            total, listen_firsts, start, today, exam, days_left, True,
            events=_event_count(conn, "listen_event", sid))),
    }

    return {
        "today": today.isoformat(), "exam_date": exam.isoformat(), "days_left": days_left,
        "scope": sid or "all", "dimensions": dimensions,
        "review_load": {"due_today": _due_today(conn, sid),
                        "steady_load": round(steady, 1)},
        "subjects": _subjects(conn, start, today, exam, days_left),
        "streak": streak(conn),
        "daily": daily_progress(conn),
        "weekly": weekly(conn),
        "milestones": milestones(conn),
    }


def _subjects(conn, start: date, today: date,
              exam: date, days_left: int) -> list[dict]:
    out = []
    for s0 in conn.execute("SELECT id, name FROM subject ORDER BY sort"):
        st_total = _scope_total(conn, s0["id"])
        row = {"id": s0["id"], "name": s0["name"]}
        for key, firsts_of in (("memo", _completion_first_ts),
                               ("listen", _listen_first_ts)):
            firsts = firsts_of(conn, s0["id"])
            m = _metrics(st_total, firsts, start, today, exam, days_left, False,
                         events=len(firsts))
            m.pop("derived")
            row[key] = m
        out.append(row)
    return out


# ---------- 习惯与成就 ----------

def _active_days(conn) -> set[str]:
    """有过任何学习动作的日期集合（记一次、听一条、读一个点都算）。"""
    days: set[str] = set()
    for sql in (
        "SELECT ts FROM card_event",
        "SELECT updated_at AS ts FROM card_listen",
        "SELECT read_at AS ts FROM point_progress WHERE read_at IS NOT NULL",
    ):
        for r in conn.execute(sql):
            if r[0]:
                days.add(r[0][:10])
    return days


def streak(conn) -> int:
    """连续学习天数：今天没学就往前找昨天，避免「今天还没开始」直接归零。"""
    days = _active_days(conn)
    cur = date.today()
    if cur.isoformat() not in days:
        cur -= timedelta(days=1)
    n = 0
    while cur.isoformat() in days:
        n += 1
        cur -= timedelta(days=1)
    return n


def daily_progress(conn) -> dict:
    today = date.today().isoformat()
    goal = 30
    row = conn.execute("SELECT value FROM settings WHERE key = 'daily_goal'").fetchone()
    if row:
        try:
            goal = max(1, int(row["value"]))
        except (TypeError, ValueError):
            pass
    cards = conn.execute(
        "SELECT COUNT(*) FROM card_event WHERE substr(ts,1,10) = ?", (today,)
    ).fetchone()[0]
    listened = conn.execute(
        "SELECT COUNT(*) FROM listen_event WHERE substr(ts,1,10) = ?", (today,)
    ).fetchone()[0]
    read = conn.execute(
        "SELECT COUNT(*) FROM point_progress WHERE substr(read_at,1,10) = ?", (today,)
    ).fetchone()[0]
    return {"goal": goal, "cards": cards, "listened": listened, "read": read}


def weekly(conn) -> dict:
    """本周 vs 上周的复习张数（周一为一周起点）。"""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    last_monday = monday - timedelta(days=7)
    rows = conn.execute(
        "SELECT substr(ts,1,10) AS d, COUNT(*) AS n FROM card_event GROUP BY d"
    ).fetchall()
    this_week = last_week = 0
    for r in rows:
        try:
            d = date.fromisoformat(r["d"])
        except (TypeError, ValueError):
            continue
        if d >= monday:
            this_week += r["n"]
        elif d >= last_monday:
            last_week += r["n"]
    delta = None
    if last_week > 0:
        delta = round((this_week - last_week) / last_week * 100)
    return {"this_week": this_week, "last_week": last_week, "delta_pct": delta,
            "week_start": monday.isoformat()}


def milestones(conn, limit: int = 8) -> dict:
    """具名成就：累计张数、连续天数、整章读完。全部由数据算出来，不随机生成。"""
    items: list[dict] = []
    graded = conn.execute("SELECT COUNT(*) FROM card_event").fetchone()[0]
    for n in (100, 500, 1000, 2000, 3000):
        if graded >= n:
            items.append({"key": f"graded-{n}", "label": f"累计记满 {n} 张"})
    st = streak(conn)
    for n in (3, 7, 14, 30, 60):
        if st >= n:
            items.append({"key": f"streak-{n}", "label": f"连续学习 {n} 天"})
    for r in conn.execute("""
        SELECT ch.id, ch.name,
               (SELECT COUNT(*) FROM point p WHERE p.chapter_id = ch.id) AS total,
               (SELECT COUNT(*) FROM point_progress pp
                JOIN point p ON p.id = pp.point_id
                WHERE p.chapter_id = ch.id AND pp.read_at IS NOT NULL) AS read_n
        FROM chapter ch
    """).fetchall():
        if r["total"] and r["read_n"] >= r["total"]:
            items.append({"key": f"chapter-{r['id']}", "label": f"{r['name']} 全部读完"})
    next_ms = None
    graded_target = next((n for n in (100, 500, 1000, 2000, 3000) if graded < n), None)
    streak_target = next((n for n in (3, 7, 14, 30, 60) if st < n), None)
    candidates = []
    if graded_target:
        candidates.append({"label": f"累计记满 {graded_target} 张", "current": graded,
                           "target": graded_target, "kind": "cards"})
    if streak_target:
        candidates.append({"label": f"连续学习 {streak_target} 天", "current": st,
                           "target": streak_target, "kind": "streak"})
    if candidates:
        next_ms = min(candidates, key=lambda c: c["current"] / c["target"])
        next_ms["pct"] = round(next_ms["current"] / next_ms["target"] * 100)
    return {"count": len(items), "items": items[-limit:], "next": next_ms}
