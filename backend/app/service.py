"""学习进度与今日队列的业务编排。"""
import json
from datetime import date, datetime, timedelta

from app import config, scheduler

PRIORITY_RANK = "CASE p.priority WHEN '★' THEN 0 WHEN '●' THEN 1 ELSE 2 END"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _loads(raw, default):
    try:
        return json.loads(raw) if raw else default
    except (TypeError, ValueError):
        return default


def card_queue(conn, sid: str | None = None, limit: int = 30) -> list[dict]:
    """到期卡优先，其次未学过的新卡；同一批内按考点优先级与卡片顺序。"""
    today = date.today().isoformat()
    sql = f"""
        SELECT c.card_id, c.point_id, c.kind, c.card_type, c.question, c.answer,
               c.options, c.answer_points, c.analysis, c.unit_refs, c.difficulty,
               p.title, p.subject_id, p.chapter_id, p.priority,
               cp.card_id AS seen, cp.due_at, cp.reviews, cp.last_result, cp.lapses,
               (SELECT listen_count FROM card_listen cl WHERE cl.card_id = c.card_id) AS listen_count
        FROM card c
        JOIN point p ON p.id = c.point_id
        JOIN chapter ch ON ch.id = p.chapter_id
        LEFT JOIN card_progress cp ON cp.card_id = c.card_id
        WHERE (cp.card_id IS NULL OR cp.due_at <= ?)
    """
    params: list = [today]
    if sid:
        sql += " AND p.subject_id = ?"
        params.append(sid)
    # 到期/新卡分组内：先按章权重（梯队 + 分值），再按考点优先级
    sql += (f" ORDER BY CASE WHEN cp.card_id IS NULL THEN 1 ELSE 0 END,"
            f" ch.tier, ch.weight_center DESC, {PRIORITY_RANK}, ch.sort, p.ord,"
            f" c.ord LIMIT ?")
    params.append(max(1, min(int(limit), 200)))
    rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        out.append({
            "card_id": r["card_id"], "point_id": r["point_id"],
            "kind": r["kind"], "card_type": r["card_type"],
            "question": r["question"], "answer": r["answer"],
            "options": _loads(r["options"], []),
            "answer_points": _loads(r["answer_points"], []),
            "analysis": r["analysis"], "unit_refs": _loads(r["unit_refs"], []),
            "difficulty": r["difficulty"], "title": r["title"],
            "priority": r["priority"], "reviews": r["reviews"] or 0,
            "last_result": r["last_result"], "lapses": r["lapses"] or 0,
            "listen_count": r["listen_count"] or 0,
            "subject_id": r["subject_id"], "chapter_id": r["chapter_id"],
            "due_at": r["due_at"], "new": r["seen"] is None,
        })
    return out


def listen_queue(conn, sid: str | None = None, limit: int = 10) -> list[dict]:
    """兼容旧接口：等价于按科目取听学卡片。"""
    """未听优先 → 次数少 → 优先级 → 章序。"""
    sql = f"""
        SELECT p.id, p.subject_id, p.title, p.point, p.listen_script, p.listen_kind,
               p.exam_types, p.chapter_id, ch.name AS chapter_name,
               lp.point_id AS heard, lp.listen_count,
               (SELECT question FROM card WHERE card_id = p.listen_card_id) AS question
        FROM point p
        JOIN chapter ch ON ch.id = p.chapter_id
        LEFT JOIN listen_progress lp ON lp.point_id = p.id
        WHERE p.listen_script != ''
    """
    params: list = []
    if sid:
        sql += " AND p.subject_id = ?"
        params.append(sid)
    sql += (f" ORDER BY CASE WHEN lp.point_id IS NULL THEN 0 ELSE 1 END,"
            f" COALESCE(lp.listen_count, 0), ch.tier, ch.weight_center DESC,"
            f" {PRIORITY_RANK}, ch.sort, p.ord LIMIT ?")
    params.append(max(1, min(int(limit), 100)))
    return [{
        "point_id": r["id"], "subject_id": r["subject_id"], "title": r["title"],
        "point": r["point"], "script": r["listen_script"], "kind": r["listen_kind"],
        "exam_types": _loads(r["exam_types"], []),
        "chapter_name": r["chapter_name"], "question": r["question"],
        "heard": r["heard"] is not None, "listen_count": r["listen_count"] or 0,
    } for r in conn.execute(sql, params).fetchall()]


