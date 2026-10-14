#!/usr/bin/env python3
"""合并被句中括号切碎的考点片段（源数据缺陷修复）。

场景：V1 解析按「；」切分考点时把括号内的并列项也切开，产生
  「植物根系对水分的吸收（主动吸水与根压、被动吸水与蒸腾拉力」+「两种吸水在不同条件下各自主导）」
两条考点。本脚本把「未闭合左括号」的点与紧随的「孤立右括号」点合并，
删除续段点并把引用（题库/卡片/媒体）重挂到合并后的点。

用法：python scripts/merge_fragment_points.py [--dry-run]
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts.normalize import to_speech  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def unbalanced(text: str) -> int:
    return text.count("（") - text.count("）")


def find_pairs(content: dict) -> list[tuple[dict, dict, dict]]:
    """返回 [(章节, 父点, 续段点)]。"""
    pairs = []
    for subj in content.get("subjects", []):
        for chap in subj.get("chapters", []):
            pts = chap.get("points", [])
            i = 0
            while i < len(pts):
                if unbalanced(pts[i]["text"]) > 0:
                    for j in range(i + 1, len(pts)):
                        if unbalanced(pts[j]["text"]) < 0:
                            pairs.append((chap, pts[i], pts[j]))
                            i = j
                            break
                i += 1
    return pairs


def merge(content: dict, dry_run: bool = False) -> dict:
    pairs = find_pairs(content)
    report = {"pairs": len(pairs), "merged": [], "refs_moved": 0}
    drop_ids = {cont["id"] for _, _, cont in pairs}
    if not pairs:
        return report
    for chap, parent, cont in pairs:
        merged_text = parent["text"].rstrip() + "；" + cont["text"].lstrip()
        report["merged"].append({"id": parent["id"], "text": merged_text})
        if dry_run:
            continue
        parent["text"] = merged_text
        parent["spoken"] = to_speech(merged_text, subject="812")
        for m in cont.get("media") or []:
            parent.setdefault("media", [])
            if not any(x.get("src") == m.get("src") for x in parent["media"]):
                parent["media"].append(m)
        chap["points"] = [p for p in chap["points"] if p["id"] != cont["id"]]
    if not dry_run:
        # 引用重挂：题库 / 卡片 / 复习记录不受影响（按点 id 记录，续段点已删）
        remap = {cont["id"]: parent["id"] for _, parent, cont in pairs}
        for subj in content.get("subjects", []):
            for chap in subj.get("chapters", []):
                for q in chap.get("quiz", []) + chap.get("cards", []):
                    if q.get("point_id") in remap:
                        q["point_id"] = remap[q["point_id"]]
                        report["refs_moved"] += 1
    report["dropped_ids"] = sorted(drop_ids)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", default=str(ROOT / "content" / "content.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    path = pathlib.Path(args.content)
    content = json.loads(path.read_text(encoding="utf-8"))
    report = merge(content, dry_run=args.dry_run)
    if not args.dry_run:
        path.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"发现碎片对 {report['pairs']} · 引用重挂 {report.get('refs_moved', 0)}")
    for m in report["merged"]:
        print("  ✓", m["id"], m["text"][:64] + ("…" if len(m["text"]) > 64 else ""))
    if report.get("dropped_ids"):
        print("删除续段点:", "、".join(report["dropped_ids"]))


if __name__ == "__main__":
    main()
