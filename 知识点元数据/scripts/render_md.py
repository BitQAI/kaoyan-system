#!/usr/bin/env python3
"""extract.json → 各科 md（人审真源）。

md 是唯一人工编辑入口；json 是机洗真源。两者由本脚本与 build.py 保持一致。
"""
import json
import pathlib
import re
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent      # master_eaxm/
META = ROOT / '知识点元数据'
BUILD = ROOT / '.build'

POINT_COLS = ['id', 'chapter', 'point', 'title', 'explain', 'exam',
              'keywords', 'priority', 'tags', 'source', 'spoken']
CHAP_COLS = ['id', 'name', 'module', 'tier', 'weight_center',
             'weight_range', 'weight_basis', 'entry_count']


def cell(v):
    """单元格净化：禁 | 与换行（法考框架 §4.3）。"""
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (list, tuple)):
        v = '/'.join(str(x) for x in v)
    if isinstance(v, dict):
        v = ';'.join(f'{k}={x}' for k, x in v.items())
    s = str(v)
    s = s.replace('|', '｜').replace('\r', ' ').replace('\n', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def source_cell(p):
    """溯源单元格：ref;basis[;outline=…]（文件名在 front matter，不逐行重复）。"""
    src = p.get('source') or {}
    parts = [src.get('ref', '')]
    if src.get('basis'):
        parts.append(src['basis'])
    if src.get('outline'):
        parts.append(f"outline={src['outline']}")
    return ';'.join(x for x in parts if x)


def load_enrich(sid):
    """读 subjects/<sid>/<sid>-enrich.jsonl（LLM 增强产物）"""
    p = META / 'subjects' / sid / f'{sid}-enrich.jsonl'
    out = {}
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            if line.strip():
                r = json.loads(line)
                out[r['id']] = r
    return out


def render_subject(sub, enrich):
    L = []
    L.append('---')
    L.append(f"subject: {sub['id']}")
    L.append(f"name: {sub['name']}")
    L.append(f"score: {sub['score']}")
    L.append('status: draft')
    L.append('schema: ky-point/2.0')
    L.append(f"source_file: {sub.get('source_file', '')}")
    L.append(f"updated: {date.today().isoformat()}")
    L.append('---')
    L.append('')
    L.append(f"# {sub['id']} {sub['name']} · 章节表")
    L.append('')
    L.append('| ' + ' | '.join(CHAP_COLS) + ' |')
    L.append('|' + '---|' * len(CHAP_COLS))
    for c in sub['chapters']:
        vals = []
        for k in CHAP_COLS:
            v = c.get(k)
            if k == 'weight_range' and v:
                v = f'[{v[0]},{v[1]}]'
            vals.append(cell(v))
        L.append('| ' + ' | '.join(vals) + ' |')
    L.append('')
    L.append(f"# {sub['id']} {sub['name']} · 知识点表")
    L.append('')
    L.append('| ' + ' | '.join(POINT_COLS) + ' |')
    L.append('|' + '---|' * len(POINT_COLS))
    for p in sub['points']:
        e = enrich.get(p['id']) or {}
        p['title'] = e.get('title', '')
        p['explain'] = e.get('explain', '')
        p['exam'] = e.get('exam', '')
        p['keywords'] = e.get('keywords', [])
        row = []
        for k in POINT_COLS:
            if k == 'source':
                row.append(cell(source_cell(p)))
            elif k == 'keywords':
                row.append(cell('[' + '/'.join(p.get('keywords') or []) + ']'))
            elif k == 'tags':
                row.append(cell('[' + '/'.join(p.get('tags') or []) + ']'))
            else:
                row.append(cell(p.get(k)))
        L.append('| ' + ' | '.join(row) + ' |')
    L.append('')
    L.append(f"# {sub['id']} {sub['name']} · 知识点关联表")
    L.append('')
    L.append('| id | prerequisites | related | confusables | evidence |')
    L.append('|---|---|---|---|---|')
    for p in sub['points']:
        L.append(f"| {p['id']} | — | — | — | — |")
    L.append('')
    return '\n'.join(L)


def main():
    data = json.loads((BUILD / 'extract.json').read_text(encoding='utf-8'))
    for sub in data['subjects']:
        sub['source_file'] = data['source']['file']
        enrich = load_enrich(sub['id'])
        out = META / 'subjects' / sub['id'] / f"{sub['id']}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_subject(sub, enrich), encoding='utf-8')
        hit = sum(1 for p in sub['points'] if (enrich.get(p['id']) or {}).get('explain'))
        print(f"  {out.relative_to(ROOT)}  {out.stat().st_size:,} bytes  "
              f"章 {len(sub['chapters'])} · 点 {len(sub['points'])} · LLM 增强 {hit}/{len(sub['points'])}")


if __name__ == '__main__':
    main()