def mark_read(conn, point_id: str) -> None:
    conn.execute(
        "INSERT INTO point_progress (point_id, read_at) VALUES (?, ?) "
        "ON CONFLICT(point_id) DO UPDATE SET read_at = excluded.read_at",
        (point_id, _now()))
    conn.commit()


def mark_card_listened(conn, card_id: str) -> None:
    conn.execute(
        "INSERT INTO card_listen (card_id, listen_count, updated_at) VALUES (?, 1, ?) "
        "ON CONFLICT(card_id) DO UPDATE SET listen_count = listen_count + 1, "
        "updated_at = excluded.updated_at",
        (card_id, _now()))
    conn.commit()


def mark_listened(conn, point_id: str) -> None:
    conn.execute(
        "INSERT INTO point_progress (point_id, listen_at) VALUES (?, ?) "
        "ON CONFLICT(point_id) DO UPDATE SET listen_at = excluded.listen_at",
        (point_id, _now()))
    conn.execute(
        "INSERT INTO listen_progress (point_id, listen_count, updated_at) "
        "VALUES (?, 1, ?) ON CONFLICT(point_id) DO UPDATE SET "
        "listen_count = listen_count + 1, updated_at = excluded.updated_at",
        (point_id, _now()))
    conn.commit()


def grade_card(conn, card_id: str, result: str) -> dict:
    row = conn.execute(
        "SELECT card_type, difficulty FROM card WHERE card_id = ?", (card_id,)
    ).fetchone()
    if row is None:
        raise KeyError(card_id)
    prev = conn.execute(
        "SELECT stage, interval, lapses, reviews FROM card_progress WHERE card_id = ?",
        (card_id,)).fetchone()
    difficulty = scheduler.initial_difficulty(row["card_type"], row["difficulty"])
    state = scheduler.next_state(
        prev["stage"] if prev else 0,
        prev["interval"] if prev else 0,
        prev["lapses"] if prev else 0,
        prev["reviews"] if prev else 0,
        result, difficulty,
    )
    conn.execute(
        "INSERT INTO card_event (card_id, ts, result) VALUES (?,?,?)",
        (card_id, _now(), result))
    conn.execute(
        "INSERT INTO card_progress (card_id, stage, ease, interval, due_at, lapses, "
        "reviews, last_result, updated_at) VALUES (?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(card_id) DO UPDATE SET stage=excluded.stage, ease=excluded.ease, "
        "interval=excluded.interval, due_at=excluded.due_at, lapses=excluded.lapses, "
        "reviews=excluded.reviews, last_result=excluded.last_result, "
        "updated_at=excluded.updated_at",
        (card_id, state["stage"], difficulty, state["interval"], state["due_at"],
         state["lapses"], state["reviews"], state["last_result"], _now()))
    conn.commit()
    return state


def mark_unit(conn, point_id: str, idx: int) -> None:
    conn.execute(
        "INSERT INTO unit_progress (point_id, idx, mastered_at) VALUES (?,?,?) "
        "ON CONFLICT(point_id, idx) DO UPDATE SET mastered_at = excluded.mastered_at",
        (point_id, idx, _now()))
    conn.commit()


