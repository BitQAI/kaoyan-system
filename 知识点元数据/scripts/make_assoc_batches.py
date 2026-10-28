#!/usr/bin/env python3
"""为 315/101/204 生成关联数据（前置/相关/易混）的输入批次与科目索引。

每个批次含本批点位的完整文本，另附全科索引（id + 章 + 标题 + 首句），
供跨章引用时查 id。批次切分按章边界，不跨章拆。

    python3 scripts/make_assoc_batches.py            # 生成
    python3 scripts/make_assoc_batches.py --list     # 只看切分结果
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
META = ROOT / '知识点元数据'
OUT = META / 'research/assoc/batches'
SIZE = 34  # 每批点数上限


def first_sentence(text, n=60):
    t = (text or '').strip()
    for sep in ('。', '；', '，'):
        i = t.find(sep)
        if 0 < i <= n:
            return t[:i]
    return t[:n]


def main(list_only):
    OUT.mkdir(parents=True, exist_ok=True)
    for sid in ('315', '101', '204'):
        d = json.loads((META / 'subjects' / sid / f'{sid}.json').read_text(encoding='utf-8'))
        chname = {c['id']: c['name'] for c in d['chapters']}
        index = [{'id': p['id'], 'chapter': p['chapter'],
                  'chapter_name': chname.get(p['chapter'], ''),
                  'title': p['title'], 'brief': first_sentence(p.get('point'))}
                 for p in d['points']]
        (META / f'research/assoc/{sid}-index.json').write_text(
            json.dumps(index, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

        # 按章顺序切批，不跨章
        batches, cur = [], []
        for p in d['points']:
            cur.append(p)
            if len(cur) >= SIZE:
                batches.append(cur)
                cur = []
        if cur:
            batches.append(cur)
        for i, chunk in enumerate(batches, 1):
            rows = [{'id': p['id'], 'chapter': p['chapter'],
                     'chapter_name': chname.get(p['chapter'], ''),
                     'title': p['title'], 'point': p['point'],
                     'keywords': p.get('keywords') or [],
                     'cards': [c.get('question') for c in (p.get('cards') or [])]}
                    for p in chunk]
            path = OUT / f'{sid}-a{i}.json'
            path.write_text(json.dumps({'subject': sid, 'points': rows},
                                       ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            if list_only:
                print(f'{sid}-a{i}: {len(rows)} 点  {rows[0]["id"]}–{rows[-1]["id"]}')
        print(f'{sid}: {len(batches)} 批 / {len(d["points"])} 点')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    main(a.list)
