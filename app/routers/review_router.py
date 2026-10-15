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


def _csv(s: str | None) -> list | None:
    items = [x.strip() for x in (s or "").split(",") if x.strip()]
    return items or None


@router.get("/memo/queue")
def memo_queue_api(quick: str = "due", subjects: str | None = None, chapters: str | None = None,
                   points: str | None = None, filter: str | None = None,
                   con: sqlite3.Connection = Depends(db.get_db)):
    if quick not in ("due", "today_look", "fav", "hot"):
        raise HTTPException(status_code=422, detail="bad_quick")
    data = content.load_content()
    look_points = None
    if quick == "today_look":
        states = {r["point_id"]: r["state"] for r in
                  con.execute("SELECT point_id, state FROM progress")}
        wrong = {r["quiz_id"] for r in
                 con.execute("SELECT quiz_id FROM wrong_book WHERE resolved_at IS NULL")}
        look_points = plan_engine.build_plan(data, states, wrong,
                                             settings_store.load(con))["look"]
    return unit_review_engine.memo_queue(
        con, data, settings_store.review_n(con), quick=quick,
        subjects=_csv(subjects), chapters=_csv(chapters), points=_csv(points),
        filter=_csv(filter), look_points=look_points)


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
    data = content.load_content()
    if not content.find_card(data, body.card_id):
        raise HTTPException(status_code=404, detail="card_not_found")
    tier = content.card_tier_map(data).get(body.card_id, 3)
    k = unit_review_engine.target_k("card", tier)
    r = unit_review_engine.rate_card(con, body.card_id, body.rating, k)
    daily_stats.bump_daily(con, "cards")
    con.commit()
    return {"ok": True,
            "next": unit_review_engine.next_intervals(r["stage"], k,
                                                      plan_engine.days_left(), body.card_id)}


@router.post("/unit_review")
def unit_review(body: UnitReviewBody, con: sqlite3.Connection = Depends(db.get_db)):
    found = content.find_point(content.load_content(), body.point_id)
    if not found:
        raise HTTPException(status_code=404, detail="point_not_found")
    _, chap, point = found
    k = unit_review_engine.target_k("unit", chap.get("tier", 3))
    total = len(point.get("units") or [])
    idxs = list(range(total)) if body.all else ([body.idx] if body.idx is not None else [])
    if not idxs:
        raise HTTPException(status_code=422, detail="idx_required")
    if any(i < 0 or i >= total for i in idxs):
        raise HTTPException(status_code=422, detail="idx_out_of_range")

    last = None
    for i in idxs:
        last = unit_review_engine.rate(con, body.point_id, i, body.rating, k)
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
            "next": unit_review_engine.next_intervals(
                last["stage"], k, plan_engine.days_left(),
                unit_review_engine.unit_key(body.point_id, idxs[-1]))}
