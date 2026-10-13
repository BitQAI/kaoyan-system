import os
import pathlib
from dataclasses import dataclass
from functools import lru_cache

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    p = pathlib.Path(os.environ.get("KY_ENV_FILE") or (ROOT / ".env"))
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    password_hash: str
    session_secret: str
    ai_provider: str
    opencode_key: str
    opencode_base: str
    bailian_key: str
    bailian_base: str
    db_path: str
    content_dir: str
    data_dir: str
    token_days: int = 90


@lru_cache
def get_settings() -> Settings:
    _load_dotenv()
    return Settings(
        password_hash=os.environ.get("KY_PASSWORD_HASH", ""),
        session_secret=os.environ.get("KY_SESSION_SECRET", "dev-secret-change-me"),
        ai_provider=os.environ.get("AI_PROVIDER", "opencode"),
        opencode_key=os.environ.get("OPENCODE_GO_KEY", ""),
        opencode_base=os.environ.get("OPENCODE_GO_BASE", "https://opencode.ai/zen/go/v1"),
        bailian_key=os.environ.get("BAILIAN_KEY", ""),
        bailian_base=os.environ.get("BAILIAN_BASE", ""),
        db_path=os.environ.get("KY_DB_PATH", str(ROOT / "data" / "kaoyan.db")),
        content_dir=os.environ.get("KY_CONTENT_DIR", str(ROOT / "content")),
        data_dir=os.environ.get("KY_DATA_DIR", str(ROOT / "data")),
    )
