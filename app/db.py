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
    _migrate_quiz_attempts(con)
    con.commit()
    con.close()


def _migrate_quiz_attempts(con) -> None:
    """幂等迁移 quiz_attempts：补 response 列；旧库 chosen 为 NOT NULL 时重建表放开。"""
    cols = {r["name"]: r for r in con.execute("PRAGMA table_info(quiz_attempts)")}
    if "response" not in cols:
        con.execute("ALTER TABLE quiz_attempts ADD COLUMN response TEXT")
        cols = {r["name"]: r for r in con.execute("PRAGMA table_info(quiz_attempts)")}
    if cols.get("chosen") is not None and cols["chosen"]["notnull"]:
        con.executescript(
            "ALTER TABLE quiz_attempts RENAME TO quiz_attempts_old;"
            "CREATE TABLE quiz_attempts ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT, quiz_id TEXT NOT NULL,"
            "  chosen INTEGER, correct INTEGER NOT NULL, ts TEXT NOT NULL, response TEXT);"
            "INSERT INTO quiz_attempts(id, quiz_id, chosen, correct, ts, response) "
            "  SELECT id, quiz_id, chosen, correct, ts, response FROM quiz_attempts_old;"
            "DROP TABLE quiz_attempts_old;")


def get_db():
    con = connect()
    try:
        yield con
    finally:
        con.close()
