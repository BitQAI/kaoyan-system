#!/usr/bin/env python3
"""补图建议：按知识点类型/梯队/优先级给未配图的点打分，输出候选清单。

用法：python3 scripts/suggest_media.py [--threshold 8]
输出：research/812-media-suggestions.md + 终端摘要
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'
OUT = META / 'research' / '812-media-suggestions.md'

# 机制/流程/结构/对比/因果链关键词
KEY = ['机制', '途径', '过程', '阶段', '步骤', '循环', '链', '结构', '关系',
       '对比', '分室', '运输', '调控', '信号', '平衡', '曲线', '差异', '类型',
       '组成', '来源', '去向', '条件', '效应']
TYPE_SCORE = {'过程': 3, '辨析': 3, '原理': 2, '应用': 1}
PRIO = {'★': 3, '●': 2, '○': 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--threshold', type=int, default=8)
    args = ap.parse_args()
    d = json.loads((META / 'subjects/812/812.json').read_text(encoding='utf-8'))
    tier = {c['id']: c['tier'] for c in d['chapters']}
    rows = []
    for p in d['points']:
        if p.get('media'):
            continue
        score = {1: 3, 2: 2, 3: 1}.get(tier.get(p['chapter']), 1) + PRIO.get(p['priority'], 1)
        reasons = []
        types = {c.get('card_type') for c in p.get('cards') or []}
        for t, s in TYPE_SCORE.items():
            if t in types:
                score += s
                reasons.append(f'{t}卡')
                break
        text = (p.get('title') or '') + (p.get('explain') or '')
        hits = [k for k in KEY if k in text]
        score += min(len(hits), 4)
        if hits:
            reasons.append('关键词:' + '/'.join(hits[:4]))
        if score >= args.threshold:
            rows.append({
                'id': p['id'], 'title': p['title'], 'chapter': p['chapter'],
                'tier': tier.get(p['chapter']), 'priority': p['priority'],
                'score': score, 'reasons': '; '.join(reasons) or '—',
            })
    rows.sort(key=lambda r: (-r['score'], r['chapter'], r['id']))
    lines = ['# 812 补图候选清单', '',
             f'> 门槛：score ≥ {args.threshold}；仅列未配图点。',
             '> 评分 = 梯队(3/2/1) + 优先级(3/2/1) + 卡型(过程/辨析3、原理2、应用1) + 关键词命中(≤4)。',
             '',
             '| 知识点 | 标题 | 章 | 梯队 | 优先级 | 分数 | 理由 |',
             '|---|---|---|---|---|---|---|']
    for r in rows:
        lines.append(f"| {r['id']} | {r['title']} | {r['chapter']} | {r['tier']} | "
                     f"{r['priority']} | {r['score']} | {r['reasons']} |")
    OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'未配图点 {sum(1 for p in d["points"] if not p.get("media"))}，'
          f'候选 {len(rows)}，输出 {OUT.relative_to(ROOT)}')
    for r in rows[:15]:
        print(f"  {r['score']:>2}  {r['id']}  {r['title']}  [{r['reasons']}]")


if __name__ == '__main__':
    main()
