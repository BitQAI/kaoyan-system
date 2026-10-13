import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import auth, db, settings_store
from app.config import get_settings

router = APIRouter(prefix="/api", dependencies=[Depends(auth.require_auth)])


class PasswordBody(BaseModel):
    old: str
    new: str


@router.get("/settings")
def get_settings_api(con: sqlite3.Connection = Depends(db.get_db)):
    return settings_store.load(con)


@router.post("/settings")
def post_settings(patch: dict, con: sqlite3.Connection = Depends(db.get_db)):
    return settings_store.save(con, patch)


@router.post("/settings/password")
def change_password(body: PasswordBody):
    s = get_settings()
    if not auth.verify_password(body.old, s.password_hash):
        raise HTTPException(status_code=401, detail="bad_password")
    if len(body.new) < 6:
        raise HTTPException(status_code=422, detail="too_short")
    settings_store.write_env_kv("KY_PASSWORD_HASH", auth.hash_password(body.new))
    return {"ok": True, "note": "已写入 .env，重启服务后生效"}
