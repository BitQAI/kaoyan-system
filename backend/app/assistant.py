"""AI 上下文组装与会话归档。

上下文四层（超出预算按顺序裁剪）：
  L1 当前知识点全文  ≤3000 字
  L2 本会话最近 6 条 ≤2000 字
  L3 FTS5 召回 ≤5 点 ≤1500 字
  L4 溯源原文整段    ≤800  字
"""
import json
import uuid
from datetime import datetime
from typing import Iterable

from app import locator, search

L1_BUDGET = 3000
L2_BUDGET = 2000
L3_BUDGET = 1500
L4_BUDGET = 800
HISTORY_TURNS = 6
RECALL_LIMIT = 5
TITLE_LEN = 24


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _loads(raw, default):
    try:
        return json.loads(raw) if raw else default
    except (TypeError, ValueError):
        return default


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


# ---------- 上下文 ----------

def point_profile(conn, point_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM point WHERE id = ?", (point_id,)).fetchone()
    if row is None:
        return None
    return dict(row)


def _l1(conn, p: dict) -> str:
    parts = [
        f"【科目】{p['subject_id']}",
        f"【知识点】{p['title']}（{p['point']}）",
        f"【解析】{p['explain']}",
        f"【怎么考】{p['exam']}",
        f"【关键词】{'、'.join(_loads(p['keywords'], []))}",
        f"【证据强度】{p['evidence_level']}：{p['evidence_basis'] or '未标注'}",
    ]
    units = [r["text"] for r in conn.execute(
        "SELECT text FROM unit WHERE point_id = ? ORDER BY idx", (p["id"],))]
    if units:
        parts.append("【记忆单元】\n" + "\n".join(f"- {u}" for u in units))
    cards = conn.execute(
        "SELECT question, answer FROM card WHERE point_id = ? ORDER BY ord",
        (p["id"],)).fetchall()
    if cards:
        parts.append("【卡片】\n" + "\n".join(
            f"- 问：{c['question']}\n  答：{c['answer']}" for c in cards))
    conf = conn.execute(
        "SELECT name, distinction FROM relation WHERE point_id=? AND kind='confusable'",
        (p["id"],)).fetchall()
    if conf:
        parts.append("【易混】\n" + "\n".join(
            f"- {c['name']}：{c['distinction']}" for c in conf))
    if p["listen_script"]:
        parts.append(f"【朗读稿】{p['listen_script']}")
    alts = [r["alt"] for r in conn.execute(
        "SELECT alt FROM media WHERE point_id = ? AND alt != ''", (p["id"],))]
    if alts:
        parts.append("【图示说明】" + " / ".join(alts))
    return _fit(parts, L1_BUDGET)


def _fit(parts: list[str], budget: int) -> str:
    out, used = [], 0
    for part in parts:
        if used >= budget:
            break
        remain = budget - used
        piece = part if len(part) <= remain else part[:remain] + "…"
        out.append(piece)
        used += len(piece)
    return "\n".join(out)


def recent_history(conn, conversation_id: str | None) -> tuple[str, list[dict]]:
    """本会话最近 N 条消息：返回 (拼接文本, 消息列表)。"""
    return _l2(conn, conversation_id)


def _l2(conn, conversation_id: str | None) -> tuple[str, list[dict]]:
    if not conversation_id:
        return "", []
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? "
        "ORDER BY id DESC LIMIT ?", (conversation_id, HISTORY_TURNS)).fetchall()
    history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    text = "\n".join(f"{h['role']}：{h['content']}" for h in history)
    return _clip(text, L2_BUDGET), history


def _l3(conn, question: str, exclude: set[str]) -> tuple[str, list[str]]:
    hits = search.search(conn, question, None, RECALL_LIMIT + len(exclude))
    lines, ids = [], []
    for item in hits["points"]:
        if item["id"] in exclude:
            continue
        row = conn.execute("SELECT explain FROM point WHERE id = ?",
                           (item["id"],)).fetchone()
        lines.append(f"[{item['id']}] {item['title']}：{item['point']}\n"
                     f"{_clip(row['explain'] if row else '', 300)}")
        ids.append(item["id"])
        if len(lines) >= RECALL_LIMIT:
            break
    return _clip("\n".join(lines), L3_BUDGET), ids


def _l4(p: dict) -> str:
    text, _ = locator.resolve_paragraph(
        p["source_ref"], p["source_kind"], p["source_file"], p["evidence_basis"])
    return _clip(text, L4_BUDGET)


