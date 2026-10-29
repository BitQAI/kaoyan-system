"""收藏夹与错题本。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import db, service

router = APIRouter(prefix="/api", tags=["study"])


class FavIn(BaseModel):
    kind: str
    ref_id: str
    on: bool = True


@router.get("/favorites")
def favorites(kind: str | None = None, sid: str | None = None,
              conn=Depends(db.get_db)):
    return {"items": service.list_favorites(conn, kind, sid),
            "ids": service.favorite_map(conn)}


@router.post("/favorites")
def set_favorite(payload: FavIn, conn=Depends(db.get_db)):
    try:
        service.set_favorite(conn, payload.kind, payload.ref_id, payload.on)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "ids": service.favorite_map(conn)}


@router.get("/review/weak")
def weak(sid: str | None = None, limit: int = 100, conn=Depends(db.get_db)):
    return {"items": service.weak_cards(conn, sid, limit),
            "counts": service.weak_counts(conn, sid)}