def _scope(subjects: list[str] | None, chapters: list[str] | None) -> tuple[str, list]:
    """把「自定义范围」翻译成 WHERE 片段（作用于别名 p 的 point 表）。"""
    where, params = [], []
    if subjects:
        where.append(f"p.subject_id IN ({','.join('?' * len(subjects))})")
        params.extend(subjects)
    if chapters:
        where.append(f"p.chapter_id IN ({','.join('?' * len(chapters))})")
        params.extend(chapters)
    return (" AND " + " AND ".join(where)) if where else "", params


def custom_cards(conn, subjects=None, chapters=None, limit=30,
                 exclude: list[str] | None = None) -> dict:
    today = date.today().isoformat()
    scope_sql, params = _scope(subjects, chapters)
    exclude = exclude or []
    excl_sql = ""
    if exclude:
        excl_sql = f" AND c.card_id NOT IN ({','.join('?' * len(exclude))})"
        params = params + exclude
    sql = f"""
        SELECT c.card_id, c.point_id, c.kind, c.card_type, c.question, c.answer,
               c.options, c.answer_points, c.analysis, c.unit_refs, c.difficulty,
               p.title, p.subject_id, p.chapter_id, p.priority,
               cp.card_id AS seen, cp.due_at, cp.reviews, cp.last_result, cp.lapses,
               (SELECT listen_count FROM card_listen cl WHERE cl.card_id = c.card_id) AS listen_count
        FROM card c
        JOIN point p ON p.id = c.point_id
        JOIN chapter ch ON ch.id = p.chapter_id
        LEFT JOIN card_progress cp ON cp.card_id = c.card_id
        WHERE (cp.card_id IS NULL OR cp.due_at <= ?){excl_sql}{scope_sql}
        ORDER BY CASE WHEN cp.card_id IS NULL THEN 1 ELSE 0 END,
                 ch.tier, ch.weight_center DESC, {PRIORITY_RANK}, ch.sort, p.ord, c.ord
        LIMIT ?
    """
    rows = conn.execute(sql, [today, *params, max(1, min(int(limit), 200))]).fetchall()
    items = [{
        "card_id": r["card_id"], "point_id": r["point_id"], "kind": r["kind"],
        "card_type": r["card_type"], "question": r["question"], "answer": r["answer"],
        "options": _loads(r["options"], []),
        "answer_points": _loads(r["answer_points"], []),
        "analysis": r["analysis"], "unit_refs": _loads(r["unit_refs"], []),
        "difficulty": r["difficulty"], "title": r["title"],
        "priority": r["priority"],
        "reviews": r["reviews"] or 0, "last_result": r["last_result"],
        "lapses": r["lapses"] or 0, "listen_count": r["listen_count"] or 0,
        "subject_id": r["subject_id"], "chapter_id": r["chapter_id"],
        "due_at": r["due_at"], "new": r["seen"] is None,
    } for r in rows]
    return {"items": items, "remaining": _count_remaining(conn, sql, [today, *params], len(items))}


def _count_remaining(conn, sql: str, params: list, fetched: int) -> int:
    count_sql = "SELECT COUNT(*) FROM (" + sql.rsplit("LIMIT", 1)[0] + ")"
    total = conn.execute(count_sql, params).fetchone()[0]
    return max(0, total - fetched)


