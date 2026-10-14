"""模拟考试：按真题题型组卷与判分（315=30选+20填 / 101=16选+17多选 / 812=名解·简答·论述自评卷）。"""
import random
import uuid

from app.services import quiz_grader

PAPERS = {
    ("315", "objective"): {"time": 90, "sections": [
        {"name": "选择题", "type": "single", "score_per": 2, "n": 30},
        {"name": "填空题", "type": "blank", "score_per": 2, "n": 20}]},
    ("101", "objective"): {"time": 60, "sections": [
        {"name": "单选题", "type": "single", "score_per": 1, "n": 16},
        {"name": "多选题", "type": "multi", "score_per": 2, "n": 17}]},
    ("812", "subjective"): {"time": 90, "sections": [
        {"name": "名词解释", "type": "card", "kind": "名解", "score_per": 5, "n": 6},
        {"name": "简答题", "type": "card", "kind": "简答", "score_per": 12, "n": 6},
        {"name": "论述题", "type": "card", "kind": "论述", "score_per": 24, "n": 2}]},
}

VERDICT_SCORE = {"know": 1.0, "fuzzy": 0.5, "no": 0.0}


def assemble(content: dict, subject: str, kind: str) -> dict:
    spec = PAPERS[(subject, kind)]
    subj = next(s for s in content["subjects"] if s["id"] == subject)
    pools = {"single": [], "multi": [], "blank": []}
    cards = []
    for ch in subj.get("chapters", []):
        for q in ch.get("quiz", []):
            pools[q.get("type", "single")].append({**q, "chapter": ch["id"]})
        for c in ch.get("cards", []):
            cards.append({**c, "chapter": ch["id"]})
    sections = []
    for s in spec["sections"]:
        if s["type"] == "card":
            items = [c for c in cards if c.get("kind") == s["kind"]]
            random.shuffle(items)
            items = items[: s["n"]]
        else:
            pool = pools[s["type"]]
            items = random.sample(pool, min(s["n"], len(pool)))
        sections.append({"name": s["name"], "type": s["type"], "kind": s.get("kind"),
                         "score_per": s["score_per"], "items": items})
    return {"exam_id": str(uuid.uuid4()), "subject": subject, "kind": kind,
            "time_limit_min": spec["time"], "sections": sections}


def score(content: dict, paper: dict, responses: list, verdicts: list) -> dict:
    rmap = {r.get("item_id"): r.get("response") for r in responses}
    vmap = {v.get("card_id"): v.get("verdict") for v in verdicts}
    per_section: dict = {}
    per_chapter: dict = {}
    total = 0.0
    got = 0.0
    for sec in paper["sections"]:
        earned = 0.0
        sec_total = 0
        for it in sec["items"]:
            sec_total += sec["score_per"]
            chid = it.get("chapter", "?")
            pc = per_chapter.setdefault(chid, {"n": 0, "correct": 0})
            pc["n"] += 1
            if sec["type"] == "card":
                v = vmap.get(it["id"], "no")
                earned += sec["score_per"] * VERDICT_SCORE.get(v, 0.0)
                if v == "know":
                    pc["correct"] += 1
            else:
                if quiz_grader.grade(it, rmap.get(it["id"]))["correct"]:
                    earned += sec["score_per"]
                    pc["correct"] += 1
        earned = round(earned, 1)
        per_section[sec["name"]] = {"earned": earned, "total": sec_total}
        got += earned
        total += sec_total
    return {"score": round(got, 1), "total": total,
            "per_section": per_section, "per_chapter": per_chapter}


def wrong_quiz_ids(paper: dict, responses: list) -> list[str]:
    """客观题答错清单（供前端一键入错题本）。"""
    rmap = {r.get("item_id"): r.get("response") for r in responses}
    out = []
    for sec in paper["sections"]:
        if sec["type"] == "card":
            continue
        for it in sec["items"]:
            if not quiz_grader.grade(it, rmap.get(it["id"]))["correct"]:
                out.append(it["id"])
    return out
