"""卡片笔记：听与记共用，每卡一条。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import db, service

router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteIn(BaseModel):
    card_id: str
    content: str


@router.get("")
def read_note(card_id: str, conn=Depends(db.get_db)):
    card_id = card_id.strip()
    if not card_id:
        raise HTTPException(400, "card_id 不能为空")
    row = service.get_note(conn, card_id)
    return row or {"card_id": card_id, "content": "", "updated_at": None}


@router.put("")
def write_note(payload: NoteIn, conn=Depends(db.get_db)):
    card_id = payload.card_id.strip()
    if not card_id:
        raise HTTPException(400, "card_id 不能为空")
    try:
        row = service.set_note(conn, card_id, payload.content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if row is None:
        raise HTTPException(404, "卡片不存在")
    return {"ok": True, **row}