def custom_listen(conn, subjects=None, chapters=None, limit=10,
                  exclude: list[str] | None = None) -> dict:
    """听学队列：按**卡片**粒度（比点更短），每张卡念「考点 + 解析」。"""
    scope_sql, params = _scope(subjects, chapters)
    exclude = exclude or []
    excl_sql = ""
    if exclude:
        excl_sql = f" AND c.card_id NOT IN ({','.join('?' * len(exclude))})"
        params = params + exclude
    sql = f"""
        SELECT c.card_id, c.point_id, c.kind, c.card_type, c.question, c.answer,
               c.analysis, c.answer_points,
               p.title, p.point, p.explain, p.subject_id, p.chapter_id, p.priority,
               ch.name AS chapter_name, cl.card_id AS heard, cl.listen_count,
               cp.reviews, cp.last_result, cp.lapses, cp.due_at
        FROM card c
        JOIN point p ON p.id = c.point_id
        JOIN chapter ch ON ch.id = p.chapter_id
        LEFT JOIN card_listen cl ON cl.card_id = c.card_id
        LEFT JOIN card_progress cp ON cp.card_id = c.card_id
        WHERE 1=1{excl_sql}{scope_sql}
        ORDER BY CASE WHEN cl.card_id IS NULL THEN 0 ELSE 1 END,
                 COALESCE(cl.listen_count, 0), ch.tier, ch.weight_center DESC,
                 {PRIORITY_RANK}, ch.sort, p.ord, c.ord
        LIMIT ?
    """
    rows = conn.execute(sql, [*params, max(1, min(int(limit), 200))]).fetchall()
    items = [{
        "card_id": r["card_id"], "point_id": r["point_id"],
        "kind": r["kind"], "card_type": r["card_type"],
        "question": r["question"], "answer": r["answer"],
        "analysis": r["analysis"],
        "answer_points": _loads(r["answer_points"], []),
        "fallback": r["explain"],
        "title": r["title"], "point": r["point"],
        "subject_id": r["subject_id"], "chapter_id": r["chapter_id"],
        "chapter_name": r["chapter_name"], "priority": r["priority"],
        "heard": r["heard"] is not None, "listen_count": r["listen_count"] or 0,
        "reviews": r["reviews"] or 0, "last_result": r["last_result"],
        "lapses": r["lapses"] or 0, "due_at": r["due_at"],
    } for r in rows]
    return {"items": items, "remaining": _count_remaining(conn, sql, params, len(items))}


def progress_stats(conn, sid: str | None = None) -> dict:
    today = date.today().isoformat()
    sub = " AND p.subject_id = ?" if sid else ""
    sp = [sid] if sid else []
    total_points = conn.execute(
        f"SELECT COUNT(*) FROM point p WHERE 1=1{sub}", sp).fetchone()[0]
    read_points = conn.execute(
        f"SELECT COUNT(*) FROM point_progress pp JOIN point p ON p.id=pp.point_id "
        f"WHERE pp.read_at IS NOT NULL{sub}", sp).fetchone()[0]
    total_cards = conn.execute(
        f"SELECT COUNT(*) FROM card c JOIN point p ON p.id=c.point_id WHERE 1=1{sub}",
        sp).fetchone()[0]
    seen_cards = conn.execute(
        f"SELECT COUNT(*) FROM card_progress cp JOIN card c ON c.card_id=cp.card_id "
        f"JOIN point p ON p.id=c.point_id WHERE 1=1{sub}", sp).fetchone()[0]
    mastered = conn.execute(
        f"SELECT COUNT(*) FROM card_progress cp JOIN card c ON c.card_id=cp.card_id "
        f"JOIN point p ON p.id=c.point_id WHERE cp.stage >= 2{sub}", sp).fetchone()[0]
    due = conn.execute(
        f"SELECT COUNT(*) FROM card_progress cp JOIN card c ON c.card_id=cp.card_id "
        f"JOIN point p ON p.id=c.point_id WHERE cp.due_at <= ?{sub}", [today, *sp]
    ).fetchone()[0]
    total_listen = conn.execute(
        f"SELECT COUNT(*) FROM point p WHERE p.listen_script != ''{sub}", sp).fetchone()[0]
    heard = conn.execute(
        f"SELECT COUNT(*) FROM listen_progress lp JOIN point p ON p.id=lp.point_id "
        f"WHERE 1=1{sub}", sp).fetchone()[0]
    chapters = [dict(r) for r in conn.execute(f"""
        SELECT ch.id, ch.name, ch.module, ch.sort,
          (SELECT COUNT(*) FROM point p WHERE p.chapter_id=ch.id) AS total,
          (SELECT COUNT(*) FROM point_progress pp JOIN point p ON p.id=pp.point_id
             WHERE p.chapter_id=ch.id AND pp.read_at IS NOT NULL) AS read_n,
          (SELECT COUNT(*) FROM card_progress cp JOIN card c ON c.card_id=cp.card_id
             JOIN point p ON p.id=c.point_id WHERE p.chapter_id=ch.id) AS seen_n,
          (SELECT COUNT(*) FROM card c JOIN point p ON p.id=c.point_id
             WHERE p.chapter_id=ch.id) AS card_n
        FROM chapter ch WHERE 1=1{" AND ch.subject_id = ?" if sid else ""}
        ORDER BY ch.sort
    """, sp).fetchall()]
    return {
        "points": {"total": total_points, "read": read_points},
        "cards": {"total": total_cards, "seen": seen_cards, "mastered": mastered, "due": due},
        "listen": {"total": total_listen, "heard": heard},
        "today": today_summary(conn),
        "chapters": chapters,
    }


