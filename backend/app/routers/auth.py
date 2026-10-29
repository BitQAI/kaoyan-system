"""登录、登出、改密。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app import auth, db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str
    remember: bool = True


class PasswordIn(BaseModel):
    old_password: str
    new_password: str


@router.post("/login")
def login(payload: LoginIn, conn=Depends(db.get_db)):
    if not auth.verify_password(conn, payload.username.strip(), payload.password):
        raise HTTPException(401, "账号或密码不对")
    token = auth.issue_token(conn, payload.username.strip(), payload.remember)
    return {"token": token, "user": payload.username.strip(),
            "expires_days": 30 if payload.remember else 0.5}


@router.get("/me")
def me(request: Request, conn=Depends(db.get_db)):
    token = auth.token_from_header(request.headers.get("authorization"))
    user = auth.verify_token(conn, token)
    if not user:
        raise HTTPException(401, "未登录")
    return {"user": user}


@router.post("/password")
def change_password(payload: PasswordIn, request: Request, conn=Depends(db.get_db)):
    token = auth.token_from_header(request.headers.get("authorization"))
    user = auth.verify_token(conn, token)
    if not user:
        raise HTTPException(401, "未登录")
    if not auth.change_password(conn, user, payload.old_password, payload.new_password):
        raise HTTPException(400, "原密码不对，或新密码少于 6 位")
    return {"token": auth.issue_token(conn, user, True)}
