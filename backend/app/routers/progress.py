"""学习进度、今日队列与评分。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import db, progress, service

router = APIRouter(prefix="/api", tags=["progress"])


class PointIn(BaseModel):
    point_id: str


class CardIn(BaseModel):
    card_id: str
    result: str


class UnitIn(BaseModel):
    point_id: str
    idx: int


class ListenIn(BaseModel):
    card_id: str | None = None
    point_id: str | None = None


class CustomIn(BaseModel):
    mode: str
    subjects: list[str] = []
    chapters: list[str] = []
    limit: int = 30
    exclude: list[str] = []


@router.get("/queue/today")
def queue(mode: str = "memo", sid: str | None = None, limit: int = 30,
          conn=Depends(db.get_db)):
    if mode == "memo":
        items = service.card_queue(conn, sid, limit)
    elif mode == "listen":
        items = service.listen_queue(conn, sid, limit)
    else:
        raise HTTPException(400, "mode 只能是 memo / listen")
    return {"mode": mode, "items": items}


@router.post("/queue/custom")
def custom_queue(payload: CustomIn, conn=Depends(db.get_db)):
    mode = payload.mode
    if mode == "memo":
        result = service.custom_cards(conn, payload.subjects, payload.chapters,
                                      payload.limit, payload.exclude)
    elif mode == "listen":
        result = service.custom_listen(conn, payload.subjects, payload.chapters,
                                       payload.limit, payload.exclude)
    else:
        raise HTTPException(400, "mode 只能是 memo / listen")
    return {"mode": mode, **result}


@router.get("/stats/today")
def stats(conn=Depends(db.get_db)):
    return service.today_summary(conn)


@router.get("/stats/timeline")
def timeline(sid: str | None = None, days: int = 21, conn=Depends(db.get_db)):
    return progress.timeline(conn, sid, days)


@router.get("/stats/forecast")
def forecast(conn=Depends(db.get_db)):
    return service.forecast(conn)


@router.get("/stats/progress")
def progress_stats(sid: str | None = None, conn=Depends(db.get_db)):
    return service.progress_stats(conn, sid)


@router.post("/progress/point")
def mark_point(payload: PointIn, conn=Depends(db.get_db)):
    service.mark_read(conn, payload.point_id)
    return {"ok": True}


@router.post("/progress/listen")
def mark_listen(payload: ListenIn, conn=Depends(db.get_db)):
    if payload.card_id:
        service.mark_card_listened(conn, payload.card_id)
    elif payload.point_id:
        service.mark_listened(conn, payload.point_id)
    else:
        raise HTTPException(400, "card_id 或 point_id 至少给一个")
    return {"ok": True}


@router.post("/progress/unit")
def mark_unit(payload: UnitIn, conn=Depends(db.get_db)):
    service.mark_unit(conn, payload.point_id, payload.idx)
    return {"ok": True}


@router.post("/progress/card")
def grade(payload: CardIn, conn=Depends(db.get_db)):
    try:
        state = service.grade_card(conn, payload.card_id, payload.result)
    except KeyError:
        raise HTTPException(404, "卡片不存在")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return state
