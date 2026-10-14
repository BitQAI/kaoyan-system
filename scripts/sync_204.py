#!/usr/bin/env python3
"""把 parse_204() 的 204 英语（二）章节/考点幂等写入 content.json（不动其他科目）。

用法：python scripts/sync_204.py [--content content/content.json]
用途：parse_content.py 全量重跑会重建 content.json（丢 listen/media），故 204 用本脚本增量应用。
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts.parse_content import parse_204  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", default=str(ROOT / "content" / "content.json"))
    args = ap.parse_args()
    path = pathlib.Path(args.content)
    content = json.loads(path.read_text(encoding="utf-8"))
    new204 = parse_204()

    # 保留已生成的 note/exam/keywords（按 point_id 沿用）
    old = next((s for s in content.get("subjects", []) if s["id"] == "204"), None)
    old_notes = {}
    if old:
        for ch in old.get("chapters", []):
            for p in ch.get("points", []):
                if p.get("note"):
                    old_notes[p["id"]] = {k: p[k] for k in ("note", "exam", "keywords") if k in p}
    for ch in new204["chapters"]:
        for p in ch["points"]:
            if p["id"] in old_notes:
                p.update(old_notes[p["id"]])

    subjects = [s for s in content.get("subjects", []) if s["id"] != "204"]
    subjects.append(new204)
    content["subjects"] = subjects
    path.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")

    pts = sum(len(c["points"]) for c in new204["chapters"])
    print(f"204 已写入：{len(new204['chapters'])} 章 · {pts} 考点 · 沿用解析 {len(old_notes)} 条 → {path}")


if __name__ == "__main__":
    main()
