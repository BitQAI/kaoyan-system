#!/usr/bin/env python3
"""content.json 校验与题库合并。

用法：python scripts/validate_content.py [--content content/content.json] [--merge]
"""
import argparse
import json
import pathlib
import sys


def _iter(content):
    for subj in content.get("subjects", []):
        for ch in subj.get("chapters", []):
            yield subj, ch


def check(content: dict, content_dir: pathlib.Path | None = None) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for subj, ch in _iter(content):
        point_ids = {p["id"] for p in ch.get("points", [])}
        for p in ch.get("points", []):
            if p["id"] in seen:
                errors.append(f"重复 id: {p['id']}")
            seen.add(p["id"])
            for m in p.get("media", []):
                src = m.get("src")
                if src and content_dir and not (content_dir / src).exists():
                    errors.append(f"媒体文件缺失: {p['id']} → {src}")
        for q in ch.get("quiz", []):
            qid = q.get("id", "?")
            if qid in seen:
                errors.append(f"重复 id: {qid}")
            seen.add(qid)
            if qid.startswith("?"):
                errors.append(f"{ch['id']} 题目缺少 id")
            if not q.get("stem"):
                errors.append(f"{qid} 缺少题干")
            qtype = q.get("type", "single")
            if qtype not in ("single", "multi", "blank"):
                errors.append(f"{qid} 未知题型: {qtype}")
            elif qtype == "blank":
                blanks = q.get("blanks") or []
                if not blanks:
                    errors.append(f"{qid} 填空缺少 blanks")
                for b in blanks:
                    if not (b.get("accept") or []):
                        errors.append(f"{qid} 填空 accept 为空")
            else:
                opts = q.get("options") or []
                if len(opts) < 2:
                    errors.append(f"{qid} 选项不足")
                ans = q.get("answer")
                if qtype == "multi":
                    if not isinstance(ans, list) or not ans or len(set(ans)) != len(ans) \
                            or any(not isinstance(a, int) or not (0 <= a < len(opts)) for a in ans):
                        errors.append(f"{qid} multi answer 非法: {ans}")
                elif not isinstance(ans, int) or not (0 <= ans < len(opts)):
                    errors.append(f"{qid} answer 越界: {ans}")
            if not q.get("explain"):
                errors.append(f"{qid} 缺少解析")
            pid = q.get("point_id")
            if pid and pid not in point_ids:
                errors.append(f"{qid} point_id 悬空: {pid}")
        for c in ch.get("cards", []):
            cid = c.get("id", "?")
            if cid in seen:
                errors.append(f"重复 id: {cid}")
            seen.add(cid)
            if not c.get("front") or not c.get("back"):
                errors.append(f"{cid} 卡片内容不完整")
            pid = c.get("point_id")
            if pid and pid not in point_ids:
                errors.append(f"{cid} point_id 悬空: {pid}")
    return errors


def merge_quiz(content: dict, quiz_dir: pathlib.Path) -> dict:
    """把 content/quiz/*.json 并入（清空后按 chapter 重挂）。"""
    for _, ch in _iter(content):
        ch["quiz"] = []
        ch["cards"] = []
    by_chap_q: dict[str, list] = {}
    by_chap_c: dict[str, list] = {}
    for f in sorted(quiz_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for q in data.get("quizzes", []):
            by_chap_q.setdefault(q["chapter"], []).append(q)
        for c in data.get("cards", []):
            by_chap_c.setdefault(c["chapter"], []).append(c)
    for _, ch in _iter(content):
        ch["quiz"] = by_chap_q.get(ch["id"], [])
        ch["cards"] = by_chap_c.get(ch["id"], [])
    return content


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", default="content/content.json")
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()

    path = pathlib.Path(args.content)
    content = json.loads(path.read_text(encoding="utf-8"))
    if args.merge:
        merge_quiz(content, path.parent / "quiz")
        path.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已合并 content/quiz/*.json")
    errors = check(content, content_dir=path.parent)
    n_q = sum(len(c.get("quiz", [])) for _, c in _iter(content))
    n_c = sum(len(c.get("cards", [])) for _, c in _iter(content))
    if errors:
        print(f"FAIL  {len(errors)} 个问题（题目 {n_q} · 卡片 {n_c}）")
        for e in errors[:40]:
            print("  -", e)
        sys.exit(1)
    print(f"OK  题目 {n_q} · 卡片 {n_c} · 0 问题")


if __name__ == "__main__":
    main()
