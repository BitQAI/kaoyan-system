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
    con.commit()
    con.close()


def get_db():
    con = connect()
    try:
        yield con
    finally:
        con.close()
