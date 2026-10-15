"""单元级复习调度：三档评分（again/hard/good）+ 考前间隔缩放（冻结毕业）。

规则（V3 Spec §3.2）：
- again → stage=0，+1 天；hard → stage 不变，+3 天；
- good  → stage+1（0→+3 天、1→+7 天）；stage≥2 毕业（stage=3，行保留，不再出卡）。
- 缩放：days_left≤7 → 所有正向间隔压到 1 天；≤21 → 上限 3 天且冻结毕业。
"""
import datetime

from app.services import plan_engine, review_engine

GRADUATE_STAGE = 3
GOOD_DAYS = {0: 3, 1: 7}
GOOD_DAYS_TAIL = 7          # stage≥2 时继续秒答的基准间隔（冻结期专用）
AGAIN_DAYS = 1
HARD_DAYS = 3


def _today(today: str | None) -> str:
    return today or datetime.date.today().isoformat()


def _plus(today: str, days: int) -> str:
    return (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()


def _days_left(today: str, days_left: int | None) -> int:
    return plan_engine.days_left(today) if days_left is None else days_left


def frozen(days_left: int) -> bool:
    return days_left <= 21


def cap_days(days: int, days_left: int) -> int:
    if days_left <= 7:
        return min(days, 1)
    if days_left <= 21:
        return min(days, 3)
    return days


def next_intervals(stage: int, days_left: int) -> dict:
    """各档评分对应的下次间隔天数（good=None 表示毕业）。"""
    if stage >= 2 and not frozen(days_left):
        good, graduates = None, True
    else:
        base = GOOD_DAYS.get(stage, GOOD_DAYS_TAIL)
        good, graduates = cap_days(base, days_left), False
    return {"again": cap_days(AGAIN_DAYS, days_left),
            "hard": cap_days(HARD_DAYS, days_left),
            "good": good, "graduates": graduates}


def rate(con, point_id: str, idx: int, rating: str, today: str | None = None,
         days_left: int | None = None) -> dict:
    t = _today(today)
    dl = _days_left(t, days_left)
    row = con.execute("SELECT stage FROM unit_reviews WHERE point_id = ? AND idx = ?",
                      (point_id, idx)).fetchone()
    stage = row["stage"] if row else 0
    if rating == "again":
        ns, days = 0, cap_days(AGAIN_DAYS, dl)
    elif rating == "hard":
        ns, days = stage, cap_days(HARD_DAYS, dl)
    elif stage >= 2:
        if frozen(dl):                                   # 冻结期：停在 stage2 循环
            ns, days = 2, cap_days(GOOD_DAYS_TAIL, dl)
        else:                                            # 毕业：行保留
            ns, days = GRADUATE_STAGE, 0
    else:
        ns, days = stage + 1, cap_days(GOOD_DAYS[stage], dl)
    due = _plus(t, days)
    con.execute(
        "INSERT INTO unit_reviews(point_id, idx, stage, due_date, updated_at) VALUES(?,?,?,?,?) "
        "ON CONFLICT(point_id, idx) DO UPDATE SET stage=excluded.stage, "
        "due_date=excluded.due_date, updated_at=excluded.updated_at",
        (point_id, idx, ns, due, t))
    con.commit()
    return {"stage": ns, "due_date": due, "graduates": ns >= GRADUATE_STAGE}


def _item(pid: str, idx: int, stage: int, due: str, days_left: int) -> dict:
    return {"point_id": pid, "idx": idx, "stage": stage, "due_date": due,
            "next": next_intervals(stage, days_left)}


def queue(con, content: dict, review_n: int, today: str | None = None,
          days_left: int | None = None, point_id: str | None = None) -> dict:
    """复习队列：到期单元 ∪ 到期考点展开（去重），(stage,due) 排序后按科目轮转交错。"""
    t = _today(today)
    dl = _days_left(t, days_left)
    rows = {(r["point_id"], r["idx"]): {"stage": r["stage"], "due_date": r["due_date"]}
            for r in con.execute("SELECT point_id, idx, stage, due_date FROM unit_reviews")}
    index = {}
    subj_order = []
    for subj in content.get("subjects", []):
        subj_order.append(subj["id"])
        for chap in subj.get("chapters", []):
            for p in chap.get("points", []):
                index[p["id"]] = (subj["id"], len(p.get("units") or []))

    def build(pid: str, i: int) -> dict | None:
        row = rows.get((pid, i))
        stage = row["stage"] if row else 0
        if stage >= GRADUATE_STAGE:
            return None
        return _item(pid, i, stage, row["due_date"] if row else t, dl)

    empty = {"items": [], "due_total": 0, "shown": 0, "days_left": dl,
             "frozen_graduation": frozen(dl)}

    if point_id is not None:                             # 单考点模式（复习此点），不受截断
        if point_id not in index:
            return empty
        items = [x for x in (build(point_id, i) for i in range(index[point_id][1])) if x]
        items.sort(key=lambda x: (x["stage"], x["due_date"], x["idx"]))
        return {"items": items, "due_total": len(items), "shown": len(items),
                "days_left": dl, "frozen_graduation": frozen(dl)}

    due_units = [x for x in (build(pid, i) for (pid, i), row in rows.items()
                             if row["due_date"] <= t) if x]
    due_point_ids = {x["point_id"] for x in due_units}
    expanded = []
    for pid in review_engine.due_points(con, t):
        if pid in due_point_ids or pid not in index:
            continue
        for i in range(index[pid][1]):
            x = build(pid, i)
            if x:
                expanded.append(x)

    by_subj: dict[str, list] = {}
    for it in due_units + expanded:
        sid = index.get(it["point_id"], ("?", 0))[0]
        by_subj.setdefault(sid, []).append(it)
    order = [sid for sid in subj_order if sid in by_subj]
    if "?" in by_subj:
        order.append("?")
    for sid in order:
        by_subj[sid].sort(key=lambda x: (x["stage"], x["due_date"], x["point_id"], x["idx"]))

    merged, ptr = [], {sid: 0 for sid in order}
    while True:
        added = False
        for sid in order:
            if ptr[sid] < len(by_subj[sid]):
                merged.append(by_subj[sid][ptr[sid]])
                ptr[sid] += 1
                added = True
        if not added:
            break
    shown = merged[:review_n]
    return {"items": shown, "due_total": len(merged), "shown": len(shown),
            "days_left": dl, "frozen_graduation": frozen(dl)}