def today_summary(conn) -> dict:
    today = date.today().isoformat()
    return {
        "date": today,
        "cards_seen": conn.execute(
            "SELECT COUNT(*) FROM card_progress WHERE substr(updated_at,1,10)=?",
            (today,)).fetchone()[0],
        "cards_due": conn.execute(
            "SELECT COUNT(*) FROM card_progress WHERE due_at <= ?", (today,)).fetchone()[0],
        "listen_done": conn.execute(
            "SELECT COUNT(*) FROM listen_progress WHERE substr(updated_at,1,10)=?",
            (today,)).fetchone()[0],
        "read_done": conn.execute(
            "SELECT COUNT(*) FROM point_progress WHERE substr(read_at,1,10)=?",
            (today,)).fetchone()[0],
    }


# ---------- 收藏 / 错题 ----------

def set_favorite(conn, kind: str, ref_id: str, on: bool) -> None:
    if kind not in ("point", "card"):
        raise ValueError("kind 只能是 point / card")
    if on:
        conn.execute(
            "INSERT OR IGNORE INTO favorites (kind, ref_id, created_at) VALUES (?,?,?)",
            (kind, ref_id, _now()))
    else:
        conn.execute("DELETE FROM favorites WHERE kind = ? AND ref_id = ?",
                     (kind, ref_id))
    conn.commit()


def favorite_map(conn) -> dict[str, list[str]]:
    out = {"point": [], "card": []}
    for r in conn.execute("SELECT kind, ref_id FROM favorites ORDER BY created_at DESC"):
        out.setdefault(r["kind"], []).append(r["ref_id"])
    return out


