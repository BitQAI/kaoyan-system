import datetime
import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import auth, content, db
from app.services import exam_engine

router = APIRouter(prefix="/api", dependencies=[Depends(auth.require_auth)])


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class NewExamBody(BaseModel):
    subject: str
    kind: str = "objective"


class SubmitBody(BaseModel):
    exam_id: str
    responses: list[dict] = []
    verdicts: list[dict] = []


@router.post("/exam/new")
def new_exam(body: NewExamBody, con: sqlite3.Connection = Depends(db.get_db)):
    if (body.subject, body.kind) not in exam_engine.PAPERS:
        raise HTTPException(status_code=422, detail="unsupported_paper")
    paper = exam_engine.assemble(content.load_content(), body.subject, body.kind)
    con.execute("INSERT INTO exam_runs(id, subject, kind, started_at, finished_at, detail_json, score, total) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (paper["exam_id"], body.subject, body.kind, _now(), None,
                 json.dumps(paper, ensure_ascii=False), None, None))
    con.commit()
    return paper


@router.get("/exam/{exam_id}")
def get_exam(exam_id: str, con: sqlite3.Connection = Depends(db.get_db)):
    row = con.execute("SELECT * FROM exam_runs WHERE id = ?", (exam_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="exam_not_found")
    return {"paper": json.loads(row["detail_json"]), "finished": bool(row["finished_at"]),
            "score": row["score"], "total": row["total"], "started_at": row["started_at"]}


@router.post("/exam/submit")
def submit(body: SubmitBody, con: sqlite3.Connection = Depends(db.get_db)):
    row = con.execute("SELECT * FROM exam_runs WHERE id = ?", (body.exam_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="exam_not_found")
    if row["finished_at"]:
        raise HTTPException(status_code=409, detail="already_submitted")
    paper = json.loads(row["detail_json"])
    result = exam_engine.score(content.load_content(), paper, body.responses, body.verdicts)
    con.execute("UPDATE exam_runs SET finished_at = ?, score = ?, total = ? WHERE id = ?",
                (_now(), result["score"], result["total"], body.exam_id))
    con.commit()
    result["wrong_quiz_ids"] = exam_engine.wrong_quiz_ids(paper, body.responses)
    return result
