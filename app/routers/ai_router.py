import datetime
import json
import sqlite3
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import auth, content, db
from app.config import get_settings
from app.services import providers

router = APIRouter(prefix="/api/ai", dependencies=[Depends(auth.require_auth)])


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class ChatBody(BaseModel):
    owner_type: Literal["point", "quiz", "free"]
    owner_ref: str | None = None
    message: str


@router.get("/threads")
def threads(con: sqlite3.Connection = Depends(db.get_db)):
    return {"items": [dict(r) for r in con.execute(
        "SELECT id, owner_type, owner_ref, title, updated_at FROM ai_threads "
        "ORDER BY updated_at DESC")]}


@router.get("/threads/{thread_id}/messages")
def thread_messages(thread_id: str, con: sqlite3.Connection = Depends(db.get_db)):
    rows = con.execute("SELECT role, content, reasoning, ts FROM ai_messages "
                       "WHERE thread_id = ? ORDER BY id", (thread_id,)).fetchall()
    return {"items": [dict(r) for r in rows]}


def _get_or_create_thread(con, owner_type: str, owner_ref: str | None) -> dict:
    row = con.execute("SELECT id, owner_type, owner_ref, title FROM ai_threads "
                      "WHERE owner_type = ? AND IFNULL(owner_ref,'') = IFNULL(?,'') "
                      "ORDER BY updated_at DESC LIMIT 1", (owner_type, owner_ref)).fetchone()
    if row:
        return dict(row)
    title = "自由问答"
    if owner_type == "point" and owner_ref:
        found = content.find_point(content.load_content(), owner_ref)
        title = found[2].get("text", owner_ref)[:24] if found else owner_ref
    elif owner_type == "quiz" and owner_ref:
        found = content.find_quiz(content.load_content(), owner_ref)
        title = ("选择题：" + found[2].get("stem", ""))[:24] if found else owner_ref
    tid = str(uuid.uuid4())
    con.execute("INSERT INTO ai_threads(id, owner_type, owner_ref, title, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?)", (tid, owner_type, owner_ref, title, _now(), _now()))
    con.commit()
    return {"id": tid, "owner_type": owner_type, "owner_ref": owner_ref, "title": title}


@router.post("/chat")
def chat(body: ChatBody):
    def gen():
        con = db.connect()
        try:
            thread = _get_or_create_thread(con, body.owner_type, body.owner_ref)
            history = [dict(r) for r in con.execute(
                "SELECT role, content FROM ai_messages WHERE thread_id = ? ORDER BY id DESC LIMIT 10",
                (thread["id"],)).fetchall()][::-1]
            con.execute("INSERT INTO ai_messages(thread_id, role, content, ts) VALUES(?,?,?,?)",
                        (thread["id"], "user", body.message, _now()))
            con.commit()
            try:
                data = content.load_content()
            except content.ContentMissing:
                data = {}
            messages = providers.build_messages(
                (body.owner_type, body.owner_ref), history, data
            ) + [{"role": "user", "content": body.message}]

            yield f"data: {json.dumps({'type': 'thread', 'thread_id': thread['id']}, ensure_ascii=False)}\n\n"
            content_buf, reasoning_buf = [], []
            try:
                for evt in providers.stream_chat(messages, thread["id"], get_settings()):
                    if evt["type"] == "content":
                        content_buf.append(evt["delta"])
                    else:
                        reasoning_buf.append(evt["delta"])
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
            except Exception as exc:  # 断流：保全已生成部分
                if content_buf or reasoning_buf:
                    con.execute("INSERT INTO ai_messages(thread_id, role, content, reasoning, ts) "
                                "VALUES(?,?,?,?,?)",
                                (thread["id"], "assistant", "".join(content_buf),
                                 "".join(reasoning_buf), _now()))
                    con.commit()
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc), 'partial_saved': bool(content_buf)}, ensure_ascii=False)}\n\n"
                return
            cur = con.execute("INSERT INTO ai_messages(thread_id, role, content, reasoning, ts) "
                              "VALUES(?,?,?,?,?)",
                              (thread["id"], "assistant", "".join(content_buf),
                               "".join(reasoning_buf), _now()))
            con.execute("UPDATE ai_threads SET updated_at = ? WHERE id = ?", (_now(), thread["id"]))
            con.commit()
            yield f"data: {json.dumps({'type': 'done', 'message_id': cur.lastrowid}, ensure_ascii=False)}\n\n"
        finally:
            con.close()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
