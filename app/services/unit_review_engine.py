"""单元/背题卡级复习调度与队列（V5：考试锚定的分档间隔）。

间隔 = (days_left − jitter) / (2^k_remain − 1)：每次复习把剩余时间按剩余次数
几何铺开，末次恒落在考前 jitter 天（1–21，由 item id 哈希分散）。
曝光次数 K 按 chapter.tier 分档：背题卡 6、第 1 梯队 4、第 2/3 梯队 2。
队列按 (tier, stage, due) 排序——末段容量不足时，排序即分配策略。
"""
import datetime
import hashlib

from app.services import plan_engine, review_engine

K_CARD = 6
K_BY_TIER = {1: 4, 2: 2, 3: 2}
K_DEFAULT = 2
JITTER_SPAN = 21
HOT_TAGS = {"易错", "高频"}


def target_k(kind: str, tier: int | None) -> int:
    """目标评分次数（含首次学习评分）。"""
    if kind == "card":
        return K_CARD
    return K_BY_TIER.get(tier if tier is not None else K_DEFAULT, K_DEFAULT)


def unit_key(point_id: str, idx: int) -> str:
    return f"{point_id}#{idx}"


def jitter(key: str) -> int:
    """确定性抖动 ∈ [1, JITTER_SPAN]，把末次复习分散到考前 1–21 天。"""
    return 1 + int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16) % JITTER_SPAN


def _today(today: str | None) -> str:
    return today or datetime.date.today().isoformat()


