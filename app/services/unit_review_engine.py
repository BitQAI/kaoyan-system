"""单元/背题卡级复习调度与队列（V3 单元 + V4「记」）。

评分规则（两类一致）：
- again → stage=0，+1 天；hard → stage 不变，+3 天；
- good  → stage+1（0→+3 天、1→+7 天）；stage≥2 毕业（stage=3，行保留）。
- 缩放：days_left≤7 → 正向间隔压到 1 天；≤21 → 上限 3 天且冻结毕业。

队列（memo_queue）：到期单元 ∪ 到期考点展开 ∪ 到期卡 ∪ 范围/快捷集合（含新卡），
(stage,due) 排序后按科目轮转交错；到期模式按 review_n 截断，显式集合不截断。
"""
import datetime

from app.services import plan_engine, review_engine

GRADUATE_STAGE = 3
GOOD_DAYS = {0: 3, 1: 7}
GOOD_DAYS_TAIL = 7          # stage≥2 时继续秒答的基准间隔（冻结期专用）
AGAIN_DAYS = 1
HARD_DAYS = 3
HOT_TAGS = {"易错", "高频"}


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


def _schedule(con, table: str, key_cols: list[str], key_vals: list,
              stage: int, rating: str, t: str, dl: int) -> dict:
    """按三档评分推进一侧（单元/背题卡共用的调度核心）。"""
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
    cols = ", ".join(key_cols + ["stage", "due_date", "updated_at"])
    ph = ", ".join("?" * (len(key_cols) + 3))
    con.execute(
        f"INSERT INTO {table}({cols}) VALUES({ph}) "
        f"ON CONFLICT({', '.join(key_cols)}) DO UPDATE SET stage=excluded.stage, "
        f"due_date=excluded.due_date, updated_at=excluded.updated_at",
        (*key_vals, ns, due, t))
    con.commit()
    return {"stage": ns, "due_date": due, "graduates": ns >= GRADUATE_STAGE}


def rate(con, point_id: str, idx: int, rating: str, today: str | None = None,
         days_left: int | None = None) -> dict:
    t = _today(today)
    dl = _days_left(t, days_left)
    row = con.execute("SELECT stage FROM unit_reviews WHERE point_id = ? AND idx = ?",
                      (point_id, idx)).fetchone()
    return _schedule(con, "unit_reviews", ["point_id", "idx"], [point_id, idx],
                     row["stage"] if row else 0, rating, t, dl)


def rate_card(con, card_id: str, rating: str, today: str | None = None,
              days_left: int | None = None) -> dict:
    t = _today(today)
    dl = _days_left(t, days_left)
    row = con.execute("SELECT stage FROM card_reviews WHERE card_id = ?", (card_id,)).fetchone()
    return _schedule(con, "card_reviews", ["card_id"], [card_id],
                     row["stage"] if row else 0, rating, t, dl)


# ---------- 队列 ----------

def _mk_unit_item(unit_rows: dict, pid: str, i: int, t: str, dl: int) -> dict | None:
    row = unit_rows.get((pid, i))
    stage = row["stage"] if row else 0
    if stage >= GRADUATE_STAGE:
        return None
    return {"kind": "unit", "point_id": pid, "idx": i, "stage": stage,
            "due_date": row["due_date"] if row else t, "next": next_intervals(stage, dl)}


def _mk_card_item(card_rows: dict, pid: str | None, cid: str, t: str, dl: int) -> dict | None:
    row = card_rows.get(cid)
    stage = row["stage"] if row else 0
    if stage >= GRADUATE_STAGE:
        return None
    return {"kind": "card", "card_id": cid, "point_id": pid, "stage": stage,
            "due_date": row["due_date"] if row else t, "next": next_intervals(stage, dl)}


def _memo_sort_key(x: dict):
    tail = x["idx"] if x["kind"] == "unit" else x["card_id"]
    return (x["stage"], x["due_date"], x["point_id"] or "",
            0 if x["kind"] == "unit" else 1, tail)


def _keep(x: dict, filters: set, unit_rows: dict, card_rows: dict,
          fav_ids: set, point_tags: dict, t: str) -> bool:
    row = (unit_rows.get((x["point_id"], x["idx"])) if x["kind"] == "unit"
           else card_rows.get(x["card_id"]))
    if "due" in filters and (not row or row["due_date"] > t):
        return False
    if "weak" in filters and (not row or row["stage"] >= 2):
        return False
    if "fav" in filters and x["point_id"] not in fav_ids:
        return False
    if "hot" in filters and not (point_tags.get(x["point_id"], set()) & HOT_TAGS):
        return False
    return True


def _assemble(items: list, subj_order: list, pindex: dict,
              review_n: int, cap: bool, dl: int) -> dict:
    by_subj: dict[str, list] = {}
    for it in items:
        sid = pindex.get(it["point_id"], ("?",))[0]
        by_subj.setdefault(sid, []).append(it)
    order = [sid for sid in subj_order if sid in by_subj]
    if "?" in by_subj:
        order.append("?")
    for sid in order:
        by_subj[sid].sort(key=_memo_sort_key)
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
    shown = merged[:review_n] if cap else merged
    units_total = sum(1 for x in merged if x["kind"] == "unit")
    return {"items": shown, "due_total": len(merged), "total": len(merged),
            "units_total": units_total, "cards_total": len(merged) - units_total,
            "shown": len(shown),
            "est_min": max(1, round(len(shown) * 0.2)) if shown else 0,
            "days_left": dl, "frozen_graduation": frozen(dl)}


