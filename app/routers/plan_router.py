import datetime
import sqlite3

from fastapi import APIRouter, Depends

from app import auth, content, db, settings_store
from app.services import plan_engine, progress_engine, review_engine, unit_review_engine

router = APIRouter(prefix="/api", dependencies=[Depends(auth.require_auth)])


def _states(con) -> dict:
    return {r["point_id"]: r["state"] for r in con.execute("SELECT point_id, state FROM progress")}


def _wrong_ids(con) -> set:
    return {r["quiz_id"] for r in con.execute(
        "SELECT quiz_id FROM wrong_book WHERE resolved_at IS NULL")}


def _streak(con) -> int:
    dates = {r["date"] for r in con.execute(
        "SELECT date FROM daily_log "
        "WHERE listen_sec > 0 OR clips > 0 OR cards > 0 OR quiz_n > 0 OR review_n > 0")}
    day = datetime.date.today()
    if day.isoformat() not in dates:
        day -= datetime.timedelta(days=1)
    n = 0
    while day.isoformat() in dates:
        n += 1
        day -= datetime.timedelta(days=1)
    return n


@router.get("/plan/today")
def plan_today(con: sqlite3.Connection = Depends(db.get_db)):
    data = content.load_content()
    states = _states(con)
    cfg = settings_store.load(con)
    dl = plan_engine.days_left()
    today = datetime.date.today().isoformat()
    done_today = con.execute(
        "SELECT COUNT(*) AS n FROM progress WHERE updated_at LIKE ?", (today + "%",)).fetchone()["n"]
    logs = [dict(r) for r in con.execute(
        "SELECT date, listen_sec, clips, cards, quiz_n FROM daily_log "
        "ORDER BY date DESC LIMIT 30")]
    due = review_engine.due_points(con)
    q = unit_review_engine.queue(con, data, settings_store.review_n(con))
    return {
        "days_left": dl,
        "plan": plan_engine.build_plan(data, states, _wrong_ids(con), cfg, due_review=set(due)),
        "pace": plan_engine.pace(data, states, days_left=dl, done_today=done_today),
        "logs_30d": logs,
        "reviews_due": len(due),
        "review_points": due[:50],
        "review_units_due": q["due_total"],
        "review_session_est_min": round(q["shown"] * 0.2),
    }


@router.get("/stats")
def stats(con: sqlite3.Connection = Depends(db.get_db)):
    data = content.load_content()
    states = _states(con)
    today = datetime.date.today().isoformat()
    row = con.execute("SELECT listen_sec, clips, cards, quiz_n, review_n FROM daily_log "
                      "WHERE date = ?", (today,)).fetchone()
    return {
        "streak_days": _streak(con),
        "today": dict(row) if row else {"listen_sec": 0, "clips": 0, "cards": 0,
                                        "quiz_n": 0, "review_n": 0},
        "ring": progress_engine.compute_all(data, states),
        "days_left": plan_engine.days_left(),
    }
