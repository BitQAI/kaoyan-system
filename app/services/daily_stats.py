"""daily_log 计数的共用入口（quiz / cards / review 各模块调用）。"""
import datetime


def bump_daily(con, col: str, n: int = 1) -> None:
    today = datetime.date.today().isoformat()
    con.execute(f"INSERT INTO daily_log(date, {col}) VALUES(?,?) "
                f"ON CONFLICT(date) DO UPDATE SET {col} = daily_log.{col} + excluded.{col}",
                (today, n))
