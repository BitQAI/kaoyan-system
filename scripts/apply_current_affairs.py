#!/usr/bin/env python3
"""时政月度流水线：把当月时政摘要转为 101-27 章节的考点并入库。

用法：
  python scripts/apply_current_affairs.py content/current_affairs/2026-11.md
  python scripts/apply_current_affairs.py            # 默认取 content/current_affairs/ 下最新的 YYYY-MM.md

输入格式见 content/current_affairs/TEMPLATE.md：
  ## 事件标题
  - 要点一
  - 要点二
  [考纲挂钩: 对应考点，可省略]

行为：
  · 每个「事件 × 要点」生成一个考点，id 为 101-27-ca01、ca02…（按文件顺序）
  · 重复执行幂等：先移除该章旧的 ca* 考点再重建
  · 新考点会清空 101-27 的章级听单（listen），需随后运行：
      python scripts/gen_chapter_listen.py --subject 101
    重新生成该章音频（同时补齐其他缺失章节）。
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts.normalize import to_speech  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CA_DIR = ROOT / "content" / "current_affairs"
CHAP_ID = "101-27"


def parse_markdown(text: str) -> list[dict]:
    """解析时政摘要：返回 [{event, point}]，每要点一条。"""
    rows: list[dict] = []
    event = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            event = line[3:].strip()
        elif line.startswith("- ") and event:
            body = line[2:].strip()
            body = re.sub(r"^\s*\[考纲挂钩[:：].*?\]\s*", "", body).strip()
            if body:
                rows.append({"event": event, "point": body})
        elif line.startswith("[考纲挂钩") and event:
            continue
    return rows


def apply_to_content(content: dict, rows: list[dict]) -> dict:
    """重建 101-27 的 ca* 考点；返回统计。"""
    chap = next((c for s in content.get("subjects", []) for c in s.get("chapters", [])
                 if c["id"] == CHAP_ID), None)
    if chap is None:
        raise SystemExit(f"content.json 缺少章节 {CHAP_ID}")
    removed = 0
    kept = []
    for p in chap.get("points", []):
        if "-ca" in p["id"]:
            removed += 1
        else:
            kept.append(p)
    added = []
    for i, row in enumerate(rows, 1):
        pid = f"{CHAP_ID}-ca{i:02d}"
        text = f"{row['event']}——{row['point']}"
        added.append({
            "id": pid, "text": text, "spoken": to_speech(text, subject="101"),
            "tags": ["时政", "高频"], "listen_ok": True, "media": [], "audio": [],
        })
    chap["points"] = kept + added
    if added and chap.get("listen"):
        chap["listen"] = []           # 章级听单需按新考点重新生成
    return {"removed": removed, "added": len(added)}


def latest_file() -> pathlib.Path:
    files = sorted(CA_DIR.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].md"))
    if not files:
        raise SystemExit(f"{CA_DIR} 下没有 YYYY-MM.md 文件（先按 TEMPLATE.md 撰写当月摘要）")
    return files[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md", nargs="?", default=None)
    ap.add_argument("--content", default=str(ROOT / "content" / "content.json"))
    args = ap.parse_args()

    md_path = pathlib.Path(args.md) if args.md else latest_file()
    rows = parse_markdown(md_path.read_text(encoding="utf-8"))
    if not rows:
        raise SystemExit(f"{md_path} 未解析出要点（检查「## 事件」与「- 要点」格式）")

    path = pathlib.Path(args.content)
    content = json.loads(path.read_text(encoding="utf-8"))
    stats = apply_to_content(content, rows)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"时政入库：{md_path.name} → 移除旧考点 {stats['removed']} · 新增 {stats['added']}")
    print("下一步：python scripts/gen_chapter_listen.py --subject 101   # 重生成 101 章级音频")


if __name__ == "__main__":
    main()
