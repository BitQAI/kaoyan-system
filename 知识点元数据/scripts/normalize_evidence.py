#!/usr/bin/env python3
"""按统一口径复核四科 exam_evidence，输出差异清单。

口径（= 字段字典.md §六 的可执行版本）：
  verified = 官方考纲**条款**或**指定教材**正文直接支持该点
             → 必须有条款级定位（clause），或来源是 syl-* / 考纲指定参考书
  inferred = 有官方大纲/教材的章节级背景，但未落到条款；或多个可靠二手来源交叉
  pending  = 仅推理，或来源不在台账 —— 必须登记 issues，不得标注考频

关键区分：syl-315 这类「整份大纲」不算条款级依据。整份大纲只能证明「这门课考这些内容」，
不能证明「这个考点对应这一条」。101/204 全科 inferred 正是这个原因（basis 自述未做条款级对齐）。

条款级对齐结果来自 .build/sdd/align/out/*.jsonl（point_id + clause + level + basis + sources）。

用法：
  python3 scripts/normalize_evidence.py                 # 报告
  python3 scripts/normalize_evidence.py --align-only     # 只统计可用于升级的条款
  python3 scripts/normalize_evidence.py --write          # 写回（保留 level_history）
"""
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
META = ROOT / '知识点元数据'
ALIGN = ROOT / '.build/sdd/align/out'


def load_ledger(sid):
    p = META / 'research' / f'{sid}-sources.md'
    out = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding='utf-8').splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 4 or cells[0] == 'id' or set(cells[0]) <= {'-'}:
            continue
        out[cells[0]] = {'type': cells[1], 'reliability': cells[2],
                         'title': cells[3], 'note': cells[-1]}
    return out


def designated_textbooks(ledger):
    """台账 note 里写明是考纲参考书/指定参考书的教材 id。"""
    return {k for k, m in ledger.items()
            if m['type'] == 'textbook' and ('参考书' in m['note'] or '指定' in m['note'])}


def load_align():
    """→ {point_id: row}"""
    rows = {}
    if not ALIGN.exists():
        return rows
    for f in sorted(ALIGN.glob('*.jsonl')):
        for line in f.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            rows[r['point_id']] = r
    return rows


def grade(ev, ledger, books, align_row):
    srcs = [s.get('id', '') for s in (ev.get('sources') or [])]
    basis = ev.get('basis') or ''
    # 有条款级对齐结果时，以对齐结论为准 —— 它已经判断过「大纲里到底有没有这一条」。
    # 不能因为 basis 长得像「考纲条款…「…」」就一律升级：inferred 的对齐行恰恰是
    # 大纲无对应条目、只能锚最近父条目的情况。
    if align_row and align_row.get('clause'):
        lvl = align_row.get('level') or 'inferred'
        return lvl, f'条款级对齐 {align_row["clause"]}（对齐判定 {lvl}）'
    sylv = [s for s in srcs if s.startswith(('syl-', 'syllabus')) and s.count('-') >= 2]
    if sylv:
        return 'verified', '考纲条款级来源: ' + ','.join(sylv)
    # 无条款级对齐的科目（812/315）：整份大纲 id + basis 逐字引用条目原文 = 已有条款级定位
    if any(s.startswith(('syl-', 'syllabus')) for s in srcs) and '「' in basis and '」' in basis:
        return 'verified', 'basis 逐字引用大纲条目'
    books_ok = [s for s in srcs if s in books]
    if books_ok:
        return 'verified', '指定教材: ' + ','.join(books_ok)
    known = [s for s in srcs if s in ledger]
    if len(known) >= 2:
        return 'inferred', '章节级/二手交叉: ' + ','.join(known)
    if len(known) == 1:
        return 'pending', '仅 1 个可识别来源: ' + known[0]
    return 'pending', '来源不在台账: ' + (','.join(srcs) or '无')


def main(mode):
    align = load_align()
    for sid in ('812', '315', '101', '204'):
        ledger = load_ledger(sid)
        if not ledger:
            print(f'{sid}: 无来源台账，跳过')
            continue
        books = designated_textbooks(ledger)
        jf = META / 'subjects' / sid / f'{sid}.json'
        doc = json.loads(jf.read_text(encoding='utf-8'))
        before, after = collections.Counter(), collections.Counter()
        changes, aligned = [], 0
        for p in doc['points']:
            ev = p.get('exam_evidence') or {}
            if not ev:
                continue
            before[ev.get('level')] += 1
            ar = align.get(p['id'])
            if ar and ar.get('clause'):
                aligned += 1
            lvl, why = grade(ev, ledger, books, ar)
            after[lvl] += 1
            if lvl != ev.get('level'):
                changes.append((p['id'], ev.get('level'), lvl, why))
        print(f'{sid}: {dict(before)} → {dict(after)}  变更 {len(changes)}  '
              f'可用的条款级对齐 {aligned}/{len(doc["points"])}')
        if mode == 'align-only':
            continue
        for c in changes[:10]:
            print(f'   {c[0]} {c[1]} → {c[2]}  ({c[3]})')
        if len(changes) > 10:
            print(f'   …其余 {len(changes) - 10} 条')
        if mode == 'write' and changes:
            for p in doc['points']:
                ev = p.get('exam_evidence') or {}
                if not ev:
                    continue
                lvl, why = grade(ev, ledger, books, align.get(p['id']))
                if lvl == ev.get('level'):
                    continue
                ev.setdefault('level_history', [])
                ev['level_history'].append({'from': ev['level'], 'to': lvl,
                                            'why': why, 'date': '2026-10-28'})
                ev['level'] = lvl
            jf.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
            print(f'   已写回 {jf.relative_to(ROOT)}')


if __name__ == '__main__':
    main('write' if '--write' in sys.argv else ('align-only' if '--align-only' in sys.argv else 'report'))
