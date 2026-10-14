import datetime
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import auth, content, db
from app.services import progress_engine, review_engine

router = APIRouter(prefix="/api", dependencies=[Depends(auth.require_auth)])

State = Literal["new", "listened", "half", "known", "review"]


class ProgressBody(BaseModel):
    point_id: str
    state: State


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _states(con: sqlite3.Connection) -> dict:
    return {r["point_id"]: r["state"] for r in con.execute("SELECT point_id, state FROM progress")}


def _unit_states(con: sqlite3.Connection) -> dict:
    return {f"{r['point_id']}#{r['idx']}": r["state"]
            for r in con.execute("SELECT point_id, idx, state FROM unit_progress")}


@router.get("/progress")
def get_progress(con: sqlite3.Connection = Depends(db.get_db)):
    states = _states(con)
    try:
        reports = progress_engine.compute_all(content.load_content(), states)
    except content.ContentMissing:
        reports = []
    return {"states": states, "unit_states": _unit_states(con), "reports": reports}


class UnitBody(BaseModel):
    point_id: str
    idx: int
    state: State


def _recompute_point_state(con: sqlite3.Connection, point_id: str) -> None:
    """细项状态变化后汇总考点状态：全会→known；有不会→review；有半会/部分→half；全清→删除。"""
    rows = con.execute("SELECT idx, state FROM unit_progress WHERE point_id = ?",
                       (point_id,)).fetchall()
    states = {r["idx"]: r["state"] for r in rows}
    try:
        found = content.find_point(content.load_content(), point_id)
        total = len((found[2].get("units") or [])) if found else 0
    except content.ContentMissing:
        total = 0
    if not states:
        new_state = "new"
    elif total and len(states) >= total and set(states.values()) == {"known"}:
        new_state = "known"
    elif "review" in states.values():
        new_state = "review"
    elif "half" in states.values():
        new_state = "half"
    elif "known" in states.values():
        new_state = "half"            # 部分已会 → 视为半会待复习
    else:
        new_state = "new"
    if new_state == "new":
        con.execute("DELETE FROM progress WHERE point_id = ?", (point_id,))
    else:
        con.execute(
            "INSERT INTO progress(point_id, state, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(point_id) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at",
            (point_id, new_state, _now()))
    con.commit()
    review_engine.on_state_change(con, point_id, new_state)


@router.post("/unit_progress")
def set_unit_progress(body: UnitBody, con: sqlite3.Connection = Depends(db.get_db)):
    if body.state == "new":
        con.execute("DELETE FROM unit_progress WHERE point_id = ? AND idx = ?",
                    (body.point_id, body.idx))
    else:
        con.execute(
            "INSERT INTO unit_progress(point_id, idx, state, updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(point_id, idx) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at",
            (body.point_id, body.idx, body.state, _now()))
    con.commit()
    _recompute_point_state(con, body.point_id)
    return {"ok": True, "point_state": _states(con).get(body.point_id, "new")}


@router.post("/progress")
def set_progress(body: ProgressBody, con: sqlite3.Connection = Depends(db.get_db)):
    if body.state == "new":
        con.execute("DELETE FROM progress WHERE point_id = ?", (body.point_id,))
    else:
        con.execute(
            "INSERT INTO progress(point_id, state, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(point_id) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at",
            (body.point_id, body.state, _now()),
        )
    con.commit()
    review_engine.on_state_change(con, body.point_id, body.state)
    return {"ok": True}


@router.get("/reviews/due")
def reviews_due(con: sqlite3.Connection = Depends(db.get_db)):
    rows = con.execute(
        "SELECT point_id, stage, due_date FROM reviews "
        "WHERE due_date <= date('now', 'localtime') ORDER BY due_date, point_id").fetchall()
    return {"items": [dict(r) for r in rows]}


@router.post("/reviews/{point_id}/advance")
def review_advance(point_id: str, con: sqlite3.Connection = Depends(db.get_db)):
    con.execute(
        "INSERT INTO progress(point_id, state, updated_at) VALUES(?, 'known', ?) "
        "ON CONFLICT(point_id) DO UPDATE SET state='known', updated_at=excluded.updated_at",
        (point_id, _now()))
    con.commit()
    review_engine.advance(con, point_id)
    return {"ok": True}
