"""内容只读接口：manifest / 章节 / 点详情 / 检索。"""
import json

from fastapi import APIRouter, Depends, HTTPException

from app import config, db, search
from app.sanitize import sanitize_svg

router = APIRouter(prefix="/api", tags=["content"])


def _loads(raw, default):
    try:
        return json.loads(raw) if raw else default
    except (TypeError, ValueError):
        return default


@router.get("/health")
def health(conn=Depends(db.get_db)):
    points = conn.execute("SELECT COUNT(*) FROM point").fetchone()[0]
    return {"ok": True, "points": points, "ai_configured": config.ai_configured(),
            "exam_date": config.EXAM_DATE}


@router.get("/manifest")
def manifest(conn=Depends(db.get_db)):
    subjects = []
    for s in conn.execute("SELECT * FROM subject ORDER BY sort"):
        rows = conn.execute(
            "SELECT id, name, module, tier, weight_center, weight_range, weight_basis, "
            "entry_count, note, sort FROM chapter WHERE subject_id = ? ORDER BY sort",
            (s["id"],),
        ).fetchall()
        subjects.append({
            "id": s["id"],
            "name": s["name"],
            "score": s["score"],
            "status": s["status"],
            "chapters": [{
                "id": c["id"], "name": c["name"], "module": c["module"],
                "tier": c["tier"], "weight_center": c["weight_center"],
                "weight_range": _loads(c["weight_range"], None),
                "weight_basis": c["weight_basis"],
                "entry_count": c["entry_count"], "note": c["note"],
            } for c in rows],
        })
    points = [{
        "id": r["id"], "chapter_id": r["chapter_id"], "subject_id": r["subject_id"],
        "title": r["title"], "priority": r["priority"],
        "evidence_level": r["evidence_level"],
    } for r in conn.execute(
        "SELECT id, chapter_id, subject_id, title, priority, evidence_level "
        "FROM point ORDER BY subject_id, ord")]
    return {"subjects": subjects, "points": points}


@router.get("/subjects/{sid}/chapters")
def subject_chapters(sid: str, conn=Depends(db.get_db)):
    rows = conn.execute(
        "SELECT * FROM chapter WHERE subject_id = ? ORDER BY sort", (sid,)).fetchall()
    if not rows:
        raise HTTPException(404, "科目不存在")
    return {"items": [{
        "id": c["id"], "name": c["name"], "module": c["module"], "tier": c["tier"],
        "weight_center": c["weight_center"],
        "weight_range": _loads(c["weight_range"], None),
        "weight_basis": c["weight_basis"], "entry_count": c["entry_count"],
        "note": c["note"],
    } for c in rows]}


@router.get("/chapters/{cid}/points")
def chapter_points(cid: str, conn=Depends(db.get_db)):
    rows = conn.execute(
        "SELECT id, title, point, priority, evidence_level FROM point "
        "WHERE chapter_id = ? ORDER BY ord", (cid,)).fetchall()
    if not rows:
        raise HTTPException(404, "章节不存在")
    return {"items": [dict(r) for r in rows]}


@router.get("/points/{pid}")
def point_detail(pid: str, conn=Depends(db.get_db)):
    row = conn.execute("SELECT * FROM point WHERE id = ?", (pid,)).fetchone()
    if row is None:
        raise HTTPException(404, "知识点不存在")
    p = dict(row)
    p["keywords"] = _loads(p["keywords"], [])
    p["tags"] = _loads(p["tags"], [])
    p["exam_types"] = _loads(p["exam_types"], [])
    p["evidence_sources"] = _loads(p["evidence_sources"], [])
    p["source"] = {
        "ref": p.pop("source_ref"), "file": p.pop("source_file"),
        "section": p.pop("source_section"), "basis": p.pop("source_basis"),
        "kind": p.pop("source_kind"),
    }
    p["exam_evidence"] = {
        "level": p.pop("evidence_level"), "basis": p.pop("evidence_basis"),
        "sources": p.pop("evidence_sources"),
    }
    p["listen"] = {"script": p.pop("listen_script"),
                   "card_id": p.pop("listen_card_id"),
                   "kind": p.pop("listen_kind")}
    p["tts"] = {"enabled": bool(p.pop("tts_enabled")), "est_sec": p.pop("tts_est_sec")}
    p["units"] = [r["text"] for r in conn.execute(
        "SELECT text FROM unit WHERE point_id = ? ORDER BY idx", (pid,)).fetchall()]
    p["cards"] = [{
        "card_id": c["card_id"], "kind": c["kind"], "card_type": c["card_type"],
        "question": c["question"], "answer": c["answer"],
        "options": _loads(c["options"], []),
        "answer_points": _loads(c["answer_points"], []),
        "analysis": c["analysis"], "unit_refs": _loads(c["unit_refs"], []),
        "difficulty": c["difficulty"],
        "reviews": c["reviews"] or 0, "last_result": c["last_result"],
        "listen_count": c["listen_count"] or 0,
    } for c in conn.execute(
        "SELECT c.*, cp.reviews, cp.last_result, cl.listen_count "
        "FROM card c "
        "LEFT JOIN card_progress cp ON cp.card_id = c.card_id "
        "LEFT JOIN card_listen cl ON cl.card_id = c.card_id "
        "WHERE c.point_id = ? ORDER BY c.ord", (pid,)).fetchall()]
    figures = []
    for m in conn.execute(
            "SELECT kind, caption, alt, svg FROM media WHERE point_id = ? ORDER BY idx",
            (pid,)).fetchall():
        svg = sanitize_svg(m["svg"])
        if svg:
            figures.append({"kind": m["kind"], "caption": m["caption"],
                            "alt": m["alt"], "svg": svg})
    p["media"] = figures
    p["relations"] = _relations(conn, pid)
    return p


def _relations(conn, pid: str) -> dict:
    groups: dict[str, list] = {"prerequisite": [], "related": [], "confusable": []}
    for r in conn.execute(
            "SELECT kind, target_id, name, distinction FROM relation "
            "WHERE point_id = ? ORDER BY kind, idx", (pid,)):
        groups[r["kind"]].append({
            "point_id": r["target_id"], "name": r["name"],
            "distinction": r["distinction"],
        })
    return groups


@router.get("/points/{pid}/source")
def point_source(pid: str, conn=Depends(db.get_db)):
    from app import locator
    row = conn.execute(
        "SELECT source_ref, source_kind, source_file, evidence_basis "
        "FROM point WHERE id = ?", (pid,)).fetchone()
    if row is None:
        raise HTTPException(404, "知识点不存在")
    text, note = locator.resolve_paragraph(
        row["source_ref"], row["source_kind"], row["source_file"],
        row["evidence_basis"])
    return {"text": text, "note": note}


@router.get("/search")
def search_api(q: str, sid: str | None = None, limit: int = 20,
               conn=Depends(db.get_db)):
    return search.search(conn, q, sid, limit)
