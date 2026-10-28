#!/usr/bin/env python3
"""LLM 拆分：把 explain 拆成「原子知识单元」units（D14=B 全量重新拆分）。

用法：
  python scripts/gen_units.py --subject 812 --limit 3
  python scripts/gen_units.py --all --concurrency 6

产出：subjects/<sid>/<sid>-units.jsonl（{id, units:[...]}）
"""
import argparse
import json
import os
import pathlib
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import llm  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'
BUILD = ROOT / '.build'
MODEL = 'deepseek-v4.1-flash'

SYSTEM = (
    '你是考研辅导助教。任务：把考点解析拆成「原子知识单元」——'
    '每个单元只讲一件事，30–70 字，句子完整、可独立记忆、保留关键术语与数字。'
    '只输出 JSON 对象本身，不要代码块标记与多余文字。不要编造原文没有的内容。'
    '涉及化学式、离子、公式时使用 Unicode 下标与上标（H₂O、CO₂、SO₄²⁻），禁止 ASCII 形态。'
)

_lock = threading.Lock()



def build_prompt(p):
    return (
        f"考点：{p['point']}\n\n"
        f"解析原文：\n{p.get('explain') or p['point']}\n\n"
        f"请拆成 6–12 个原子知识单元，输出 JSON 对象 {{\"units\": [\"...\", \"...\", ...]}}。\n"
        f"硬约束：\n"
        f"① 每个单元 30–70 字，只讲一件事（一个定义 / 一条结构 / 一步机制 / 一个易错点）；\n"
        f"② 句子完整、可脱离原文独立记忆，保留关键术语、数字、公式；\n"
        f"③ 按逻辑顺序（定义 → 结构/组成 → 机制/过程 → 意义/应用）；\n"
        f"④ 6–12 个单元（内容多则多拆）；不要编号，不要以「首先/其次」等连接词开头；\n"
        f"⑤ 不要把一句话拆成两半，也不要合并两件不同的事。"
    )


def clean(got):
    if not isinstance(got, dict):
        return None
    units = got.get('units')
    if units is None:
        cands = [v for v in got.values() if isinstance(v, list)]
        units = cands[0] if cands else None
    if not isinstance(units, list):
        return None
    units = [str(u).strip() for u in units if str(u).strip()]
    if len(units) < 3:
        return None
    return units[:12]


def load_done(path):
    done = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                try:
                    r = json.loads(line)
                    done[r['id']] = r
                except json.JSONDecodeError:
                    continue
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--subject', action='append', default=[])
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--concurrency', type=int, default=6)
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    ext = json.loads((BUILD / 'extract.json').read_text(encoding='utf-8'))
    enrich_cache = {}
    subjects = ext['subjects']
    if not args.all:
        subjects = [s for s in subjects if s['id'] in args.subject]
    if not subjects:
        raise SystemExit('用 --all 或 --subject 指定科目')

    for sub in subjects:
        sid = sub['id']
        ef = META / 'subjects' / sid / f'{sid}-enrich.jsonl'
        en = {}
        if ef.exists():
            for line in ef.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    r = json.loads(line)
                    en[r['id']] = r
        out_dir = META / 'subjects' / sid
        out_file = out_dir / f'{sid}-units.jsonl'
        done = {} if args.force else load_done(out_file)
        todo = [p for p in sub['points'] if p['id'] not in done and en.get(p['id'])]
        if args.limit:
            todo = todo[:args.limit]
        print(f'{sid} {sub["name"]}：待拆分 {len(todo)}（已缓存 {len(done)}）')

        def one(p):
            e = en[p['id']]
            got = llm.call_llm([
                {'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': build_prompt({**p, 'explain': e.get('explain', '')})},
            ])
            return p['id'], clean(got)

        ok = fail = 0
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(one, p): p for p in todo}
            for i, fut in enumerate(as_completed(futs), 1):
                pid, u = fut.result()
                if u:
                    ok += 1
                    with _lock:
                        with out_file.open('a', encoding='utf-8') as f:
                            f.write(json.dumps({'id': pid, 'units': u}, ensure_ascii=False) + '\n')
                else:
                    fail += 1
                if i % 20 == 0 or i == len(todo):
                    print(f'  进度 {i}/{len(todo)}（成功 {ok} · 失败 {fail}）')
        print(f'完成：成功 {ok} · 失败 {fail}')


if __name__ == '__main__':
    main()
