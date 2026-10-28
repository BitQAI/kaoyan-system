#!/usr/bin/env python3
"""把 .build/sdd/align/out 的条款级对齐结果写进 subjects/*.md 的关联表。

只改关联表的 evidence 单元格；其它行、其它列一律不动。
写入内容 = 对齐行的 {level, basis, sources}，basis 末尾附条款号与条款原文，便于回查。

    python3 scripts/apply_alignment.py            # 报告将改动多少
    python3 scripts/apply_alignment.py --write    # 写入 md
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import normalize_evidence as NE  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
META = ROOT / '知识点元数据'
ALIGN = ROOT / '.build/sdd/align/out'
MAX_BASIS = 180  # 关联表单元格保持一行可读


def load_align():
    rows = {}
    if not ALIGN.exists():
        return rows
    for f in sorted(ALIGN.glob('*.jsonl')):
        for line in f.read_text(encoding='utf-8').splitlines():
            if line.strip():
                r = json.loads(line)
                rows[r['point_id']] = r
    return rows


def ledger_index(path):
    """→ {(title, url): id}，以及按 title 的兜底索引。台账里的 title 与 url 可能各占一列。"""
    exact, by_title = {}, {}
    if not path.exists():
        return exact, by_title
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 6 or cells[0] == 'id' or set(cells[0]) <= {'-'}:
            continue
        exact[(cells[3], cells[5])] = cells[0]
        by_title.setdefault(cells[3], cells[0])
    return exact, by_title


def build_evidence(r, ledger):
    """把对齐行的 sources 映射回台账 id —— 证据复核按 id 查台账，只留 title/url 会被判 pending。"""
    clause = r.get('clause') or ''
    text = (r.get('clause_text') or '').strip()
    basis = f'考纲条款 {clause}「{text}」'
    extra = (r.get('basis') or '').strip()
    if extra and len(basis) + len(extra) + 2 <= MAX_BASIS:
        basis += '；' + extra
    exact, by_title = ledger
    srcs = []
    for s in r.get('sources') or []:
        sid = s.get('id')
        if not sid:
            title = (s.get('title') or '').strip()
            url = (s.get('url') or '').strip()
            sid = exact.get((title, url)) or by_title.get(title)
        srcs.append({'id': sid} if sid else {'title': s.get('title'), 'url': s.get('url')})
    return {'level': r.get('level'), 'basis': basis, 'sources': srcs, 'clause': clause}


def main(write):
    align = load_align()
    for sid in ('101', '204'):
        rows_of = {pid: r for pid, r in align.items() if pid.startswith(sid)}
        if not rows_of:
            print(f'{sid}: 无对齐结果')
            continue
        ledger = ledger_index(META / 'research' / f'{sid}-sources.md')
        mf = META / 'subjects' / sid / f'{sid}.md'
        lines = mf.read_text(encoding='utf-8').splitlines(keepends=True)
        in_assoc, n, skipped = False, 0, []
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
            r = rows_of.get(pid)
            if not r:
                skipped.append(pid)
                continue
            ev = build_evidence(r, ledger)
            cells[5] = ' ' + json.dumps(ev, ensure_ascii=False, separators=(',', ':')) + ' '
            lines[i] = '|'.join(cells) + '\n'
            n += 1
        print(f'{sid}: 写入 {n} 行（对齐 {len(rows_of)} 点，未对齐 {len(skipped)} 点）')
        if skipped[:5]:
            print('   未对齐示例', skipped[:5])
        if write:
            mf.write_text(''.join(lines), encoding='utf-8')
            print(f'   已写 {mf.relative_to(ROOT)}')


if __name__ == '__main__':
    main('--write' in sys.argv)
