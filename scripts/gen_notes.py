#!/usr/bin/env python3
"""考点解析批量生成：为每个点位生成 note（理解）/ exam（考点怎么考）/ keywords。

用法：
  python scripts/gen_notes.py --subject 101 --limit 2     # 试点
  python scripts/gen_notes.py --all --concurrency 3       # 全量
  python scripts/gen_notes.py --all --merge               # 写回 content.json

断点续跑：结果逐条追加到 content/notes/notes.jsonl，已有记录的点位跳过（--force 重生成）。
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
NOTES_DIR = ROOT / "content" / "notes"
NOTES_FILE = NOTES_DIR / "notes.jsonl"
MODEL = "deepseek-v4.1-flash"

SYSTEM = (
    "你是考研辅导助教，为备战 2027 考研的学生生成「考点精讲卡」。"
    "只输出 JSON 对象本身，不要代码块标记、不要多余文字。"
    "内容必须依据考研大纲与标准教材，不确定的内容写「请对照教材核验」，不要编造。"
)

STYLE = {
    "101": "政治理论：note 要讲清概念的内涵与逻辑关系；exam 指明单选/多选/分析题怎么考、"
           "常见设问、易混概念辨析与答题要点。",
    "315": "化学（农）：note 讲清定义、适用条件与内在联系；exam 指明计算题/判断题的考法与"
           "常见陷阱。涉及公式、数值用 Unicode 符号（如 1.8×10⁻⁵、c₁V₁=c₂V₂），"
           "化学式、常数、计算结果必须准确。",
    "812": "植物生理学：note 用因果链讲清机制（刺激→信号→响应）；exam 覆盖名词解释/"
           "简答/论述的作答结构与常考角度。",
    "204": "英语（二）：note 用中文讲清考点含义与训练方法；exam 指明对应题型（完形/阅读A/B/"
           "翻译/写作）的解题步骤、定位方法与常见失分点。",
}
_lock = threading.Lock()


def build_prompt(subj_name: str, subj_id: str, chap_name: str, point: dict,
                 siblings: list[str]) -> list[dict]:
    sib = "、".join(siblings[:12]) if siblings else "（无）"
    user = (
        f"科目：{subj_name}\n章节：{chap_name}\n考点：{point['text']}\n"
        f"同章其他考点（仅供定位，勿展开）：{sib}\n\n"
        "输出 JSON：\n"
        '{"note":"理解与解析：3-6 句，讲清是什么、为什么重要、内在逻辑，'
        '面向备考学生，可直接当复习讲解稿","exam":"考点怎么考：3-4 条，含常考题型、'
        '设问方式、答题要点、易错点，用分号分隔，不要换行","keywords":["3-5 个关键词"]}\n\n'
        f"科目要求：{STYLE.get(subj_id, '')}"
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse_reply(text: str) -> dict | None:
    """从模型回复中提取 JSON；容忍 ```json 围栏与前后噪声。"""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    note = (obj.get("note") or "").strip()
    exam = (obj.get("exam") or "").strip()
    kws = [str(k).strip() for k in (obj.get("keywords") or []) if str(k).strip()]
    if not note or not exam or not kws:
        return None
    return {"note": note, "exam": exam, "keywords": kws[:6]}


def call_llm(messages: list[dict], settings, retries: int = 2) -> dict | None:
    url = settings.opencode_base.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.opencode_key}",
               "x-opencode-session": "gen-notes"}
    last = ""
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, headers={**headers, "Content-Type": "application/json"},
                              json={"model": MODEL, "messages": messages,
                                    "max_tokens": 6000}, timeout=300)
            r.raise_for_status()
            j = r.json()
            choice = (j.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content") or ""
            got = parse_reply(content)
            if got:
                return got
            last = f"finish={choice.get('finish_reason')} content_len={len(content)} " \
                   f"usage={j.get('usage', {}).get('completion_tokens')}"
        except Exception as e:  # noqa: BLE001
            last = str(e)[:120]
        time.sleep(1.5 * (attempt + 1))
    print(f"  ! 生成失败：{last}", file=sys.stderr)
    return None


def load_done() -> dict:
    done = {}
    if NOTES_FILE.exists():
        for line in NOTES_FILE.read_text(encoding="utf-8").splitlines():
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
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        with NOTES_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def iter_points(content: dict, only: set | None):
    for subj in content.get("subjects", []):
        if only and subj["id"] not in only:
            continue
        for chap in subj.get("chapters", []):
            titled = [p["text"] for p in chap.get("points", [])]
            for p in chap.get("points", []):
                yield subj, chap, p, [t for t in titled if t != p["text"]]


def generate(content: dict, only: set | None, limit: int | None,
             force: bool, concurrency: int) -> dict:
    settings = get_settings()
    done = load_done()
    jobs = []
    for subj, chap, p, sibs in iter_points(content, only):
        if not force and p["id"] in done:
            continue
        if limit and len(jobs) >= limit:
            break
        jobs.append((subj, chap, p, sibs))
    print(f"待生成 {len(jobs)} 点（已缓存 {len(done)}）", flush=True)
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = {pool.submit(call_llm, build_prompt(subj["name"], subj["id"], chap["name"],
                                                   p, sibs), settings): p
                for subj, chap, p, sibs in jobs}
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
                    p["note"] = rec["note"]
                    p["exam"] = rec["exam"]
                    p["keywords"] = rec["keywords"]
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
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--content", default=str(ROOT / "content" / "content.json"))
    args = ap.parse_args()

    path = pathlib.Path(args.content)
    content = json.loads(path.read_text(encoding="utf-8"))
    if args.merge:
        n = merge_into_content(path)
        print(f"已合并 {n} 个点位的解析到 {path}")
        return
    only = None if args.all else set(args.subject or ["101", "315", "812"])
    stats = generate(content, only, args.limit, args.force, args.concurrency)
    print(f"完成：成功 {stats['ok']} · 失败 {stats['fail']} · 累计缓存 {stats['cached'] + stats['ok']}")


if __name__ == "__main__":
    main()
