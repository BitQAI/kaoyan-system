import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import db
from app.config import get_settings
from app.routers import (ai_router, auth_router, content_router, media_state_router,
                         plan_router, progress_router, quiz_router, settings_router)

WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="kaoyan-system", lifespan=lifespan)
app.include_router(auth_router.router)
app.include_router(content_router.router)
app.include_router(progress_router.router)
app.include_router(media_state_router.router)
app.include_router(quiz_router.router)
app.include_router(plan_router.router)
app.include_router(settings_router.router)
app.include_router(ai_router.router)


@app.get("/api/health")
def health():
    return {"ok": True}


_content_dir = pathlib.Path(get_settings().content_dir)
app.mount("/audio", StaticFiles(directory=_content_dir / "audio", check_dir=False), name="audio")
app.mount("/media", StaticFiles(directory=_content_dir / "media", check_dir=False), name="media")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
