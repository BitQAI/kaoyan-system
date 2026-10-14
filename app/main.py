import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app import db
from app.config import get_settings
from app.routers import (ai_router, auth_router, content_router, exam_router, media_state_router,
                         plan_router, progress_router, quiz_router, settings_router, stats_router)

WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="kaoyan-system", lifespan=lifespan)


class _NoStoreStatic(BaseHTTPMiddleware):
    """静态前端资源禁用 HTTP 缓存（SW 已负责离线缓存；避免改版后拿到旧 JS）。"""

    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        if request.url.path.startswith(("/js/", "/vendor/")) or \
                request.url.path in ("/app.css", "/sw.js", "/manifest.json"):
            resp.headers["Cache-Control"] = "no-store"
        return resp


app.add_middleware(_NoStoreStatic)
app.include_router(auth_router.router)
app.include_router(content_router.router)
app.include_router(progress_router.router)
app.include_router(media_state_router.router)
app.include_router(quiz_router.router)
app.include_router(exam_router.router)
app.include_router(stats_router.router)
app.include_router(plan_router.router)
app.include_router(settings_router.router)
app.include_router(ai_router.router)


@app.get("/api/health")
def health():
    return {"ok": True}


_content_dir = pathlib.Path(get_settings().content_dir)
app.mount("/audio", StaticFiles(directory=_content_dir / "audio", check_dir=False), name="audio")
app.mount("/media", StaticFiles(directory=_content_dir / "media", check_dir=False), name="media")
app.mount("/media-private", StaticFiles(directory=_content_dir / "media-private", check_dir=False),
          name="media-private")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
