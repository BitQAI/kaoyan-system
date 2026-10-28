"""FTS5 检索（trigram）。

trigram 要求查询串 ≥3 字；短查询回落 LIKE，避免「细胞」这种两字词零命中。
"""
import json

SHORT_QUERY_LEN = 3


def _fts_query(q: str) -> str:
    return '"' + q.replace('"', '""') + '"'


def search(conn, q: str, sid: str | None = None, limit: int = 20) -> dict:
    q = (q or "").strip()
    if not q:
        return {"points": [], "cards": []}
    limit = max(1, min(int(limit or 20), 50))
    if len(q) < SHORT_QUERY_LEN:
        return _like_search(conn, q, sid, limit)

    point_rows = conn.execute(
        "SELECT point_id, bm25(point_fts) AS score FROM point_fts "
        "WHERE point_fts MATCH ? ORDER BY score LIMIT ?",
        (_fts_query(q), limit * 3),
    ).fetchall()
    card_rows = conn.execute(
        "SELECT card_id, point_id, bm25(card_fts) AS score FROM card_fts "
        "WHERE card_fts MATCH ? ORDER BY score LIMIT ?",
        (_fts_query(q), limit * 3),
    ).fetchall()
    return {
        "points": _hydrate_points(conn, [r["point_id"] for r in point_rows], sid, limit),
        "cards": _hydrate_cards(conn, [r["card_id"] for r in card_rows], sid, limit),
    }


def _like_search(conn, q: str, sid: str | None, limit: int) -> dict:
    like = f"%{q}%"
    pids = [r["id"] for r in conn.execute(
        "SELECT id FROM point WHERE (title LIKE ? OR point LIKE ? OR keywords LIKE ?) "
        "ORDER BY CASE WHEN title LIKE ? THEN 0 ELSE 1 END LIMIT ?",
        (like, like, like, f"%{q}%", limit),
    ).fetchall()]
    cids = [r["card_id"] for r in conn.execute(
        "SELECT card_id FROM card WHERE question LIKE ? LIMIT ?", (like, limit),
    ).fetchall()]
    return {
        "points": _hydrate_points(conn, pids, sid, limit),
        "cards": _hydrate_cards(conn, cids, sid, limit),
    }


def _hydrate_points(conn, ids, sid, limit) -> list[dict]:
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    sql = (f"SELECT id, subject_id, chapter_id, title, point, priority "
           f"FROM point WHERE id IN ({placeholders})")
    params: list = list(ids)
    if sid:
        sql += " AND subject_id = ?"
        params.append(sid)
    rows = conn.execute(sql, params).fetchall()
    by_id = {r["id"]: dict(r) for r in rows}
    out = [by_id[i] for i in ids if i in by_id][:limit]
    for item in out:
        item["keywords"] = json.loads(
            conn.execute("SELECT keywords FROM point WHERE id = ?",
                         (item["id"],)).fetchone()[0] or "[]")
    return out


def _hydrate_cards(conn, ids, sid, limit) -> list[dict]:
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    sql = (f"SELECT c.card_id, c.point_id, c.kind, c.question, p.title, p.subject_id "
           f"FROM card c JOIN point p ON p.id = c.point_id "
           f"WHERE c.card_id IN ({placeholders})")
    params: list = list(ids)
    if sid:
        sql += " AND p.subject_id = ?"
        params.append(sid)
    rows = conn.execute(sql, params).fetchall()
    by_id = {r["card_id"]: dict(r) for r in rows}
    return [by_id[i] for i in ids if i in by_id][:limit]