def list_favorites(conn, kind: str | None = None, sid: str | None = None) -> list[dict]:
    if kind == "card":
        sql = """
            SELECT f.ref_id, f.created_at, c.question, c.kind AS card_kind,
                   c.point_id, p.title, p.subject_id, p.priority,
                   (SELECT last_result FROM card_progress cp WHERE cp.card_id=c.card_id) AS last_result
            FROM favorites f
            JOIN card c ON c.card_id = f.ref_id
            JOIN point p ON p.id = c.point_id
            WHERE f.kind = 'card'
        """
    else:
        sql = """
            SELECT f.ref_id, f.created_at, p.title, p.point, p.subject_id,
                   p.priority, ch.name AS chapter_name
            FROM favorites f
            JOIN point p ON p.id = f.ref_id
            JOIN chapter ch ON ch.id = p.chapter_id
            WHERE f.kind = 'point'
        """
    params: list = []
    if sid:
        sql += " AND p.subject_id = ?"
        params.append(sid)
    sql += " ORDER BY f.created_at DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def weak_cards(conn, sid: str | None = None, limit: int = 100) -> list[dict]:
    """错题本：记模块评为「吃力 / 忘了」的卡，忘了排在前面。"""
    sql = """
        SELECT cp.card_id, cp.last_result, cp.lapses, cp.stage, cp.due_at,
               cp.updated_at, c.question, c.kind AS card_kind, c.point_id,
               p.title, p.subject_id, p.priority, ch.name AS chapter_name
        FROM card_progress cp
        JOIN card c ON c.card_id = cp.card_id
        JOIN point p ON p.id = c.point_id
        JOIN chapter ch ON ch.id = p.chapter_id
        WHERE cp.last_result IN ('吃力', '忘了')
    """
    params: list = []
    if sid:
        sql += " AND p.subject_id = ?"
        params.append(sid)
    sql += (" ORDER BY CASE cp.last_result WHEN '忘了' THEN 0 ELSE 1 END,"
            " cp.updated_at DESC LIMIT ?")
    params.append(max(1, min(int(limit), 500)))
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def weak_counts(conn, sid: str | None = None) -> dict:
    sub = " AND p.subject_id = ?" if sid else ""
    params = [sid] if sid else []
    rows = conn.execute(
        f"SELECT cp.last_result, COUNT(*) n FROM card_progress cp "
        f"JOIN card c ON c.card_id=cp.card_id JOIN point p ON p.id=c.point_id "
        f"WHERE cp.last_result IN ('吃力','忘了'){sub} GROUP BY cp.last_result",
        params).fetchall()
    got = {r["last_result"]: r["n"] for r in rows}
    return {"forgot": got.get("忘了", 0), "fuzzy": got.get("吃力", 0),
            "total": sum(got.values())}


# ---------- 学完时间预测 ----------

def forecast(conn) -> dict:
    """按各科已见卡片的日均速度，估算学完日期。

    口径：速度 = 已见卡片数 / 距首次学习的天数（至少 1 天）；
    剩余 = 该科还没见过的卡片；预计学完 = 今天 + 剩余 / 速度。
    """
    today = date.today()
    out = []
    for s in conn.execute("SELECT id, name FROM subject ORDER BY sort").fetchall():
        sid = s["id"]
        total = conn.execute(
            "SELECT COUNT(*) FROM card c JOIN point p ON p.id=c.point_id "
            "WHERE p.subject_id = ?", (sid,)).fetchone()[0]
        row = conn.execute(
            "SELECT COUNT(*) AS seen, MIN(cp.updated_at) AS first_at, "
            "SUM(cp.reviews) AS reviews "
            "FROM card_progress cp JOIN card c ON c.card_id=cp.card_id "
            "JOIN point p ON p.id=c.point_id WHERE p.subject_id = ?", (sid,)).fetchone()
        seen = row["seen"] or 0
        first_at = row["first_at"]
        days = 1
        if first_at:
            try:
                days = max(1, (today - date.fromisoformat(first_at[:10])).days + 1)
            except ValueError:
                days = 1
        pace = seen / days if seen else 0.0
        remaining = max(0, total - seen)
        eta = None
        if pace > 0 and remaining > 0:
            eta = (today + timedelta(days=round(remaining / pace))).isoformat()
        elif remaining == 0:
            eta = today.isoformat()
        out.append({
            "id": sid, "name": s["name"], "total": total, "seen": seen,
            "remaining": remaining, "pace": round(pace, 2),
            "days_active": days, "eta": eta,
        })
    return {"today": today.isoformat(), "exam_date": config.EXAM_DATE, "subjects": out}


# ---------- 进度时间线与预测 ----------

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


def _scope_total(conn, sid: str | None) -> int:
    if sid:
        return conn.execute(
            "SELECT COUNT(*) FROM card c JOIN point p ON p.id=c.point_id "
            "WHERE p.subject_id = ?", (sid,)).fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM card").fetchone()[0]


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


