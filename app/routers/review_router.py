"""V3 单元级复习：队列与三档评分。"""
import datetime
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import auth, content, db, settings_store
from app.services import daily_stats, plan_engine, progress_engine, unit_review_engine

router = APIRouter(prefix="/api", dependencies=[Depends(auth.require_auth)])

STATE_OF_RATING = {"again": "review", "hard": "half", "good": "known"}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@router.get("/review/queue")
def review_queue(point: str | None = None, con: sqlite3.Connection = Depends(db.get_db)):
    return unit_review_engine.queue(con, content.load_content(), settings_store.review_n(con),
                                    point_id=point)


class UnitReviewBody(BaseModel):
    point_id: str
    rating: Literal["again", "hard", "good"]
    idx: int | None = None
    all: bool = False


class CardReviewBody(BaseModel):
    card_id: str
    rating: Literal["again", "hard", "good"]


@router.post("/card_review")
def card_review(body: CardReviewBody, con: sqlite3.Connection = Depends(db.get_db)):
    if not content.find_card(content.load_content(), body.card_id):
        raise HTTPException(status_code=404, detail="card_not_found")
    r = unit_review_engine.rate_card(con, body.card_id, body.rating)
    daily_stats.bump_daily(con, "cards")
    con.commit()
    return {"ok": True,
            "next": unit_review_engine.next_intervals(r["stage"], plan_engine.days_left())}


@router.post("/unit_review")
def unit_review(body: UnitReviewBody, con: sqlite3.Connection = Depends(db.get_db)):
    found = content.find_point(content.load_content(), body.point_id)
    if not found:
        raise HTTPException(status_code=404, detail="point_not_found")
    total = len(found[2].get("units") or [])
    idxs = list(range(total)) if body.all else ([body.idx] if body.idx is not None else [])
    if not idxs:
        raise HTTPException(status_code=422, detail="idx_required")
    if any(i < 0 or i >= total for i in idxs):
        raise HTTPException(status_code=422, detail="idx_out_of_range")

    last = None
    for i in idxs:
        last = unit_review_engine.rate(con, body.point_id, i, body.rating)
        con.execute(
            "INSERT INTO unit_progress(point_id, idx, state, updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(point_id, idx) DO UPDATE SET state=excluded.state, "
            "updated_at=excluded.updated_at",
            (body.point_id, i, STATE_OF_RATING[body.rating], _now()))
        con.execute("INSERT INTO unit_ratings(point_id, idx, rating, ts) VALUES(?,?,?,?)",
                    (body.point_id, i, body.rating, _now()))
    daily_stats.bump_daily(con, "review_n", len(idxs))
    con.commit()
    progress_engine.recompute_point_state(con, body.point_id)
    state = con.execute("SELECT state FROM progress WHERE point_id = ?",
                        (body.point_id,)).fetchone()
    return {"ok": True, "point_state": state["state"] if state else "new",
            "next": unit_review_engine.next_intervals(last["stage"], plan_engine.days_left())}
