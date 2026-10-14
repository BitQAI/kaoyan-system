import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException, Request

from app.config import get_settings

COOKIE = "ky_session"
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1

# ---- 登录失败限速（进程级内存，单进程个人应用足够）----
_FAIL_WINDOW = 900          # 15 分钟
_MAX_FAILS = 5
_fails: dict[str, list[float]] = {}


def login_allowed(ip: str, now: float | None = None) -> int:
    """允许返回 0；被锁返回还需等待的秒数（并顺带清理过期记录）。"""
    t = now if now is not None else time.time()
    arr = [x for x in _fails.get(ip, []) if t - x < _FAIL_WINDOW]
    _fails[ip] = arr
    if len(arr) >= _MAX_FAILS:
        return int(_FAIL_WINDOW - (t - arr[0])) + 1
    return 0


def record_login_fail(ip: str, now: float | None = None) -> None:
    _fails.setdefault(ip, []).append(now if now is not None else time.time())


def clear_login_fails(ip: str) -> None:
    _fails.pop(ip, None)


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt_hex),
                            n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_token(secret: str, days: int = 90, now: int | None = None) -> str:
    exp = int(now if now is not None else time.time()) + days * 86400
    payload = _b64e(json.dumps({"exp": exp}).encode())
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_token(token: str, secret: str, now: int | None = None) -> bool:
    try:
        payload, sig = token.split(".")
        expect = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            return False
        exp = json.loads(_b64d(payload))["exp"]
        return int(now if now is not None else time.time()) <= exp
    except (ValueError, KeyError, json.JSONDecodeError):
        return False


def token_exp(token: str) -> int | None:
    try:
        return int(json.loads(_b64d(token.split(".")[0]))["exp"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def require_auth(request: Request) -> None:
    s = get_settings()
    token = request.cookies.get(COOKIE, "")
    if not s.password_hash or not verify_token(token, s.session_secret):
        raise HTTPException(status_code=401, detail="unauthorized")
