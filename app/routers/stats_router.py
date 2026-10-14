"""统计与导出：章节正确率、错题清单、进度表（Markdown）。"""
import datetime
import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app import auth, content, db
from app.services import progress_engine

router = APIRouter(prefix="/api", dependencies=[Depends(auth.require_auth)])


@router.get("/stats/chapters")
def chapters_stats(subject: str, con: sqlite3.Connection = Depends(db.get_db)):
    data = content.load_content()
    qmap = content.quiz_chapter_map(data)
    chapters = {ch["id"]: ch["name"]
                for s in data["subjects"] if s["id"] == subject for ch in s.get("chapters", [])}
    agg = {cid: {"n": 0, "correct": 0} for cid in chapters}
    for r in con.execute("SELECT quiz_id, correct FROM quiz_attempts"):
        cid = qmap.get(r["quiz_id"])
        if cid in agg:
            agg[cid]["n"] += 1
            agg[cid]["correct"] += r["correct"]
    items = [{"chap_id": cid, "name": name, "n": v["n"], "correct": v["correct"],
              "rate": round(v["correct"] / v["n"], 3) if v["n"] else None}
             for cid, name in chapters.items() for v in [agg[cid]]]
    return {"items": items}


def _md_response(text: str, filename: str) -> Response:
    return Response(text, media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/export/wrong")
def export_wrong(con: sqlite3.Connection = Depends(db.get_db)):
    data = content.load_content()
    chap_names = {ch["id"]: ch["name"] for _, ch in content.iter_chapters(data)}
    today = datetime.date.today().isoformat()
    lines = [f"# 错题清单（{today}）", ""]
    n = 0
    for r in con.execute("SELECT quiz_id, wrong_count FROM wrong_book "
                         "WHERE resolved_at IS NULL ORDER BY last_wrong_at DESC"):
        found = content.find_quiz(data, r["quiz_id"])
        if not found:
            continue
        _, chap, q = found
        n += 1
        lines.append(f"## {n}. {q.get('stem', '')}")
        qtype = q.get("type", "single")
        if qtype == "blank":
            ans = "；".join(b["accept"][0] for b in q.get("blanks", []))
            lines.append(f"- **答案**：{ans}")
        else:
            for i, opt in enumerate(q.get("options", [])):
                mark = " ✅" if (i in q["answer"] if qtype == "multi" else i == q["answer"]) else ""
                lines.append(f"  - {'ABCD'[i]}. {opt}{mark}")
            correct = "".join("ABCD"[i] for i in sorted(q["answer"])) if qtype == "multi" \
                else "ABCD"[q["answer"]]
            lines.append(f"- **答案**：{correct}")
        lines.append(f"- **解析**：{q.get('explain', '')}")
        lines.append(f"- 所属章节：{chap_names.get(chap['id'], chap['id'])}（{chap['id']}）· 错过 {r['wrong_count']} 次")
        lines.append("")
    if n == 0:
        lines.append("（暂无未清错题 🎉）")
    return _md_response("\n".join(lines), "wrong-list.md")


@router.get("/export/progress")
def export_progress(con: sqlite3.Connection = Depends(db.get_db)):
    data = content.load_content()
    states = {r["point_id"]: r["state"] for r in con.execute("SELECT point_id, state FROM progress")}
    reports = progress_engine.compute_all(data, states)
    today = datetime.date.today().isoformat()
    lines = [f"# 备考进度表（{today}）", "", "| 科目 | 加权完成度 | 原始完成度 |", "|---|---|---|"]
    for r in reports:
        lines.append(f"| {r['name']} | {r['weighted'] * 100:.1f}% | {r['raw'] * 100:.1f}% |")
    lines.append("")
    for r in reports:
        if not r.get("chapters"):
            continue
        lines += [f"## {r['name']}", "", "| 章节 | 权重 | 进度 |", "|---|---|---|"]
        for c in r["chapters"]:
            lines.append(f"| {c['name']}（{c['id']}） | {c['weight_center']} 分 | {c['completion'] * 100:.0f}% |")
        lines.append("")
    return _md_response("\n".join(lines), "progress.md")