def build_context(conn, question: str, point_id: str | None = None,
                  conversation_id: str | None = None) -> tuple[str, list[str], list[str]]:
    blocks: list[str] = []
    related: list[str] = []
    source_refs: list[str] = []

    current = point_profile(conn, point_id) if point_id else None
    if current:
        related.append(current["id"])
        blocks.append("【当前知识点】\n" + _l1(conn, current))
        if current["source_ref"]:
            source_refs.append(f"{current['source_kind'] or ''}:{current['source_ref']}")
            para = _l4(current)
            if para:
                blocks.append("【原文段落】\n" + para)

    history_text, _ = _l2(conn, conversation_id)
    if history_text:
        blocks.append("【本次对话上文】\n" + history_text)

    recall_text, recall_ids = _l3(conn, question, set(related))
    if recall_text:
        blocks.append("【相关问题召回】\n" + recall_text)
        related.extend(recall_ids)

    return "\n\n".join(blocks), related, source_refs[:10]


# ---------- 会话 ----------

def ensure_conversation(conn, conversation_id: str | None, point_id: str | None,
                        question: str) -> str:
    if conversation_id:
        row = conn.execute("SELECT id FROM conversations WHERE id = ?",
                           (conversation_id,)).fetchone()
        if row:
            return conversation_id
    cid = conversation_id or uuid.uuid4().hex[:16]
    now = _now()
    conn.execute(
        "INSERT INTO conversations (id, title, point_id, created_at, updated_at, msg_count) "
        "VALUES (?,?,?,?,?,0)",
        (cid, question.strip()[:TITLE_LEN], point_id, now, now))
    conn.commit()
    return cid


def persist_turn(conn, conversation_id: str, question: str, answer: str,
                 related_ids: Iterable[str], source_refs: Iterable[str],
                 model: str = "", truncated: bool = False) -> int:
    now = _now()
    ids = list(dict.fromkeys(x for x in related_ids if x))
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, related_point_ids, "
        "source_refs, model, truncated, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (conversation_id, "user", question, "[]", "[]", model, 0, now))
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, related_point_ids, "
        "source_refs, model, truncated, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (conversation_id, "assistant", answer,
         json.dumps(ids, ensure_ascii=False),
         json.dumps(list(source_refs), ensure_ascii=False),
         model, 1 if truncated else 0, now))
    msg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    # 问答两行都挂上知识点：答句用于取引用，问句用于「按点看历史」的精确匹配
    for pid in ids:
        for mid in (user_id, msg_id):
            conn.execute("INSERT OR IGNORE INTO message_points (message_id, point_id) "
                         "VALUES (?,?)", (mid, pid))
    conn.execute(
        "UPDATE conversations SET updated_at = ?, msg_count = msg_count + 2 WHERE id = ?",
        (now, conversation_id))
    conn.commit()
    return msg_id


def history_for_point(conn, point_id: str, limit: int = 20) -> list[dict]:
    """按知识点反查历史，走关联表做精确匹配（避免 2040101 误配 20401010）。"""
    limit = max(1, min(int(limit or 20), 50))
    rows = conn.execute(
        "SELECT DISTINCT m.id, m.conversation_id, m.content AS answer, "
        "m.created_at, m.related_point_ids, c.title "
        "FROM message_points mp "
        "JOIN messages m ON m.id = mp.message_id "
        "JOIN conversations c ON c.id = m.conversation_id "
        "WHERE mp.point_id = ? AND m.role = 'assistant' "
        "ORDER BY m.id DESC LIMIT ?", (point_id, limit)).fetchall()
    out = []
    for r in rows:
        ask = conn.execute(
            "SELECT content FROM messages WHERE conversation_id = ? AND id < ? "
            "AND role = 'user' ORDER BY id DESC LIMIT 1",
            (r["conversation_id"], r["id"])).fetchone()
        out.append({
            "id": r["id"], "conversation_id": r["conversation_id"],
            "ts": r["created_at"], "question": ask["content"] if ask else "",
            "answer": r["answer"],
            "related_point_ids": _loads(r["related_point_ids"], []),
        })
    return out


def count_for_point(conn, point_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM message_points mp JOIN messages m ON m.id = mp.message_id "
        "WHERE mp.point_id = ? AND m.role = 'user'", (point_id,)).fetchone()[0]


def list_conversations(conn, limit: int = 30, offset: int = 0) -> list[dict]:
    limit = max(1, min(int(limit or 30), 100))
    return [dict(r) for r in conn.execute(
        "SELECT id, title, point_id, created_at, updated_at, msg_count "
        "FROM conversations ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (limit, max(0, int(offset or 0)))).fetchall()]


def conversation_messages(conn, cid: str) -> list[dict]:
    return [{
        "id": r["id"], "role": r["role"], "content": r["content"],
        "related_point_ids": _loads(r["related_point_ids"], []),
        "source_refs": _loads(r["source_refs"], []),
        "truncated": bool(r["truncated"]), "created_at": r["created_at"],
    } for r in conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (cid,))]


def delete_conversation(conn, cid: str) -> None:
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
    conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))
    conn.commit()
