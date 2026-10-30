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
               c.payload,
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
            "payload": _loads(r["payload"], {}),
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
    now = _now()
    conn.execute(
        "INSERT INTO card_listen (card_id, listen_count, updated_at) VALUES (?, 1, ?) "
        "ON CONFLICT(card_id) DO UPDATE SET listen_count = listen_count + 1, "
        "updated_at = excluded.updated_at",
        (card_id, now))
    conn.execute("INSERT INTO listen_event (card_id, ts) VALUES (?, ?)", (card_id, now))
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
               c.payload,
               p.title, p.subject_id, p.chapter_id, p.priority,
               cp.card_id AS seen, cp.due_at, cp.reviews, cp.last_result, cp.lapses,
               cn.content AS note,
               (SELECT listen_count FROM card_listen cl WHERE cl.card_id = c.card_id) AS listen_count
        FROM card c
        JOIN point p ON p.id = c.point_id
        JOIN chapter ch ON ch.id = p.chapter_id
        LEFT JOIN card_progress cp ON cp.card_id = c.card_id
        LEFT JOIN card_note cn ON cn.card_id = c.card_id
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
            "payload": _loads(r["payload"], {}),
        "priority": r["priority"],
        "reviews": r["reviews"] or 0, "last_result": r["last_result"],
        "lapses": r["lapses"] or 0, "listen_count": r["listen_count"] or 0,
        "note": r["note"] or "",
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
               c.analysis, c.answer_points, c.payload,
               p.title, p.point, p.explain, p.subject_id, p.chapter_id, p.priority,
               ch.name AS chapter_name, cl.card_id AS heard, cl.listen_count,
               cp.reviews, cp.last_result, cp.lapses, cp.due_at,
               cn.content AS note
        FROM card c
        JOIN point p ON p.id = c.point_id
        JOIN chapter ch ON ch.id = p.chapter_id
        LEFT JOIN card_listen cl ON cl.card_id = c.card_id
        LEFT JOIN card_progress cp ON cp.card_id = c.card_id
        LEFT JOIN card_note cn ON cn.card_id = c.card_id
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
        "payload": _loads(r["payload"], {}),
        "fallback": r["explain"],
        "title": r["title"], "point": r["point"],
        "subject_id": r["subject_id"], "chapter_id": r["chapter_id"],
        "chapter_name": r["chapter_name"], "priority": r["priority"],
        "heard": r["heard"] is not None, "listen_count": r["listen_count"] or 0,
        "reviews": r["reviews"] or 0, "last_result": r["last_result"],
        "lapses": r["lapses"] or 0, "due_at": r["due_at"],
        "note": r["note"] or "",
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
    heard = conn.execute(
        f"SELECT COUNT(*) FROM card_listen cl JOIN card c ON c.card_id=cl.card_id "
        f"JOIN point p ON p.id=c.point_id WHERE 1=1{sub}", sp).fetchone()[0]
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
        "listen": {"total": total_cards, "heard": heard},
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


# ---------- 卡片笔记 ----------

NOTE_MAX_LEN = 2000


def get_note(conn, card_id: str) -> dict | None:
    row = conn.execute(
        "SELECT card_id, content, created_at, updated_at FROM card_note "
        "WHERE card_id = ?", (card_id,)).fetchone()
    return dict(row) if row else None


def set_note(conn, card_id: str, content: str) -> dict | None:
    """保存或删除笔记；卡不存在返回 None，超长抛 ValueError。"""
    if conn.execute("SELECT 1 FROM card WHERE card_id = ?", (card_id,)).fetchone() is None:
        return None
    text = (content or "").strip()
    if len(text) > NOTE_MAX_LEN:
        raise ValueError(f"笔记不能超过 {NOTE_MAX_LEN} 字")
    now = _now()
    if not text:
        conn.execute("DELETE FROM card_note WHERE card_id = ?", (card_id,))
        conn.commit()
        return {"card_id": card_id, "content": "", "updated_at": None}
    conn.execute(
        "INSERT INTO card_note (card_id, content, created_at, updated_at) "
        "VALUES (?,?,?,?) ON CONFLICT(card_id) DO UPDATE SET "
        "content = excluded.content, updated_at = excluded.updated_at",
        (card_id, text, now, now))
    conn.commit()
    row = get_note(conn, card_id)
    return row


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

