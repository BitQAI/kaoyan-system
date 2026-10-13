"""每日计划：确定性贪心——权重 × 未完成度 排序，听/看/测三单。"""
import datetime

from app.services import progress_engine

VISUAL_TYPES = ("diagram", "chart", "structure")
EXAM_DATE = "2026-12-19"


def clip_id_of(audio_entry: dict) -> str:
    src = audio_entry.get("src", "")
    return src.removeprefix("audio/").removesuffix(".mp3")


def _iter_points(content):
    for subj in content.get("subjects", []):
        for chap in subj.get("chapters", []):
            for p in chap.get("points", []):
                yield subj, chap, p


def _is_visual(point: dict) -> bool:
    return any(m.get("type") in VISUAL_TYPES for m in point.get("media", []))


def _chapter_score(chap: dict, states: dict) -> float:
    comp = progress_engine.compute_chapter([p["id"] for p in chap.get("points", [])], states)
    return chap.get("weight_center", 0) * (1 - comp)


def build_plan(content: dict, states: dict, wrong_ids: set, cfg: dict) -> dict:
    listen_minutes = cfg.get("listen_minutes", 40)
    look_n = cfg.get("look_n", 8)
    quiz_n = cfg.get("quiz_n", 15)

    chapters = sorted(content.get("subjects", []) and
                      [(c, s) for s in content["subjects"] for c in s.get("chapters", [])],
                      key=lambda cs: -_chapter_score(cs[0], states))

    listen, secs, budget = [], 0, listen_minutes * 60
    for chap, _ in chapters:
        for p in chap.get("points", []):
            if secs >= budget:
                break
            if states.get(p["id"], "new") not in ("new", None):
                continue
            if not p.get("listen_ok", True) or not p.get("audio"):
                continue
            if _is_visual(p):
                continue
            for a in p["audio"]:
                listen.append(clip_id_of(a))
                secs += a.get("dur", 0)
    listened_points = {cid.rsplit("-p", 1)[0] if "-p" in cid[-4:] else cid for cid in listen}

    wrong_points = {q["point_id"] for s in content.get("subjects", [])
                    for c in s.get("chapters", []) for q in c.get("quiz", [])
                    if q["id"] in wrong_ids and q.get("point_id")}
    review_candidates = [(chap, p) for _, chap, p in _iter_points(content)
                         if states.get(p["id"]) in ("half", "review") or p["id"] in wrong_points]
    review_candidates.sort(key=lambda cp: -cp[0].get("weight_center", 0))
    look = [p["id"] for _, p in review_candidates]
    if len(look) < look_n:
        fresh = [(chap, p) for _, chap, p in _iter_points(content)
                 if states.get(p["id"], "new") in ("new", None) and p["id"] not in listened_points]
        fresh.sort(key=lambda cp: -cp[0].get("weight_center", 0))
        for _, p in fresh:
            if len(look) >= look_n:
                break
            if p["id"] not in look:
                look.append(p["id"])
    look = look[:look_n]

    today_chapters = {chap["id"] for _, chap, p in _iter_points(content)
                      if p["id"] in set(look) | listened_points}
    quiz = [q for s in content.get("subjects", []) for c in s.get("chapters", [])
            if c["id"] in today_chapters for q in c.get("quiz", [])]
    wrong_quiz = [q for s in content.get("subjects", []) for c in s.get("chapters", [])
                  for q in c.get("quiz", []) if q["id"] in wrong_ids]
    seen, merged = set(), []
    for q in wrong_quiz + quiz:
        if q["id"] not in seen:
            seen.add(q["id"])
            merged.append(q["id"])
    return {"listen": listen, "look": look, "test": merged[:quiz_n],
            "est_minutes": secs // 60}


def pace(content: dict, states: dict, days_left: int, done_today: int = 0) -> dict:
    total = remaining = 0
    for _, _, p in _iter_points(content):
        total += 1
        if states.get(p["id"]) != "known":
            remaining += 1
    per_day = remaining / max(1, days_left)
    return {"remaining_points": remaining, "total_points": total,
            "per_day": per_day, "behind": done_today < per_day}


def days_left(today: str | None = None) -> int:
    t = datetime.date.fromisoformat(today) if today else datetime.date.today()
    return max(0, (datetime.date.fromisoformat(EXAM_DATE) - t).days)
