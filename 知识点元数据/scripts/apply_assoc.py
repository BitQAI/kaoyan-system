#!/usr/bin/env python3
"""校验并落地 315/101/204 的关联数据（前置 / 相关 / 易混）。

代理产出去 `research/assoc/out/<sid>-aN.jsonl`，每行一个点：
  {"id":"3150101","prerequisites":["3150102"],"related":["3150103"],
   "confusables":[{"name":"真溶液 vs 胶体","point_id":"3150103","distinction":"粒子直径以 1 nm 为界"}]}

落地写 `<sid>.md` 的知识点关联表第 2–4 列，evidence 列不动。

    python3 scripts/apply_assoc.py 315            # 只校验
    python3 scripts/apply_assoc.py 315 --write    # 校验通过后写入 md
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
META = ROOT / '知识点元数据'
OUT = META / 'research/assoc/out'
MAX_PRE, MAX_REL, MAX_CONF = 3, 3, 2
MAX_NAME, MAX_DIST = 20, 60


def load_subject(sid):
    d = json.loads((META / 'subjects' / sid / f'{sid}.json').read_text(encoding='utf-8'))
    return {p['id']: p for p in d['points']}


def validate(sid):
    pts = load_subject(sid)
    rows, probs = {}, []
    files = sorted(OUT.glob(f'{sid}-a*.jsonl'))
    if not files:
        return rows, [f'{sid}: 没有产出文件']
    for f in files:
        for line in f.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                probs.append(f'{f.name}: JSON 解析失败 {e}')
                continue
            pid = r.get('id')
            if pid not in pts:
                probs.append(f'{f.name}: 未知知识点 {pid}')
                continue
            if pid in rows:
                probs.append(f'{f.name}: {pid} 重复出现')
                continue
            rows[pid] = r
    missing = [p for p in pts if p not in rows]
    if missing:
        probs.append(f'{sid}: 缺 {len(missing)} 个点（如 {missing[:5]}）')
    for pid, r in rows.items():
        pre = r.get('prerequisites') or []
        rel = r.get('related') or []
        conf = r.get('confusables') or []
        for field, arr, cap in (('prerequisites', pre, MAX_PRE), ('related', rel, MAX_REL)):
            if len(arr) > cap:
                probs.append(f'{pid} {field} 超过 {cap} 个（{len(arr)}）')
            if len(set(arr)) != len(arr):
                probs.append(f'{pid} {field} 有重复')
            for x in arr:
                if x == pid:
                    probs.append(f'{pid} {field} 引用了自己')
                elif x not in pts:
                    probs.append(f'{pid} {field} 引用了不存在的 {x}')
        if len(conf) > MAX_CONF:
            probs.append(f'{pid} confusables 超过 {MAX_CONF} 个')
        for c in conf:
            if not (c.get('name') or '').strip():
                probs.append(f'{pid} confusable 缺 name')
            elif len(c['name']) > MAX_NAME:
                probs.append(f'{pid} confusable name 超 {MAX_NAME} 字：{c["name"]}')
            if not (c.get('distinction') or '').strip():
                probs.append(f'{pid} confusable 缺 distinction')
            elif len(c['distinction']) > MAX_DIST:
                probs.append(f'{pid} confusable distinction 超 {MAX_DIST} 字')
            t = c.get('point_id')
            if '|' in (c.get('name') or '') or '|' in (c.get('distinction') or ''):
                probs.append(f'{pid} confusable 含竖线 |，会破坏 md 表格')
            if t == pid:
                probs.append(f'{pid} confusable 指向自己')
            elif t and t not in pts:
                probs.append(f'{pid} confusable 指向不存在的 {t}')
    return rows, probs


def write_md(sid, rows):
    mf = META / 'subjects' / sid / f'{sid}.md'
    lines = mf.read_text(encoding='utf-8').splitlines(keepends=True)
    in_assoc, n = False, 0
    for i, l in enumerate(lines):
        if l.startswith('# ') and '关联表' in l:
            in_assoc = True
            continue
        if in_assoc and l.startswith('# '):
            in_assoc = False
        if not in_assoc or not l.startswith('| '):
            continue
        cells = l.rstrip('\n').split('|')
        if len(cells) != 7:
            continue
        pid = cells[1].strip()
        r = rows.get(pid)
        if not r:
            continue
        pre = '/'.join(r.get('prerequisites') or []) or '—'
        rel = '/'.join(r.get('related') or []) or '—'
        conf = json.dumps(r.get('confusables') or [], ensure_ascii=False,
                          separators=(',', ':')) if r.get('confusables') else '—'
        cells[2] = f' {pre} '
        cells[3] = f' {rel} '
        cells[4] = f' {conf} '
        lines[i] = '|'.join(cells) + '\n'
        n += 1
    mf.write_text(''.join(lines), encoding='utf-8')
    return n


def main(sid, do_write):
    rows, probs = validate(sid)
    filled = sum(1 for r in rows.values()
                 if r.get('prerequisites') or r.get('related') or r.get('confusables'))
    conf_n = sum(len(r.get('confusables') or []) for r in rows.values())
    print(f'{sid}: {len(rows)} 行，有关系的 {filled}，易混条目 {conf_n}')
    for p in probs[:25]:
        print('  FAIL', p)
    if len(probs) > 25:
        print(f'  …其余 {len(probs) - 25} 条')
    print('问题数', len(probs))
    if probs or not do_write:
        return 1 if probs else 0
    n = write_md(sid, rows)
    print(f'已写入 {sid}.md 关联表 {n} 行')
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('sid')
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    sys.exit(main(a.sid, a.write))
