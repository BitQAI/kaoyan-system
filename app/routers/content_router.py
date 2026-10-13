from fastapi import APIRouter, Depends, HTTPException

from app import auth, content

router = APIRouter(prefix="/api", dependencies=[Depends(auth.require_auth)])


@router.get("/content")
def get_content():
    try:
        return content.load_content()
    except content.ContentMissing:
        raise HTTPException(status_code=503, detail="content_missing")
