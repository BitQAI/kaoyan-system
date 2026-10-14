import pathlib
import sqlite3

from app.config import get_settings

SCHEMA = pathlib.Path(__file__).parent / "schema.sql"


def connect(path: str | None = None) -> sqlite3.Connection:
    p = pathlib.Path(path or get_settings().db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db() -> None:
    con = connect()
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    # 幂等迁移：老库补列（SQLite 无 IF NOT EXISTS ADD COLUMN）
    cols = {r["name"] for r in con.execute("PRAGMA table_info(quiz_attempts)")}
    if "response" not in cols:
        con.execute("ALTER TABLE quiz_attempts ADD COLUMN response TEXT")
    con.commit()
    con.close()


def get_db():
    con = connect()
    try:
        yield con
    finally:
        con.close()