def _active_days(conn) -> set[str]:
    """有过任何学习动作的日期集合（记一次、听一条、读一个点都算）。"""
    days: set[str] = set()
    for sql in (
        "SELECT ts FROM card_event",
        "SELECT updated_at AS ts FROM card_listen",
        "SELECT read_at AS ts FROM point_progress WHERE read_at IS NOT NULL",
    ):
        for r in conn.execute(sql):
            if r["ts"]:
                days.add(r["ts"][:10])
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
        "SELECT COUNT(*) FROM card_listen WHERE substr(updated_at,1,10) = ?", (today,)
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
    # 下一个里程碑：取两条阶梯里最接近的那个，空状态也有内容可看
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


def timeline(conn, sid: str | None = None, days: int = 21) -> dict:
    """按天的累计完成曲线 + 线性外推预测。

    完成口径：卡片至少复习过一次（card_progress 有记录）。
    速度口径：最近 7 天新增完成数 / 7；不足 7 天则用整体平均。
    """
    today = date.today()
    try:
        exam = date.fromisoformat(config.EXAM_DATE)
    except ValueError:
        exam = today + timedelta(days=60)
    days_left = max(0, (exam - today).days)

    total = _scope_total(conn, sid)
    firsts = _completion_first_ts(conn, sid)
    done = len(firsts)
    derived = sum(1 for _, _, d in firsts if d)
    per_day: dict[str, int] = {}
    for _, day, _d in firsts:
        per_day[day] = per_day.get(day, 0) + 1

    days = max(7, min(int(days or 21), 60))
    start = today - timedelta(days=days - 1)
    if per_day:
        earliest = date.fromisoformat(min(per_day))
        if earliest > start:
            start = earliest       # 不画没有数据的历史
    span_days = max(1, (today - start).days + 1)

    # 速度口径固定用「最近 7 天 / 7」，不足 7 天时按 7 天摊平，避免第一天的
    # 集中复习被放大成十几倍的假速度
    window = 7
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

    # 实际段：start..today 的累计
    series = []
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

    subjects = []
    for s0 in conn.execute("SELECT id, name FROM subject ORDER BY sort"):
        st_total = _scope_total(conn, s0["id"])
        st_firsts = _completion_first_ts(conn, s0["id"])
        st_done = len(st_firsts)
        st_per_day: dict[str, int] = {}
        for _, day, _d in st_firsts:
            st_per_day[day] = st_per_day.get(day, 0) + 1
        st_sp = max(1, (today - start).days + 1)
        st_win = 7 if st_sp >= 7 else st_sp
        st_n = sum(n for day, n in st_per_day.items()
                   if date.fromisoformat(day) > today - timedelta(days=st_win))
        st_pace = st_n / st_win if st_n else (st_done / st_sp if st_done else 0.0)
        st_rem = max(0, st_total - st_done)
        st_finish = (today + timedelta(days=round(st_rem / st_pace))
                     if st_pace > 0 and st_rem else (today if st_rem == 0 else None))
        st_required = (st_rem / days_left) if days_left > 0 else None
        st_status, _ = _status(st_done, st_total, st_finish, exam, st_pace, st_required)
        subjects.append({
            "id": s0["id"], "name": s0["name"], "total": st_total, "done": st_done,
            "percent": round(st_done / st_total * 100, 2) if st_total else 0,
            "pace": round(st_pace, 2), "finish_date": st_finish.isoformat() if st_finish else None,
            "status": st_status,
        })

    return {
        "today": today.isoformat(), "exam_date": exam.isoformat(), "days_left": days_left,
        "scope": sid or "all", "total": total, "done": done,
        "percent": round(done / total * 100, 2) if total else 0,
        "status": status, "status_text": status_text,
        "pace": round(pace, 2), "pace_window": window,
        "required_pace": round(required, 2) if required is not None else None,
        "finish_date": finish.isoformat() if finish else None,
        "series": series, "subjects": subjects,
        "data_quality": {"derived_cards": derived, "recorded_cards": done - derived},
        "streak": streak(conn),
        "daily": daily_progress(conn),
        "weekly": weekly(conn),
        "milestones": milestones(conn),
    }
