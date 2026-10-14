import datetime
import json
import random
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import auth, content, db
from app.services import quiz_grader, review_engine, wrongbook

router = APIRouter(prefix="/api", dependencies=[Depends(auth.require_auth)])


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _wb_row(con, quiz_id: str) -> dict | None:
    r = con.execute("SELECT wrong_count, streak, resolved_at FROM wrong_book WHERE quiz_id = ?",
                    (quiz_id,)).fetchone()
    return dict(r) if r else None


def _wb_upsert(con, quiz_id: str, s: dict) -> None:
    con.execute(
        "INSERT INTO wrong_book(quiz_id, wrong_count, streak, resolved_at, last_wrong_at) "
        "VALUES(?,?,?,?,?) ON CONFLICT(quiz_id) DO UPDATE SET "
        "wrong_count=excluded.wrong_count, streak=excluded.streak, "
        "resolved_at=excluded.resolved_at, last_wrong_at=excluded.last_wrong_at",
        (quiz_id, s["wrong_count"], s["streak"], s["resolved_at"], _now()),
    )


def _bump_daily(con, col: str, n: int = 1) -> None:
    today = datetime.date.today().isoformat()
    con.execute(f"INSERT INTO daily_log(date, {col}) VALUES(?,?) "
                f"ON CONFLICT(date) DO UPDATE SET {col} = daily_log.{col} + excluded.{col}",
                (today, n))


class AttemptBody(BaseModel):
    quiz_id: str
    chosen: int | None = None      # 旧形状（单选中标）
    response: object = None        # 新形状：single=int / multi=list[int] / blank=list[str]


class CardReviewBody(BaseModel):
    card_id: str
    verdict: Literal["know", "fuzzy", "no"]


@router.post("/quiz/attempt")
def attempt(body: AttemptBody, con: sqlite3.Connection = Depends(db.get_db)):
    found = content.find_quiz(content.load_content(), body.quiz_id)
    if not found:
        raise HTTPException(status_code=404, detail="quiz_not_found")
    _, _, quiz = found
    resp = body.response if body.response is not None else body.chosen
    result = quiz_grader.grade(quiz, resp)
    correct = result["correct"]
    chosen_int = resp if isinstance(resp, int) else None
    con.execute("INSERT INTO quiz_attempts(quiz_id, chosen, correct, ts, response) VALUES(?,?,?,?,?)",
                (body.quiz_id, chosen_int, int(correct), _now(),
                 json.dumps(resp, ensure_ascii=False)))
    new_state = wrongbook.apply_attempt(_wb_row(con, body.quiz_id), correct, _now())
    if new_state is not None:
        _wb_upsert(con, body.quiz_id, new_state)
    if not correct and quiz.get("point_id"):
        review_engine.schedule(con, quiz["point_id"])
    _bump_daily(con, "quiz_n")
    con.commit()
    return {"correct": correct, "explain": quiz.get("explain", ""), "answer": result["answer"]}


@router.get("/quiz/wrong")
def wrong_list(con: sqlite3.Connection = Depends(db.get_db)):
    items = []
    for r in con.execute("SELECT quiz_id, wrong_count, streak, last_wrong_at FROM wrong_book "
                         "WHERE resolved_at IS NULL ORDER BY last_wrong_at DESC"):
        found = content.find_quiz(content.load_content(), r["quiz_id"])
        if not found:
            continue
        _, _, quiz = found
        last = con.execute("SELECT chosen FROM quiz_attempts WHERE quiz_id = ? AND correct = 0 "
                           "ORDER BY ts DESC LIMIT 1", (r["quiz_id"],)).fetchone()
        items.append({**quiz, "wrong_count": r["wrong_count"], "last_chosen": last["chosen"] if last else None})
    return {"items": items}


@router.get("/quiz/run")
def quiz_run(mode: Literal["chapter", "wrong", "favorites"], chapter: str | None = None,
             n: int = 15, con: sqlite3.Connection = Depends(db.get_db)):
    data = content.load_content()
    if mode == "chapter":
        items = [q for _, ch in content.iter_chapters(data)
                 if (chapter is None or ch["id"] == chapter)
                 for q in ch.get("quiz", [])]
    elif mode == "wrong":
        ids = {r["quiz_id"] for r in con.execute(
            "SELECT quiz_id FROM wrong_book WHERE resolved_at IS NULL")}
        items = [q for _, ch in content.iter_chapters(data) for q in ch.get("quiz", []) if q["id"] in ids]
    else:
        ids = {r["ref_id"] for r in con.execute(
            "SELECT ref_id FROM favorites WHERE type = 'quiz'")}
        items = [q for _, ch in content.iter_chapters(data) for q in ch.get("quiz", []) if q["id"] in ids]
    random.shuffle(items)
    return {"items": items[:n]}


@router.post("/cards/review")
def card_review(body: CardReviewBody, con: sqlite3.Connection = Depends(db.get_db)):
    found = content.find_card(content.load_content(), body.card_id)
    if not found:
        raise HTTPException(status_code=404, detail="card_not_found")
    _, _, card = found
    state = {"know": "known", "fuzzy": "half", "no": "review"}[body.verdict]
    point_id = card.get("point_id")
    if point_id:
        con.execute(
            "INSERT INTO progress(point_id, state, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(point_id) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at",
            (point_id, state, _now()))
        review_engine.on_state_change(con, point_id, state)
    _bump_daily(con, "cards")
    con.commit()
    return {"ok": True, "point_state": state}