def memo_queue(con, content: dict, review_n: int, quick: str = "due",
               subjects: list | None = None, chapters: list | None = None,
               points: list | None = None, filter: list | None = None,
               look_points: list | None = None,
               today: str | None = None, days_left: int | None = None) -> dict:
    """「记」复习队列（V4 Spec §3.2）。

    种子优先级：显式范围（points/chapters/subjects）> 快捷集合（today_look/fav/hot）
    > 到期模式（quick=due）。到期模式按 review_n 截断；显式集合不截断。
    """
    t = _today(today)
    dl = _days_left(t, days_left)
    filters = set(filter or [])
    unit_rows = {(r["point_id"], r["idx"]): {"stage": r["stage"], "due_date": r["due_date"]}
                 for r in con.execute("SELECT point_id, idx, stage, due_date FROM unit_reviews")}
    card_rows = {r["card_id"]: {"stage": r["stage"], "due_date": r["due_date"]}
                 for r in con.execute("SELECT card_id, stage, due_date FROM card_reviews")}
    pindex = {}
    point_tags = {}
    point_cards = {}
    card_point = {}
    subj_order = []
    for subj in content.get("subjects", []):
        subj_order.append(subj["id"])
        for chap in subj.get("chapters", []):
            for p in chap.get("points", []):
                pindex[p["id"]] = (subj["id"], chap["id"], len(p.get("units") or []))
                point_tags[p["id"]] = set(p.get("tags") or [])
            for c in chap.get("cards", []):
                pid = c.get("point_id")
                card_point[c["id"]] = pid
                if pid:
                    point_cards.setdefault(pid, []).append(c["id"])

    fav_ids = {r["ref_id"] for r in
               con.execute("SELECT ref_id FROM favorites WHERE type = 'point'")}

    seed = None
    if points:
        seed = [p for p in points if p in pindex]
    elif chapters:
        cset = set(chapters)
        seed = [pid for pid, (_, cid, _) in pindex.items() if cid in cset]
    elif subjects:
        sset = set(subjects)
        seed = [pid for pid, (sid, _, _) in pindex.items() if sid in sset]
    elif quick == "today_look":
        seed = [p for p in (look_points or []) if p in pindex]
    elif quick == "fav":
        seed = [pid for pid in pindex if pid in fav_ids]
    elif quick == "hot":
        seed = [pid for pid, tags in point_tags.items() if tags & HOT_TAGS]

    if seed is not None:
        items = []
        for pid in seed:
            for i in range(pindex[pid][2]):
                x = _mk_unit_item(unit_rows, pid, i, t, dl)
                if x:
                    items.append(x)
            for cid in point_cards.get(pid, []):
                x = _mk_card_item(card_rows, pid, cid, t, dl)
                if x:
                    items.append(x)
        cap = False
    else:
        due_units = [x for x in (_mk_unit_item(unit_rows, pid, i, t, dl)
                                 for (pid, i), r in unit_rows.items()
                                 if r["due_date"] <= t) if x]
        due_point_ids = {x["point_id"] for x in due_units}
        expanded = []
        for pid in review_engine.due_points(con, t):
            if pid in due_point_ids or pid not in pindex:
                continue
            for i in range(pindex[pid][2]):
                x = _mk_unit_item(unit_rows, pid, i, t, dl)
                if x:
                    expanded.append(x)
        due_cards = [x for x in (_mk_card_item(card_rows, card_point.get(cid), cid, t, dl)
                                 for cid, r in card_rows.items()
                                 if r["due_date"] <= t) if x]
        items = due_units + expanded + due_cards
        cap = True

    if filters:
        items = [x for x in items if _keep(x, filters, unit_rows, card_rows,
                                           fav_ids, point_tags, t)]
    return _assemble(items, subj_order, pindex, review_n, cap, dl)


def queue(con, content: dict, review_n: int, today: str | None = None,
          days_left: int | None = None, point_id: str | None = None) -> dict:
    """V3 兼容入口：考点模式 = 该点未毕业单元（不受截断）；否则 = 到期模式队列。"""
    if point_id is None:
        return memo_queue(con, content, review_n, quick="due", today=today, days_left=days_left)
    t = _today(today)
    dl = _days_left(t, days_left)
    total = 0
    subj_order = []
    pindex = {}
    for subj in content.get("subjects", []):
        subj_order.append(subj["id"])
        for chap in subj.get("chapters", []):
            for p in chap.get("points", []):
                pindex[p["id"]] = (subj["id"], chap["id"], len(p.get("units") or []))
                if p["id"] == point_id:
                    total = len(p.get("units") or [])
    if point_id not in pindex:
        return {"items": [], "due_total": 0, "total": 0, "units_total": 0, "cards_total": 0,
                "shown": 0, "est_min": 0, "days_left": dl, "frozen_graduation": frozen(dl)}
    rows = {(r["point_id"], r["idx"]): {"stage": r["stage"], "due_date": r["due_date"]}
            for r in con.execute("SELECT point_id, idx, stage, due_date FROM unit_reviews "
                                 "WHERE point_id = ?", (point_id,))}
    items = [x for x in (_mk_unit_item(rows, point_id, i, t, dl) for i in range(total)) if x]
    items.sort(key=lambda x: (x["stage"], x["due_date"], x["idx"]))
    return {"items": items, "due_total": len(items), "total": len(items),
            "units_total": len(items), "cards_total": 0, "shown": len(items),
            "est_min": max(1, round(len(items) * 0.2)) if items else 0,
            "days_left": dl, "frozen_graduation": frozen(dl)}
