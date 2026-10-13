STATE_COEF = {"known": 1.0, "review": 0.6, "half": 0.5, "listened": 0.3, "new": 0.0}
VALID_STATES = tuple(STATE_COEF.keys())


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
