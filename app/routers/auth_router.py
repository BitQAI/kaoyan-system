from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app import auth
from app.config import get_settings

router = APIRouter(prefix="/api")


class LoginBody(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginBody, response: Response):
    s = get_settings()
    if not auth.verify_password(body.password, s.password_hash):
        raise HTTPException(status_code=401, detail="bad_password")
    token = auth.create_token(s.session_secret, days=s.token_days)
    response.set_cookie(auth.COOKIE, token, max_age=s.token_days * 86400,
                        httponly=True, samesite="lax", path="/")
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request, _: None = Depends(auth.require_auth)):
    return {"ok": True, "expires_at": auth.token_exp(request.cookies.get(auth.COOKIE, ""))}