def _plus(today: str, days: int) -> str:
    return (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()


def _days_left(today: str, days_left: int | None) -> int:
    return plan_engine.days_left(today) if days_left is None else days_left


def _gap(stage: int, k: int, days_left: int, key: str) -> int | None:
    """stage 为「评分后的新 stage」。None 表示应毕业。"""
    kr = k - stage                       # 剩余复习次数（含即将安排的这次）
    if kr <= 0:
        return None
    r = days_left - jitter(key)
    if r < 1:
        return None
    return max(1, round(r / (2 ** kr - 1)))


def next_intervals(stage: int, k: int, days_left: int, key: str) -> dict:
    """各档评分对应的下次间隔天数（good=None 表示毕业）。"""
    good = _gap(stage + 1, k, days_left, key)
    if good is None:
        hard = max(1, round((days_left - jitter(key)) / 2))
    else:
        hard = max(1, round(good / 2))
    return {"again": 1, "hard": hard, "good": good, "graduates": good is None}


def _advance(stage: int, rating: str, k: int, t: str, dl: int,
             key: str) -> tuple[int, str | None]:
    """返回 (新 stage, 新 due_date)；due_date 为 None 表示毕业。"""
    if rating == "again":
        return 0, _plus(t, 1)
    ns = stage + 1 if rating == "good" else stage
    g = _gap(ns, k, dl, key)
    if g is None:
        return ns, None
    if rating == "hard":
        g = max(1, round(g / 2))
    return ns, _plus(t, g)


def _schedule(con, table: str, key_cols: list[str], key_vals: list,
              stage: int, rating: str, k: int, t: str, dl: int, key: str) -> dict:
    """按三档评分推进一侧（单元/背题卡共用的调度核心）。"""
    ns, due = _advance(stage, rating, k, t, dl, key)
    graduates = due is None
    if graduates:                                    # 毕业：行保留，due 置为当天
        ns = max(ns, k)
        due = t
    cols = ", ".join(key_cols + ["stage", "due_date", "updated_at"])
    ph = ", ".join("?" * (len(key_cols) + 3))
    con.execute(
        f"INSERT INTO {table}({cols}) VALUES({ph}) "
        f"ON CONFLICT({', '.join(key_cols)}) DO UPDATE SET stage=excluded.stage, "
        f"due_date=excluded.due_date, updated_at=excluded.updated_at",
        (*key_vals, ns, due, t))
    con.commit()
    return {"stage": ns, "due_date": due, "graduates": graduates}


def rate(con, point_id: str, idx: int, rating: str, k: int, today: str | None = None,
         days_left: int | None = None) -> dict:
    t = _today(today)
    dl = _days_left(t, days_left)
    row = con.execute("SELECT stage FROM unit_reviews WHERE point_id = ? AND idx = ?",
                      (point_id, idx)).fetchone()
    return _schedule(con, "unit_reviews", ["point_id", "idx"], [point_id, idx],
                     row["stage"] if row else 0, rating, k, t, dl, unit_key(point_id, idx))


def rate_card(con, card_id: str, rating: str, k: int, today: str | None = None,
              days_left: int | None = None) -> dict:
    t = _today(today)
    dl = _days_left(t, days_left)
    row = con.execute("SELECT stage FROM card_reviews WHERE card_id = ?", (card_id,)).fetchone()
    return _schedule(con, "card_reviews", ["card_id"], [card_id],
                     row["stage"] if row else 0, rating, k, t, dl, card_id)


# ---------- 队列 ----------

def _mk_unit_item(unit_rows: dict, pid: str, i: int, t: str, dl: int,
                  tier: int, k: int) -> dict | None:
    row = unit_rows.get((pid, i))
    stage = row["stage"] if row else 0
    if stage >= k:
        return None
    return {"kind": "unit", "point_id": pid, "idx": i, "tier": tier, "k": k, "stage": stage,
            "due_date": row["due_date"] if row else t,
            "next": next_intervals(stage, k, dl, unit_key(pid, i))}


def _mk_card_item(card_rows: dict, pid: str | None, cid: str, t: str, dl: int,
                  tier: int, k: int) -> dict | None:
    row = card_rows.get(cid)
    stage = row["stage"] if row else 0
    if stage >= k:
        return None
    return {"kind": "card", "card_id": cid, "point_id": pid, "tier": tier, "k": k, "stage": stage,
            "due_date": row["due_date"] if row else t,
            "next": next_intervals(stage, k, dl, cid)}


def _memo_sort_key(x: dict):
    tail = x["idx"] if x["kind"] == "unit" else x["card_id"]
    return (x["tier"], x["stage"], x["due_date"], x["point_id"] or "",
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
            "days_left": dl}


def memo_queue(con, content: dict, review_n: int, quick: str = "due",
               subjects: list | None = None, chapters: list | None = None,
               points: list | None = None, filter: list | None = None,
               look_points: list | None = None,
               today: str | None = None, days_left: int | None = None) -> dict:
    """「记」复习队列（V5 Spec §6.1）。

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
    ctier = {}
    point_tags = {}
    point_cards = {}
    card_point = {}
    subj_order = []
    for subj in content.get("subjects", []):
        subj_order.append(subj["id"])
        for chap in subj.get("chapters", []):
            tier = chap.get("tier", 3)
            for p in chap.get("points", []):
                pindex[p["id"]] = (subj["id"], chap["id"], len(p.get("units") or []), tier)
                point_tags[p["id"]] = set(p.get("tags") or [])
            for c in chap.get("cards", []):
                pid = c.get("point_id")
                card_point[c["id"]] = pid
                ctier[c["id"]] = tier
                if pid:
                    point_cards.setdefault(pid, []).append(c["id"])

    fav_ids = {r["ref_id"] for r in
               con.execute("SELECT ref_id FROM favorites WHERE type = 'point'")}

    seed = None
    if points:
        seed = [p for p in points if p in pindex]
    elif chapters:
        cset = set(chapters)
        seed = [pid for pid, (_, cid, _, _) in pindex.items() if cid in cset]
    elif subjects:
        sset = set(subjects)
        seed = [pid for pid, (sid, _, _, _) in pindex.items() if sid in sset]
    elif quick == "today_look":
        seed = [p for p in (look_points or []) if p in pindex]
    elif quick == "fav":
        seed = [pid for pid in pindex if pid in fav_ids]
    elif quick == "hot":
        seed = [pid for pid, tags in point_tags.items() if tags & HOT_TAGS]

    if seed is not None:
        items = []
        for pid in seed:
            tier = pindex[pid][3]
            k = target_k("unit", tier)
            for i in range(pindex[pid][2]):
                x = _mk_unit_item(unit_rows, pid, i, t, dl, tier, k)
                if x:
                    items.append(x)
            for cid in point_cards.get(pid, []):
                x = _mk_card_item(card_rows, pid, cid, t, dl, ctier.get(cid, tier),
                                  target_k("card", ctier.get(cid, tier)))
                if x:
                    items.append(x)
        cap = False
    else:
        due_units = []
        for (pid, i), r in unit_rows.items():
            if r["due_date"] > t or pid not in pindex:
                continue
            x = _mk_unit_item(unit_rows, pid, i, t, dl, pindex[pid][3],
                              target_k("unit", pindex[pid][3]))
            if x:
                due_units.append(x)
        due_point_ids = {x["point_id"] for x in due_units}
        expanded = []
        for pid in review_engine.due_points(con, t):
            if pid in due_point_ids or pid not in pindex:
                continue
            tier = pindex[pid][3]
            k = target_k("unit", tier)
            for i in range(pindex[pid][2]):
                x = _mk_unit_item(unit_rows, pid, i, t, dl, tier, k)
                if x:
                    expanded.append(x)
        due_cards = []
        for cid, r in card_rows.items():
            if r["due_date"] > t:
                continue
            tier = ctier.get(cid, 3)
            x = _mk_card_item(card_rows, card_point.get(cid), cid, t, dl, tier,
                              target_k("card", tier))
            if x:
                due_cards.append(x)
        items = due_units + expanded + due_cards
        cap = True

    if filters:
        items = [x for x in items if _keep(x, filters, unit_rows, card_rows,
                                           fav_ids, point_tags, t)]
    return _assemble(items, subj_order, pindex, review_n, cap, dl)


def queue(con, content: dict, review_n: int, today: str | None = None,
          days_left: int | None = None, point_id: str | None = None) -> dict:
    """V5 兼容入口：考点模式 = 该点未毕业单元（不受截断）；否则 = 到期模式队列。"""
    if point_id is None:
        return memo_queue(con, content, review_n, quick="due", today=today, days_left=days_left)
    t = _today(today)
    dl = _days_left(t, days_left)
    total = 0
    subj_order = []
    pindex = {}
    tier = 3
    for subj in content.get("subjects", []):
        subj_order.append(subj["id"])
        for chap in subj.get("chapters", []):
            for p in chap.get("points", []):
                pindex[p["id"]] = (subj["id"], chap["id"], len(p.get("units") or []),
                                   chap.get("tier", 3))
                if p["id"] == point_id:
                    total = len(p.get("units") or [])
                    tier = chap.get("tier", 3)
    if point_id not in pindex:
        return {"items": [], "due_total": 0, "total": 0, "units_total": 0, "cards_total": 0,
                "shown": 0, "est_min": 0, "days_left": dl}
    k = target_k("unit", tier)
    rows = {(r["point_id"], r["idx"]): {"stage": r["stage"], "due_date": r["due_date"]}
            for r in con.execute("SELECT point_id, idx, stage, due_date FROM unit_reviews "
                                 "WHERE point_id = ?", (point_id,))}
    items = [x for x in (_mk_unit_item(rows, point_id, i, t, dl, tier, k)
                         for i in range(total)) if x]
    items.sort(key=lambda x: (x["stage"], x["due_date"], x["idx"]))
    return {"items": items, "due_total": len(items), "total": len(items),
            "units_total": len(items), "cards_total": 0, "shown": len(items),
            "est_min": max(1, round(len(items) * 0.2)) if items else 0,
            "days_left": dl}
