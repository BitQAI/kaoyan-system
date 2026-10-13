import datetime
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import auth, db

router = APIRouter(prefix="/api", dependencies=[Depends(auth.require_auth)])


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class AudioPosBody(BaseModel):
    clip_id: str
    position_sec: float
    plays_delta: int = 0


class FavoriteBody(BaseModel):
    type: Literal["point", "quiz", "card", "clip"]
    ref_id: str
    action: Literal["add", "remove"]


@router.post("/audio_pos")
def post_audio_pos(body: AudioPosBody, con: sqlite3.Connection = Depends(db.get_db)):
    con.execute(
        "INSERT INTO audio_pos(clip_id, position_sec, plays, last_at) VALUES(?,?,?,?) "
        "ON CONFLICT(clip_id) DO UPDATE SET "
        "position_sec = MAX(audio_pos.position_sec, excluded.position_sec), "
        "plays = audio_pos.plays + excluded.plays, "
        "last_at = excluded.last_at",
        (body.clip_id, max(0.0, body.position_sec), max(0, body.plays_delta), _now()),
    )
    con.commit()
    return {"ok": True}


@router.get("/audio_pos")
def get_audio_pos(con: sqlite3.Connection = Depends(db.get_db)):
    return {r["clip_id"]: {"position_sec": r["position_sec"], "plays": r["plays"]}
            for r in con.execute("SELECT clip_id, position_sec, plays FROM audio_pos")}


@router.post("/favorite")
def post_favorite(body: FavoriteBody, con: sqlite3.Connection = Depends(db.get_db)):
    if body.action == "add":
        con.execute("INSERT OR IGNORE INTO favorites(type, ref_id, created_at) VALUES(?,?,?)",
                    (body.type, body.ref_id, _now()))
    else:
        con.execute("DELETE FROM favorites WHERE type = ? AND ref_id = ?", (body.type, body.ref_id))
    con.commit()
    return {"ok": True}


@router.get("/favorites")
def get_favorites(con: sqlite3.Connection = Depends(db.get_db)):
    out: dict[str, list[str]] = {"point": [], "quiz": [], "card": [], "clip": []}
    for r in con.execute("SELECT type, ref_id FROM favorites ORDER BY created_at"):
        out[r["type"]].append(r["ref_id"])
    return out
