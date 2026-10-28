from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import assistant, content, progress

app = FastAPI(title="考研学习应用")

# 开发期前端跑在 :3000，生产由 nginx 同源代理
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"http://192\.168\.\d+\.\d+:3000",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(content.router)
app.include_router(progress.router)
app.include_router(assistant.router)
