"""间隔重复复习调度（简版遗忘曲线，3 阶段毕业）。

规则：half/review → 建档 stage0（+1 天）；known 有记录 → advance（0→1 +7 天、
1→2 +15 天、2→毕业删除）；known 无记录 → 建 stage1（+3 天）；new → 删除。
日期一律为本地日期 ISO 字符串，due 比较为字符串 <=。
"""
import datetime


def _today(today: str | None) -> str:
    return today or datetime.date.today().isoformat()


def _plus(today: str, days: int) -> str:
    return (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()


def schedule(con, point_id: str, today: str | None = None) -> None:
    t = _today(today)
    con.execute(
        "INSERT INTO reviews(point_id, stage, due_date, updated_at) VALUES(?,0,?,?) "
        "ON CONFLICT(point_id) DO UPDATE SET stage=0, due_date=excluded.due_date, "
        "updated_at=excluded.updated_at",
        (point_id, _plus(t, 1), t),
    )
    con.commit()


def advance(con, point_id: str, today: str | None = None) -> None:
    t = _today(today)
    row = con.execute("SELECT stage FROM reviews WHERE point_id = ?", (point_id,)).fetchone()
    if row is None:
        return
    stage = row["stage"] + 1
    if stage >= 3:
        con.execute("DELETE FROM reviews WHERE point_id = ?", (point_id,))
    else:
        days = 7 if stage == 1 else 15
        con.execute("UPDATE reviews SET stage = ?, due_date = ?, updated_at = ? WHERE point_id = ?",
                    (stage, _plus(t, days), t, point_id))
    con.commit()


def on_state_change(con, point_id: str, new_state: str, today: str | None = None) -> None:
    if new_state in ("half", "review"):
        schedule(con, point_id, today)
    elif new_state == "known":
        exists = con.execute("SELECT 1 FROM reviews WHERE point_id = ?", (point_id,)).fetchone()
        if exists:
            advance(con, point_id, today)
        else:
            t = _today(today)
            con.execute("INSERT OR IGNORE INTO reviews(point_id, stage, due_date, updated_at) "
                        "VALUES(?,1,?,?)", (point_id, _plus(t, 3), t))
            con.commit()
    elif new_state == "new":
        con.execute("DELETE FROM reviews WHERE point_id = ?", (point_id,))
        con.commit()


def due_points(con, today: str | None = None) -> list[str]:
    t = _today(today)
    return [r["point_id"] for r in con.execute(
        "SELECT point_id FROM reviews WHERE due_date <= ? ORDER BY due_date, point_id", (t,))]
