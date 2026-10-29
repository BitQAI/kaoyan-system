"""进度统计与预测：记 / 听 双维度。

完成口径：
- 记：卡片至少复习过一次（card_progress 有记录），事件源 card_event。
- 听：卡片至少听完一次（card_listen 有记录），事件源 listen_event。

两个维度都以全部卡片为分母，百分比可直接横向对比。
速度口径固定为「最近 7 天新增 / 7」；不足 7 天时按统计跨度摊平，
避免第一天的集中复习被放大成假速度。
"""
from datetime import date, timedelta

from app import config

WINDOW = 7
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


def _status(done: int, total: int, finish: date | None, exam: date, pace: float,
            required: float | None) -> tuple[str, str]:
    if done == 0:
        return "empty", "还没有学习记录"
    if pace <= 0:
        return "empty", "近期没有复习，无法预测"
    if finish is None:
        return "risk", "数据不足"
    if finish > exam:
        return "late", "按当前速度无法在初试前学完"
    if required and pace > 0 and required > pace * 1.2:
        return "risk", "能赶上但余量很薄，需要提速"
    if (exam - finish).days < 7:
        return "risk", "能赶上，但几乎没有缓冲"
    return "ok", "按当前速度可以在初试前学完"


def _per_day(firsts: list[tuple[str, str, int]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for _, day, _derived in firsts:
        out[day] = out.get(day, 0) + 1
    return out


def _series(per_day: dict[str, int], start: date, today: date, total: int,
            pace: float, finish: date | None, exam: date) -> list[dict]:
    series: list[dict] = []
    acc = sum(n for day, n in per_day.items() if date.fromisoformat(day) < start)
    for i in range((today - start).days + 1):
        d = start + timedelta(days=i)
        acc += per_day.get(d.isoformat(), 0)
        series.append({"date": d.isoformat(), "done": acc,
                       "percent": round(acc / total * 100, 2) if total else 0,
                       "actual": True})

    # 预测段画到初试当天为止：曲线在 100% 之前停止 = 赶不上，一眼能看出来
    proj_end = min(finish or exam, exam)
    if proj_end > today + timedelta(days=180):
        proj_end = today + timedelta(days=180)
    if pace > 0 and total:
        for i in range(1, (proj_end - today).days + 1):
            d = today + timedelta(days=i)
            n = acc + round(pace * i)
            series.append({"date": d.isoformat(), "done": n,
                           "percent": round(min(n, total) / total * 100, 2),
                           "actual": False})
    return series


def _metrics(total: int, firsts, start: date, span_days: int, today: date,
             exam: date, days_left: int, with_series: bool) -> dict:
    done = len(firsts)
    derived = sum(1 for *_rest, d in firsts if d)
    per_day = _per_day(firsts)
    window = WINDOW
    done_window = sum(n for day, n in per_day.items()
                      if date.fromisoformat(day) > today - timedelta(days=window))
    pace = done_window / window if done_window else (done / span_days if done else 0.0)
    remaining = max(0, total - done)
    required = (remaining / days_left) if days_left > 0 else None

    finish: date | None = None
    if pace > 0 and remaining > 0:
        finish = today + timedelta(days=round(remaining / pace))
    elif remaining == 0:
        finish = today

    if done and span_days < 3:
        status, status_text = "insufficient", "学习记录不足 3 天，暂不做预测"
    else:
        status, status_text = _status(done, total, finish, exam, pace, required)

    out = {
        "total": total, "done": done,
        "percent": round(done / total * 100, 2) if total else 0,
        "status": status, "status_text": status_text,
        "pace": round(pace, 2), "pace_window": window,
        "required_pace": round(required, 2) if required is not None else None,
        "finish_date": finish.isoformat() if finish else None,
        "derived": derived,
    }
    if with_series:
        out["series"] = _series(per_day, start, today, total, pace, finish, exam)
    return out


def _dimension(label: str, metrics: dict) -> dict:
    derived = metrics.pop("derived")
    return {
        "label": label, "unit": UNIT, **metrics,
        "data_quality": {"derived_cards": derived,
                         "recorded_cards": metrics["done"] - derived},
    }


def timeline(conn, sid: str | None = None, days: int = 21) -> dict:
    """按天的累计完成曲线 + 线性外推预测，记 / 听 两个维度。"""
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
    span_days = max(1, (today - start).days + 1)

    total = _scope_total(conn, sid)
    dimensions = {
        "memo": _dimension("记", _metrics(
            total, memo_firsts, start, span_days, today, exam, days_left, True)),
        "listen": _dimension("听", _metrics(
            total, listen_firsts, start, span_days, today, exam, days_left, True)),
    }

    return {
        "today": today.isoformat(), "exam_date": exam.isoformat(), "days_left": days_left,
        "scope": sid or "all", "dimensions": dimensions,
        "subjects": _subjects(conn, start, span_days, today, exam, days_left),
        "streak": streak(conn),
        "daily": daily_progress(conn),
        "weekly": weekly(conn),
        "milestones": milestones(conn),
    }


def _subjects(conn, start: date, span_days: int, today: date,
              exam: date, days_left: int) -> list[dict]:
    out = []
    for s0 in conn.execute("SELECT id, name FROM subject ORDER BY sort"):
        st_total = _scope_total(conn, s0["id"])
        row = {"id": s0["id"], "name": s0["name"]}
        for key, firsts_of in (("memo", _completion_first_ts),
                               ("listen", _listen_first_ts)):
            m = _metrics(st_total, firsts_of(conn, s0["id"]), start, span_days,
                         today, exam, days_left, False)
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
