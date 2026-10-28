#!/usr/bin/env python3
"""812 v3 质量审计：原子度、覆盖率、重复题、卡型分布。

用法：python3 scripts/audit_v3.py [--sid 812]
退出码：有重复设问时为 1。
"""
import collections
import json
import pathlib
import re
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'


def norm(s):
    return re.sub(r'\s+', '', s or '')


def audit(sid='812'):
    d = json.loads((META / 'subjects' / sid / f'{sid}.json').read_text(encoding='utf-8'))
    pts = d['points']
    cards = [c for p in pts for c in p.get('cards') or []]
    q = collections.Counter(norm(c.get('question')) for c in cards)
    dup = {k: v for k, v in q.items() if k and v > 1}
    cpp = [len(p.get('cards') or []) for p in pts]
    ctypes = collections.Counter(c.get('card_type') for c in cards)
    kinds = collections.Counter(c.get('kind') for c in cards)
    ev = collections.Counter((p.get('exam_evidence') or {}).get('level') for p in pts)
    covered, total = 0, 0
    for p in pts:
        n = len(p.get('units') or [])
        refs = {r for c in p.get('cards') or [] for r in (c.get('unit_refs') or [])}
        total += n
        covered += len([i for i in range(1, n + 1) if i in refs])

    lines = [
        f'# {sid} v3 质量审计', '',
        f'- 知识点：{len(pts)}',
        f'- 卡片：{len(cards)}',
        f'- 每点卡片 min/中位/max：{min(cpp)}/{statistics.median(cpp):.0f}/{max(cpp)}',
        f'- 重复设问：{len(dup)}',
        f'- unit 覆盖：{covered}/{total} ({covered / max(total, 1) * 100:.1f}%)',
        '', '## 卡片类型分布', '', '| card_type | 数量 |', '|---|---|',
    ]
    for k, v in ctypes.most_common():
        lines.append(f'| {k or "（缺）"} | {v} |')
    lines += ['', '## 卷面题型分布', '', '| kind | 数量 |', '|---|---|']
    for k, v in kinds.most_common():
        lines.append(f'| {k or "（缺）"} | {v} |')
    lines += ['', '## 证据等级分布', '', '| level | 点数 |', '|---|---|']
    for k, v in ev.most_common():
        lines.append(f'| {k or "（缺）"} | {v} |')
    if dup:
        lines += ['', '## 重复设问清单', '', '| 设问 | 次数 |', '|---|---|']
        for k, v in sorted(dup.items(), key=lambda x: -x[1]):
            lines.append(f'| {k[:60]} | {v} |')

    out = META / 'research' / f'{sid}-audit.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines[:12]))
    return 1 if dup else 0


if __name__ == '__main__':
    sid = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == '--sid' else '812'
    sys.exit(audit(sid))
