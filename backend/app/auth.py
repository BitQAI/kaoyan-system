"""单用户登录：账号密码 + 记住我（HMAC 签名令牌，服务端无会话表）。

凭据首次启动时自动生成，落在 settings 表；也可用 KY_AUTH_USER / KY_AUTH_PASS 预设。
密码只存 PBKDF2 派生值，令牌用服务器私钥签名，改密即失效。
"""
import base64
import hashlib
import hmac
import json
import secrets
import time

from app import config

KEY = "auth"
ROUNDS = 120_000
REMEMBER_TTL = 30 * 24 * 3600
SHORT_TTL = 12 * 3600


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                               ROUNDS).hex()


def _load(conn) -> dict | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (KEY,)).fetchone()
    return json.loads(row["value"]) if row else None


def _save(conn, data: dict) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (KEY, json.dumps(data)))
    conn.commit()


def ensure_credentials(conn) -> dict | None:
    """首次调用时创建凭据。返回 {"user","password"}（仅在新建时返回明文）。"""
    data = _load(conn)
    if data:
        return None
    user = config.AUTH_USER or "kaoyan"
    password = config.AUTH_PASS or secrets.token_urlsafe(9)
    salt = secrets.token_hex(16)
    data = {"user": user, "salt": salt, "hash": _hash(password, salt),
            "secret": secrets.token_hex(32),
            "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _save(conn, data)
    return {"user": user, "password": password}


def verify_password(conn, user: str, password: str) -> bool:
    data = _load(conn)
    if not data or not user or not password:
        return False
    if not hmac.compare_digest(user, data["user"]):
        return False
    return hmac.compare_digest(_hash(password, data["salt"]), data["hash"])


def change_password(conn, user: str, old: str, new: str) -> bool:
    if not verify_password(conn, user, old) or len(new) < 6:
        return False
    data = _load(conn) or {}
    salt = secrets.token_hex(16)
    data.update({"salt": salt, "hash": _hash(new, salt),
                 "secret": secrets.token_hex(32)})  # 换私钥=旧令牌全部失效
    _save(conn, data)
    return True


def _secret(conn) -> str:
    data = _load(conn)
    return data["secret"] if data else ""


def issue_token(conn, user: str, remember: bool) -> str:
    ttl = REMEMBER_TTL if remember else SHORT_TTL
    payload = f"{user}:{int(time.time()) + ttl}"
    raw = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(_secret(conn).encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def verify_token(conn, token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    raw, _, sig = token.rpartition(".")
    expect = hmac.new(_secret(conn).encode(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expect):
        return None
    try:
        payload = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
        user, exp = payload.rsplit(":", 1)
        if int(exp) < time.time():
            return None
        return user
    except (ValueError, UnicodeDecodeError):
        return None


def token_from_header(value: str | None) -> str | None:
    if not value:
        return None
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return None
