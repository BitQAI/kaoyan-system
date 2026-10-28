#!/usr/bin/env python3
"""812 v3 原子单元生成：4–15 条/点，30–70 字，一事一句。"""
import argparse
import json
import pathlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import llm

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'
PATH = META / 'subjects' / '812' / '812-units.jsonl'
LOCK = threading.Lock()

SYSTEM = (
    '你是植物生理学教学专家。把给定知识点的理解解析拆成原子记忆单元。'
    '每条 30–70 字、只讲一件事、句子完整、可脱离上下文独立记忆；'
    '保留关键术语/数字/公式；按「定义→结构/组成→机制/过程→条件→意义/应用→易错」排序；'
    '不照抄原句序，不编造原文没有的内容；化学式用 Unicode 角标。'
    '只输出 JSON：{"id":"...","units":["...","..."]}'
)


def build_prompt(p):
    return (
        f'知识点：{p["point"]}\n短标题：{p["title"]}\n'
        f'理解解析：{p["explain"]}\n考法：{p["exam"]}\n'
        f'要求：4–15 条；每条 30–70 字；一事一句。'
    )


def one(p):
    raw = llm.call_llm([
        {'role': 'system', 'content': SYSTEM},
        {'role': 'user', 'content': build_prompt(p)},
    ], max_tokens=3000)
    obj = llm.parse_reply(raw)
    if not obj or obj.get('id') != p['id']:
        return None
    units = [u.strip() for u in obj.get('units', []) if u.strip()]
    if not (3 <= len(units) <= 18):
        return None
    if any(not (20 <= len(u) <= 85) for u in units):
        return None
    return {'id': p['id'], 'units': units}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', nargs='*')
    ap.add_argument('--force', action='store_true', help='已有 unit 的点也重生成')
    ap.add_argument('--concurrency', type=int, default=4)
    args = ap.parse_args()
    d = json.loads((META / 'subjects/812/812.json').read_text(encoding='utf-8'))
    pts = [p for p in d['points'] if not args.ids or p['id'] in args.ids]
    done = {}
    if PATH.exists():
        for line in PATH.read_text(encoding='utf-8').splitlines():
            if line.strip():
                r = json.loads(line)
                done[r['id']] = r
    todo = [p for p in pts if args.force or p['id'] not in done]
    print(f'待生成 {len(todo)} / {len(pts)}')
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(one, p): p for p in todo}
        for f in as_completed(futs):
            p = futs[f]
            try:
                r = f.result()
            except Exception as e:
                print('ERR', p['id'], e)
                continue
            if not r:
                print('FAIL', p['id'])
                continue
            with LOCK:
                done[r['id']] = r
                with PATH.open('a', encoding='utf-8') as fh:
                    fh.write(json.dumps(r, ensure_ascii=False) + '\n')
                print('OK', p['id'], len(r['units']))
    print('完成', len(done))


if __name__ == '__main__':
    main()
