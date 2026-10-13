from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db
from app.routers import (ai_router, auth_router, content_router, media_state_router,
                         plan_router, progress_router, quiz_router, settings_router)


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
