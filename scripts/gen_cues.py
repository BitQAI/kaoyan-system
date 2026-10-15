#!/usr/bin/env python3
"""线索式标题（cue）批量生成：为每个考点生成「只提示主题、不泄露答案」的短标题。

用法：
  python scripts/gen_cues.py --limit 20            # 样例（门控：主人确认后全量）
  python scripts/gen_cues.py --all --concurrency 3 # 全量生成
  python scripts/gen_cues.py --merge               # 写回 content.json（p.cue）
  python scripts/gen_cues.py --sample              # 打印已有样例对照表

断点续跑：结果追加到 content/cues/cues.jsonl；已有记录跳过（--force 重生成）。
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
CUES_DIR = ROOT / "content" / "cues"
CUES_FILE = CUES_DIR / "cues.jsonl"
MODEL = "deepseek-v4.1-flash"

SYSTEM = (
    "你是考研辅导助教。为考点生成「线索式标题」：只提示这个考点问什么、要回忆什么，"
    "绝不包含答案结论。只输出 JSON 对象本身，不要代码块标记。"
)

_lock = threading.Lock()


def build_prompt(chap_name: str, point: dict) -> list[dict]:
    user = (
        f"章节：{chap_name}\n考点原文（可能是结论式表述）：{point['text']}\n\n"
        "生成线索式标题，要求：\n"
        "1. 6-18 字，保留专有名词与编号；\n"
        "2. 只提示「考的是什么」，不得出现原文的答案部分（数字、结论、判别方向）；\n"
        "3. 好例：原文「光呼吸消耗乙醇酸并释放CO2」→ 线索「光呼吸的底物与产物」；\n"
        "   坏例：「光呼吸消耗乙醇酸」（泄题）。\n\n"
        '输出 JSON：{"cue":"线索标题"}'
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse_reply(text: str) -> dict | None:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    cue = (obj.get("cue") or "").strip().strip("「」\"'")
    if not (2 <= len(cue) <= 24):
        return None
    return {"cue": cue}


def call_llm(messages: list[dict], settings, retries: int = 2) -> dict | None:
    url = settings.opencode_base.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.opencode_key}",
               "x-opencode-session": "gen-cues"}
    last = ""
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, headers={**headers, "Content-Type": "application/json"},
                              json={"model": MODEL, "messages": messages,
                                    "max_tokens": 800}, timeout=120)
            r.raise_for_status()
            choice = (r.json().get("choices") or [{}])[0]
            got = parse_reply((choice.get("message") or {}).get("content") or "")
            if got:
                return got
            last = f"finish={choice.get('finish_reason')}"
        except Exception as e:  # noqa: BLE001
            last = str(e)[:120]
        time.sleep(1.5 * (attempt + 1))
    print(f"  ! 生成失败：{last}", file=sys.stderr)
    return None


def load_done() -> dict:
    done = {}
    if CUES_FILE.exists():
        for line in CUES_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                done[rec["id"]] = rec
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def append_record(rec: dict) -> None:
    with _lock:
        CUES_DIR.mkdir(parents=True, exist_ok=True)
        with CUES_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def iter_points(content: dict, only: set | None):
    for subj in content.get("subjects", []):
        if only and subj["id"] not in only:
            continue
        for chap in subj.get("chapters", []):
            for p in chap.get("points", []):
                yield subj, chap, p


def generate(content: dict, only: set | None, limit: int | None,
             force: bool, concurrency: int) -> dict:
    settings = get_settings()
    done = load_done()
    jobs = []
    for subj, chap, p in iter_points(content, only):
        if not force and p["id"] in done:
            continue
        if limit and len(jobs) >= limit:
            break
        jobs.append((chap, p))
    print(f"待生成 {len(jobs)} 点（已缓存 {len(done)}）", flush=True)
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = {pool.submit(call_llm, build_prompt(chap["name"], p), settings): p
                for chap, p in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            p = futs[fut]
            got = fut.result()
            if got:
                append_record({"id": p["id"], "text": p["text"], **got})
                ok += 1
            else:
                fail += 1
            if i % 10 == 0 or i == len(jobs):
                print(f"  进度 {i}/{len(jobs)}（成功 {ok} · 失败 {fail}）", flush=True)
    return {"ok": ok, "fail": fail}


def print_samples(limit: int) -> None:
    done = load_done()
    for i, rec in enumerate(done.values()):
        if i >= limit:
            break
        print(f"- [{rec['id']}] 原文：{rec['text']}\n  线索：{rec['cue']}")


def merge_into_content(path: pathlib.Path) -> int:
    content = json.loads(path.read_text(encoding="utf-8"))
    done = load_done()
    n = 0
    for _, _, p in iter_points(content, None):
        rec = done.get(p["id"])
        if rec:
            p["cue"] = rec["cue"]
            n += 1
    path.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", action="append", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--sample-n", type=int, default=20)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--content", default=str(ROOT / "content" / "content.json"))
    args = ap.parse_args()

    path = pathlib.Path(args.content)
    if args.merge:
        n = merge_into_content(path)
        print(f"已合并 {n} 个 cue 到 {path}")
        return
    if args.sample:
        print_samples(args.sample_n)
        return
    content = json.loads(path.read_text(encoding="utf-8"))
    only = None if args.all else set(args.subject or ["812"])
    stats = generate(content, only, args.limit, args.force, args.concurrency)
    print(f"完成：成功 {stats['ok']} · 失败 {stats['fail']}")


if __name__ == "__main__":
    main()
