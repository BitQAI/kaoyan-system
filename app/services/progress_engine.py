import datetime

from app import content
from app.services import review_engine

STATE_COEF = {"known": 1.0, "review": 0.6, "half": 0.5, "listened": 0.3, "new": 0.0}
VALID_STATES = tuple(STATE_COEF.keys())


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def recompute_point_state(con, point_id: str) -> None:
    """细项状态变化后汇总考点状态：全会→known；有不会→review；有半会/部分→half；全清→删除。"""
    rows = con.execute("SELECT idx, state FROM unit_progress WHERE point_id = ?",
                       (point_id,)).fetchall()
    states = {r["idx"]: r["state"] for r in rows}
    try:
        found = content.find_point(content.load_content(), point_id)
        total = len((found[2].get("units") or [])) if found else 0
    except content.ContentMissing:
        total = 0
    if not states:
        new_state = "new"
    elif total and len(states) >= total and set(states.values()) == {"known"}:
        new_state = "known"
    elif "review" in states.values():
        new_state = "review"
    elif "half" in states.values():
        new_state = "half"
    elif "known" in states.values():
        new_state = "half"            # 部分已会 → 视为半会待复习
    else:
        new_state = "new"
    if new_state == "new":
        con.execute("DELETE FROM progress WHERE point_id = ?", (point_id,))
    else:
        con.execute(
            "INSERT INTO progress(point_id, state, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(point_id) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at",
            (point_id, new_state, _now()))
    con.commit()
    review_engine.on_state_change(con, point_id, new_state)


def compute_chapter(point_ids: list[str], states: dict[str, str]) -> float:
    if not point_ids:
        return 0.0
    total = sum(STATE_COEF.get(states.get(pid, "new"), 0.0) for pid in point_ids)
    return total / len(point_ids)


def compute_subject(chapters: list[dict], states: dict[str, str]) -> dict:
    weights = [c.get("weight_center", 0) for c in chapters]
    comps = [compute_chapter(c.get("points", []), states) for c in chapters]
    wsum = sum(weights) or 1.0
    psum = sum(len(c.get("points", [])) for c in chapters) or 1
    weighted = sum(w * comp for w, comp in zip(weights, comps)) / wsum
    raw = sum(comp * len(c.get("points", [])) for c, comp in zip(chapters, comps)) / psum
    return {"weighted": weighted, "raw": raw}


def compute_all(content: dict, states: dict[str, str]) -> list[dict]:
    reports = []
    for subj in content.get("subjects", []):
        chapters = subj.get("chapters", [])
        agg = compute_subject(
            [{"weight_center": c.get("weight_center", 0),
              "points": [p["id"] for p in c.get("points", [])]} for c in chapters],
            states,
        )
        reports.append({
            "id": subj["id"], "name": subj.get("name", subj["id"]),
            "weighted": agg["weighted"], "raw": agg["raw"],
            "has_content": subj.get("has_content", False),
            "chapters": [
                {"id": c["id"], "name": c.get("name", ""), "tier": c.get("tier"),
                 "weight_center": c.get("weight_center", 0),
                 "completion": compute_chapter([p["id"] for p in c.get("points", [])], states)}
                for c in chapters
            ],
        })
    return reports
