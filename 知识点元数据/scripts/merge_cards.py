#!/usr/bin/env python3
"""合并各分片 cards → subjects/<sid>/<sid>-cards.jsonl，并核验章级配额。"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
M = ROOT / '知识点元数据'
PARTS = ROOT / '.build' / 'cards_parts'

VALID = {
    '812': {'名解', '简答', '论述'},
    '315': {'名词解释', '简答', '公式速记', '综合'},
    '101': {'名词解释', '简答', '分析'},
    '204': {'词汇', '句型', '技巧', '模板'},
}
# 812 章级硬配额：名解≥2 · 简答≥2 · 论述≥1
QUOTA_812 = {'名解': 2, '简答': 2, '论述': 1}


def main():
    problems = []
    for sid in ('812', '315', '101', '204'):
        rec = {}
        for f in sorted(PARTS.glob(f'{sid}_*.jsonl')):
            for line in f.read_text(encoding='utf-8').splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if r['id'] in rec:
                    problems.append(f'{sid} {r["id"]} 分片重复')
                    continue
                rec[r['id']] = r['cards']

        doc = json.loads((M / 'subjects' / sid / f'{sid}.json').read_text(encoding='utf-8'))
        chap_of = {p['id']: p['chapter'] for p in doc['points']}
        want = [p['id'] for p in doc['points']]

        # 校验并修正
        clean = {}
        for pid in want:
            cs = []
            for c in rec.get(pid, []):
                k = c.get('kind', '')
                if k not in VALID[sid]:
                    k = '简答'
                    problems.append(f'{sid} {pid} kind 非法→简答')
                fr = c.get('front', '').replace('|', '｜').strip()[:40]
                bk = c.get('back', '').replace('|', '｜').strip()
                if not fr or not bk:
                    continue
                if len(bk) < 40 or len(bk) > 300:
                    problems.append(f'{sid} {pid} back 长度 {len(bk)} 越界')
                cs.append({'kind': k, 'front': fr, 'back': bk,
                           'point_id': pid,
                           'card_id': f'c{pid}-{len(cs) + 1}'})
            clean[pid] = cs

        out = M / 'subjects' / sid / f'{sid}-cards.jsonl'
        with out.open('w', encoding='utf-8') as fh:
            for pid in want:
                fh.write(json.dumps({'id': pid, 'cards': clean[pid]}, ensure_ascii=False) + '\n')

        n = sum(len(v) for v in clean.values())
        lens = [len(c['back']) for v in clean.values() for c in v]
        flens = [len(c['front']) for v in clean.values() for c in v]
        # 章级配额核验（仅 812 有硬约束）
        if sid == '812':
            import collections
            per = collections.defaultdict(collections.Counter)
            for pid, cs in clean.items():
                for c in cs:
                    per[chap_of[pid]][c['kind']] += 1
            for chid, cnt in sorted(per.items()):
                for k, need in QUOTA_812.items():
                    if cnt.get(k, 0) < need:
                        problems.append(f'812 {chid} {k} 仅 {cnt.get(k, 0)} 张 < 配额 {need}')
        print(f'  {sid}: 点 {len(clean)} · 卡 {n} → {out.name}'
              f'  · front {min(flens)}-{max(flens)} 字 · back {min(lens)}-{max(lens)} 字')

    if problems:
        print(f'\n问题 {len(problems)} 条：')
        for p in problems[:25]:
            print('  ', p)
        if len(problems) > 25:
            print(f'   …其余 {len(problems) - 25} 条省略')
    else:
        print('\n卡片校验通过')


if __name__ == '__main__':
    main()
