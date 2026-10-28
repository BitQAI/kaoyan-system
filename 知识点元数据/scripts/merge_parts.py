#!/usr/bin/env python3
"""合并各分片 units → subjects/<sid>/<sid>-units.jsonl，并做覆盖校验。"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
M = ROOT / '知识点元数据'
PARTS = ROOT / '.build' / 'units_parts'


def main():
    allrec = {}
    dup = []
    # 先读各科已有的 units 文件（人工手写批次），再读分片（分片优先）
    for sid in ('812', '315', '101', '204'):
        f = M / 'subjects' / sid / f'{sid}-units.jsonl'
        if f.exists():
            for line in f.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    r = json.loads(line)
                    allrec.setdefault(r['id'], r['units'])
    for f in sorted(PARTS.glob('*.jsonl')):
        for line in f.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r['id'] in allrec:
                if allrec[r['id']] != r['units']:
                    dup.append((r['id'], f.name))   # 内容不一致才算冲突
                continue
            allrec[r['id']] = r['units']

    # 人工生成的批次（812 绪论 + 第一章）已在正式文件里，合并时以分片为准
    for sid in ('812', '315', '101', '204'):
        doc = json.loads((M / 'subjects' / sid / f'{sid}.json').read_text(encoding='utf-8'))
        want = [p['id'] for p in doc['points']]
        have = [i for i in want if i in allrec]
        miss = [i for i in want if i not in allrec]
        out = M / 'subjects' / sid / f'{sid}-units.jsonl'
        with out.open('w', encoding='utf-8') as fh:
            for i in have:
                fh.write(json.dumps({'id': i, 'units': allrec[i]}, ensure_ascii=False) + '\n')
        n = sum(len(allrec[i]) for i in have)
        per = [len(allrec[i]) for i in have]
        flag = '✓' if not miss else f'✗ 缺 {len(miss)}'
        print(f'  {sid}: {len(have)}/{len(want)} 点 {flag} · 单元 {n} · 每点均 '
              f'{sum(per)//max(len(per),1)} (min {min(per) if per else 0} max {max(per) if per else 0})')
        if miss:
            print(f'      缺: {miss[:12]}')
    if dup:
        print(f'  分片间 id 重复 {len(dup)}: {dup[:5]}')


if __name__ == '__main__':
    main()
