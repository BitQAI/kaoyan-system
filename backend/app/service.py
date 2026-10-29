"""学习进度与今日队列的业务编排。"""
import json
from datetime import date, datetime

from app import scheduler

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
               p.title, p.subject_id, p.chapter_id,
               cp.card_id AS seen, cp.due_at
        FROM card c
        JOIN point p ON p.id = c.point_id
        LEFT JOIN card_progress cp ON cp.card_id = c.card_id
        WHERE (cp.card_id IS NULL OR cp.due_at <= ?)
    """
    params: list = [today]
    if sid:
        sql += " AND p.subject_id = ?"
        params.append(sid)
    sql += (f" ORDER BY CASE WHEN cp.card_id IS NULL THEN 1 ELSE 0 END,"
            f" {PRIORITY_RANK}, c.ord LIMIT ?")
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
            "subject_id": r["subject_id"], "chapter_id": r["chapter_id"],
            "due_at": r["due_at"], "new": r["seen"] is None,
        })
    return out


def listen_queue(conn, sid: str | None = None, limit: int = 10) -> list[dict]:
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
            f" COALESCE(lp.listen_count, 0), {PRIORITY_RANK}, ch.sort, p.ord LIMIT ?")
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
               p.title, p.subject_id, p.chapter_id, cp.card_id AS seen, cp.due_at
        FROM card c
        JOIN point p ON p.id = c.point_id
        LEFT JOIN card_progress cp ON cp.card_id = c.card_id
        WHERE (cp.card_id IS NULL OR cp.due_at <= ?){excl_sql}{scope_sql}
        ORDER BY CASE WHEN cp.card_id IS NULL THEN 1 ELSE 0 END,
                 {PRIORITY_RANK}, c.ord
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
    scope_sql, params = _scope(subjects, chapters)
    exclude = exclude or []
    excl_sql = ""
    if exclude:
        excl_sql = f" AND p.id NOT IN ({','.join('?' * len(exclude))})"
        params = params + exclude
    sql = f"""
        SELECT p.id, p.subject_id, p.title, p.point, p.listen_script, p.listen_kind,
               p.exam_types, p.listen_card_id, p.chapter_id, ch.name AS chapter_name,
               lp.point_id AS heard, lp.listen_count,
               (SELECT question FROM card WHERE card_id = p.listen_card_id) AS question,
               (SELECT card_id FROM card WHERE card_id = p.listen_card_id) AS card_id
        FROM point p
        JOIN chapter ch ON ch.id = p.chapter_id
        LEFT JOIN listen_progress lp ON lp.point_id = p.id
        WHERE p.listen_script != ''{excl_sql}{scope_sql}
        ORDER BY CASE WHEN lp.point_id IS NULL THEN 0 ELSE 1 END,
                 COALESCE(lp.listen_count, 0), {PRIORITY_RANK}, ch.sort, p.ord
        LIMIT ?
    """
    rows = conn.execute(sql, [*params, max(1, min(int(limit), 100))]).fetchall()
    items = [{
        "point_id": r["id"], "subject_id": r["subject_id"], "title": r["title"],
        "point": r["point"], "script": r["listen_script"], "kind": r["listen_kind"],
        "exam_types": _loads(r["exam_types"], []), "chapter_name": r["chapter_name"],
        "question": r["question"], "card_id": r["card_id"],
        "heard": r["heard"] is not None, "listen_count": r["listen_count"] or 0,
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
