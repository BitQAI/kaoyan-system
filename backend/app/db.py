"""SQLite 连接与建表。

运行时一律用原生 sqlite3（数据量小，ORM 是纯负担）；表结构以 models.py 为准。
"""
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine

from app import config, models

#: FTS5 虚拟表：Table 表达不了，单独建；Alembic 的 include_object 已忽略它们
FTS_SQL = [
    """CREATE VIRTUAL TABLE IF NOT EXISTS point_fts USING fts5(
           point_id UNINDEXED, title, point, keywords, explain,
           tokenize='trigram')""",
    """CREATE VIRTUAL TABLE IF NOT EXISTS card_fts USING fts5(
           card_id UNINDEXED, point_id UNINDEXED, question, answer, answer_points,
           tokenize='trigram')""",
]


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    target = Path(path or config.DB_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    """按 models.py 建全部表 + FTS 索引（幂等）。"""
    engine = create_engine(f"sqlite:///{_db_path(conn)}")
    models.metadata.create_all(engine)
    engine.dispose()
    for sql in FTS_SQL:
        conn.execute(sql)
    conn.commit()


def _db_path(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA database_list").fetchone()
    return row["file"] or ":memory:"


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM point_fts")
    conn.execute(
        "INSERT INTO point_fts (point_id, title, point, keywords, explain) "
        "SELECT id, title, point, keywords, explain FROM point"
    )
    conn.execute("DELETE FROM card_fts")
    conn.execute(
        "INSERT INTO card_fts (card_id, point_id, question, answer, answer_points) "
        "SELECT card_id, point_id, question, answer, answer_points FROM card"
    )
    conn.commit()
