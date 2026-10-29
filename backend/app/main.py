from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import auth, db
from app.routers import (assistant, auth as auth_router, content, progress,
                         study)

app = FastAPI(title="考研学习应用")

# 开发期前端跑在 :3000，生产由 nginx 同源代理
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"http://192\.168\.\d+\.\d+:3000",
    allow_methods=["*"],
    allow_headers=["*"],
)

#: 免登录的接口：健康检查与登录本身
OPEN_PATHS = {"/api/health", "/api/auth/login"}


@app.middleware("http")
async def auth_guard(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in OPEN_PATHS:
        conn = db.connect()
        try:
            user = auth.verify_token(
                conn, auth.token_from_header(request.headers.get("authorization")))
        finally:
            conn.close()
        if not user:
            return JSONResponse({"detail": "未登录"}, status_code=401)
    return await call_next(request)


app.include_router(auth_router.router)
app.include_router(content.router)
app.include_router(progress.router)
app.include_router(study.router)
app.include_router(assistant.router)
