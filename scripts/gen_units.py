#!/usr/bin/env python3
"""原子知识单元拆分：把每个考点的解析（note）拆成 ~50 字的可独立记忆单元。

用法：
  python scripts/gen_units.py --chapter 812-01 --merge     # 试点某章
  python scripts/gen_units.py --all                        # 全量
  python scripts/gen_units.py --merge                      # 写回 content.json

断点续跑：结果追加到 content/units/units.jsonl，已有记录跳过（--force 重生成）。
"""
import argparse
import json
import pathlib
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.config import get_settings  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
UNITS_DIR = ROOT / "content" / "units"
UNITS_FILE = UNITS_DIR / "units.jsonl"
MODEL = "deepseek-v4.1-flash"

SYSTEM = (
    "你是考研辅导助教。任务：把考点解析拆成「原子知识单元」——"
    "每个单元只讲一件事，30-70 字，句子完整、可独立记忆、保留关键术语与数字。"
    "只输出 JSON 对象本身，不要代码块标记与多余文字。不要编造原文没有的内容。"
)
_lock = threading.Lock()


def build_prompt(subj_id: str, chap_name: str, point_text: str, note: str) -> list[dict]:
    style = {
        "315": "化学类：公式与数值必须准确，可用 Unicode 上下标（如 1.8×10⁻⁵）。",
        "812": "植物生理学：机制按因果链写（刺激→信号→响应）。",
        "101": "政治：区分概念内涵、判断标准与易混点。",
        "204": "英语二：用中文说明考点与做题步骤。",
    }.get(subj_id, "")
    user = (
        f"章节：{chap_name}\n考点：{point_text}\n\n解析原文：\n{note}\n\n"
        "拆成原子知识单元，输出 JSON：\n"
        '{"units":["单元一","单元二","..."]}\n\n'
        "要求：\n"
        "① 每个单元 30-70 字，只讲一件事（一个定义 / 一条结构 / 一步机制 / 一个易错点）；\n"
        "② 句子完整、可脱离原文独立记忆，保留关键术语、数字、公式；\n"
        "③ 按逻辑顺序（定义 → 结构/组成 → 机制/过程 → 意义/应用）；\n"
        "④ 6-12 个单元（内容多则多拆）；不要编号，不要「首先/其次」等连接词开头；\n"
        "⑤ 不要把一句话拆成两半，也不要合并两件不同的事。\n"
        f"科目要求：{style}"
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse_reply(text: str) -> list[str] | None:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    units = [str(u).strip() for u in (obj.get("units") or []) if str(u).strip()]
    return units if len(units) >= 3 else None


def call_llm(messages: list[dict], settings, retries: int = 2) -> list[str] | None:
    url = settings.opencode_base.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.opencode_key}",
               "x-opencode-session": "gen-units"}
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, headers={**headers, "Content-Type": "application/json"},
                              json={"model": MODEL, "messages": messages,
                                    "max_tokens": 4000}, timeout=300)
            r.raise_for_status()
            got = parse_reply(r.json()["choices"][0]["message"].get("content") or "")
            if got:
                return got
        except Exception as e:  # noqa: BLE001
            print(f"  ! LLM 失败：{str(e)[:80]}", file=sys.stderr)
        time.sleep(1.5 * (attempt + 1))
    return None


def load_done() -> dict:
    done = {}
    if UNITS_FILE.exists():
        for line in UNITS_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rec = json.loads(line)
                    done[rec["id"]] = rec
                except (json.JSONDecodeError, KeyError):
                    continue
    return done


def append_record(rec: dict) -> None:
    with _lock:
        UNITS_DIR.mkdir(parents=True, exist_ok=True)
        with UNITS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def iter_points(content: dict, chapter: str | None):
    for subj in content.get("subjects", []):
        for chap in subj.get("chapters", []):
            if chapter and chap["id"] != chapter:
                continue
            for p in chap.get("points", []):
                if p.get("note"):
                    yield subj, chap, p


def generate(content: dict, chapter: str | None, force: bool, concurrency: int) -> dict:
    settings = get_settings()
    done = load_done()
    jobs = [(subj, chap, p) for subj, chap, p in iter_points(content, chapter)
            if force or p["id"] not in done]
    print(f"待拆分 {len(jobs)} 点（已缓存 {len(done)}）", flush=True)
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = {pool.submit(call_llm, build_prompt(subj["id"], chap["name"], p["text"], p["note"]),
                            settings): p for subj, chap, p in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            p = futs[fut]
            got = fut.result()
            if got:
                append_record({"id": p["id"], "units": got})
                ok += 1
            else:
                fail += 1
            if i % 10 == 0 or i == len(jobs):
                print(f"  进度 {i}/{len(jobs)}（成功 {ok} · 失败 {fail}）", flush=True)
    return {"ok": ok, "fail": fail, "cached": len(done)}


def merge_into_content(path: pathlib.Path) -> int:
    content = json.loads(path.read_text(encoding="utf-8"))
    done = load_done()
    n = 0
    for subj in content.get("subjects", []):
        for chap in subj.get("chapters", []):
            for p in chap.get("points", []):
                rec = done.get(p["id"])
                if rec:
                    p["units"] = rec["units"]
                    n += 1
    path.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapter", default=None, help="只处理某章（如 812-01）")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--content", default=str(ROOT / "content" / "content.json"))
    args = ap.parse_args()

    path = pathlib.Path(args.content)
    if args.merge:
        n = merge_into_content(path)
        print(f"已合并 {n} 个考点的知识单元")
        return
    content = json.loads(path.read_text(encoding="utf-8"))
    stats = generate(content, args.chapter, args.force, args.concurrency)
    print(f"完成：成功 {stats['ok']} · 失败 {stats['fail']} · 累计缓存 {stats['cached'] + stats['ok']}")


if __name__ == "__main__":
    main()
