import datetime
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import auth, content, db
from app.services import progress_engine

router = APIRouter(prefix="/api", dependencies=[Depends(auth.require_auth)])

State = Literal["new", "listened", "half", "known", "review"]


class ProgressBody(BaseModel):
    point_id: str
    state: State


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _states(con: sqlite3.Connection) -> dict:
    return {r["point_id"]: r["state"] for r in con.execute("SELECT point_id, state FROM progress")}


@router.get("/progress")
def get_progress(con: sqlite3.Connection = Depends(db.get_db)):
    states = _states(con)
    try:
        reports = progress_engine.compute_all(content.load_content(), states)
    except content.ContentMissing:
        reports = []
    return {"states": states, "reports": reports}


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
    return {"ok": True}
