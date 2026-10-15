"""负载模拟：验证 V5 调度在给定容量下的日负载与考前覆盖率（Spec §7.2）。

公式一律复用 unit_review_engine（next_intervals / target_k / unit_key），
不重写，否则脚本与实现会漂移。
"""
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.services import unit_review_engine as e   # noqa: E402

EXAM = 65          # 距考试天数（day 0 = 今天；2026-10-15 → 2026-12-19 = 65 天）
TAIL = 21          # 考前窗口
DEFAULT_CONTENT = pathlib.Path(__file__).resolve().parent.parent / "content" / "content.json"


def load_items(content_path):
    """返回 [(tier, kind, key)]；单元在考点级、卡片挂在章级。"""
    data = json.loads(pathlib.Path(content_path).read_text(encoding="utf-8"))
    items = []
    for subj in data["subjects"]:
        for chap in subj.get("chapters", []):
            tier = chap.get("tier", 3)
            for p in chap.get("points", []):
                for i in range(len(p.get("units") or [])):
                    items.append((tier, "unit", e.unit_key(p["id"], i)))
            for c in chap.get("cards", []):
                items.append((tier, "card", c["id"]))
    return items


def simulate(content_path=DEFAULT_CONTENT, cap=260, learn_days=45):
    """逐日推进调度：到期集合按 (tier, due) 排序取前 cap 条，其余顺延。"""
    items = load_items(content_path)
    by_tier = collections.defaultdict(list)
    for tier, kind, key in items:
        by_tier[tier].append((kind, key))

    # 学习顺序：高梯队先学（模拟 plan_engine 的权重×未完成度排序）
    todo = []
    for tier in (1, 2, 3):
        group = by_tier[tier]
        n = len(group)
        for pos, (kind, key) in enumerate(group):
            todo.append({"tier": tier, "kind": kind, "key": key,
                         "learn": int(pos * learn_days / n), "stage": 0, "due": None})

    per_day = collections.Counter()
    tail_hit = collections.Counter()
    completed = collections.Counter()
    deferred = 0

    for day in range(EXAM + 1):
        dl = EXAM - day
        for it in todo:
            if it["learn"] == day and it["stage"] == 0:
                # 首次学习评分：stage 0 → 1，并按公式排下一次复习
                g = e.next_intervals(0, e.target_k(it["kind"], it["tier"]), dl, it["key"])["good"]
                it["stage"] = 1
                it["due"] = day + g if g is not None else None

        due = [it for it in todo if it["due"] is not None and it["due"] <= day]
        due.sort(key=lambda x: (x["tier"], x["due"]))       # 容量不足时的分配策略
        take = due[:cap]
        deferred += max(0, len(due) - cap)

        for it in take:
            k = e.target_k(it["kind"], it["tier"])
            g = e.next_intervals(it["stage"], k, dl, it["key"])["good"]
            it["stage"] += 1
            per_day[day] += 1
            if day >= EXAM - TAIL:
                tail_hit[it["tier"]] += 1
            if g is None:
                it["due"] = None                            # 毕业
                completed[it["tier"]] += 1
            else:
                it["due"] = day + g

    totals = {t: len(by_tier[t]) for t in (1, 2, 3)}
    values = [per_day.get(d, 0) for d in range(EXAM + 1)]
    return {
        "daily_avg": sum(values) // len(values),
        "peak": max(values),
        "deferred": deferred,
        "total_reviews": sum(values),
        "tier_tail_coverage": {t: tail_hit[t] / totals[t] for t in (1, 2, 3)},
        "tier_ladder_completion": {t: completed[t] / totals[t] for t in (1, 2, 3)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", default=str(DEFAULT_CONTENT))
    ap.add_argument("--cap", type=int, default=260)
    ap.add_argument("--learn-days", type=int, default=45)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    out = simulate(a.content, a.cap, a.learn_days)
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    print(f"总复习 {out['total_reviews']}  日均 {out['daily_avg']}  "
          f"峰值 {out['peak']}  顺延 {out['deferred']}")
    for t in (1, 2, 3):
        print(f"  第{t}梯队  考前 {TAIL} 天覆盖 {out['tier_tail_coverage'][t] * 100:.0f}%"
              f"  走完阶梯 {out['tier_ladder_completion'][t] * 100:.0f}%")


if __name__ == "__main__":
    main()
