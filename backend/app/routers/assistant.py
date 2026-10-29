"""AI 问答：SSE 流式 + 会话历史。"""
import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import ai, assistant, db

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AskIn(BaseModel):
    question: str
    point_id: str | None = None
    card_id: str | None = None
    conversation_id: str | None = None


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/ask")
async def ask(payload: AskIn, conn=Depends(db.get_db)):
    question = payload.question.strip()
    if not question:
        raise HTTPException(400, "问题不能为空")

    context, related_ids, source_refs = assistant.build_context(
        conn, question, payload.point_id, payload.conversation_id, payload.card_id)
    _, history = assistant.recent_history(conn, payload.conversation_id)
    cid = assistant.ensure_conversation(
        conn, payload.conversation_id, payload.point_id, question, payload.card_id)
    db_path = Path(conn.execute("PRAGMA database_list").fetchone()["file"])
    model = ai.chat_target()[1]

    async def gen():
        parts: list[str] = []
        truncated = False
        msg_id = 0
        try:
            async for delta in ai.stream_answer(question, context, history):
                parts.append(delta)
                yield _sse({"type": "delta", "delta": delta})
        except (asyncio.CancelledError, GeneratorExit):
            # 客户端中断（关面板/切知识点）时 Starlette 取消生成器，走到这里
            truncated = True
            raise
        finally:
            # 请求级连接在流式期间可能已关，落库用同库新连接
            log_conn = db.connect(db_path)
            try:
                msg_id = assistant.persist_turn(
                    log_conn, cid, question, "".join(parts), related_ids,
                    source_refs, model, truncated)
            finally:
                log_conn.close()
        if not truncated:
            yield _sse({"type": "done", "message_id": msg_id,
                        "conversation_id": cid, "related_point_ids": related_ids})

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/history")
def history(point_id: str | None = None, card_id: str | None = None,
            limit: int = 20, conn=Depends(db.get_db)):
    if card_id and card_id.strip():
        return {"items": assistant.history_for_card(conn, card_id.strip(), limit)}
    if point_id and point_id.strip():
        return {"items": assistant.history_for_point(conn, point_id.strip(), limit)}
    raise HTTPException(400, "point_id 或 card_id 至少给一个")


@router.get("/history/count")
def history_count(point_id: str | None = None, card_id: str | None = None,
                  conn=Depends(db.get_db)):
    if card_id and card_id.strip():
        return {"count": assistant.count_for_card(conn, card_id.strip())}
    if point_id and point_id.strip():
        return {"count": assistant.count_for_point(conn, point_id.strip())}
    return {"count": 0}


@router.get("/conversations")
def conversations(limit: int = 30, offset: int = 0, conn=Depends(db.get_db)):
    return {"items": assistant.list_conversations(conn, limit, offset)}


@router.get("/conversations/{cid}")
def conversation(cid: str, conn=Depends(db.get_db)):
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (cid,)).fetchone()
    if row is None:
        raise HTTPException(404, "会话不存在")
    return {"conversation": dict(row),
            "messages": assistant.conversation_messages(conn, cid)}


@router.delete("/conversations/{cid}")
def remove(cid: str, conn=Depends(db.get_db)):
    assistant.delete_conversation(conn, cid)
    return {"ok": True}
