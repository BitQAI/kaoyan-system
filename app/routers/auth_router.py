from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app import auth
from app.config import get_settings

router = APIRouter(prefix="/api")


class LoginBody(BaseModel):
    password: str


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response):
    ip = _client_ip(request)
    wait = auth.login_allowed(ip)
    if wait > 0:
        raise HTTPException(status_code=429, detail="too_many_attempts",
                            headers={"Retry-After": str(wait)})
    s = get_settings()
    if not auth.verify_password(body.password, s.password_hash):
        auth.record_login_fail(ip)
        raise HTTPException(status_code=401, detail="bad_password")
    auth.clear_login_fails(ip)
    token = auth.create_token(s.session_secret, days=s.token_days)
    secure = request.url.scheme == "https" or \
        request.headers.get("x-forwarded-proto", "").lower() == "https"
    response.set_cookie(auth.COOKIE, token, max_age=s.token_days * 86400,
                        httponly=True, samesite="lax", path="/", secure=secure)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request, _: None = Depends(auth.require_auth)):
    return {"ok": True, "expires_at": auth.token_exp(request.cookies.get(auth.COOKIE, ""))}
