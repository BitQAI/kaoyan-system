"""清理指向已删除内容的运行时记录。

内容表（point/card）由 import_meta.py 全量重建；上游删掉的点与卡会在进度、
事件、收藏里留下悬空引用，统计与预测仍会把它们算进去。本脚本按现存内容裁剪。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402

BY_CARD = ("card_progress", "card_listen", "card_event", "listen_event")
BY_POINT = ("point_progress", "unit_progress", "listen_progress")


def prune(conn) -> dict[str, int]:
    removed = {}
    for table in BY_CARD:
        cur = conn.execute(
            f"DELETE FROM {table} WHERE card_id NOT IN (SELECT card_id FROM card)")
        removed[table] = cur.rowcount
    for table in BY_POINT:
        cur = conn.execute(
            f"DELETE FROM {table} WHERE point_id NOT IN (SELECT id FROM point)")
        removed[table] = cur.rowcount
    cur = conn.execute(
        "DELETE FROM favorites WHERE (kind = 'card' "
        "AND ref_id NOT IN (SELECT card_id FROM card)) OR (kind = 'point' "
        "AND ref_id NOT IN (SELECT id FROM point))")
    removed["favorites"] = cur.rowcount
    conn.commit()
    return removed


if __name__ == "__main__":
    conn = db.connect(config.DB_PATH)
    print(prune(conn))
    conn.close()
