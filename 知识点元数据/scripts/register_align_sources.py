#!/usr/bin/env python3
"""把 .build/sdd/align/out 里出现的来源登记进 research/<sid>-sources.md。

对齐行用的是 {title, url}，而 exam_evidence 按 id 查台账。不登记的话
normalize_evidence.py 会把它们判成「来源不在台账」并降级为 pending。

规则：
  - 已存在的同一 url（或同一 title）复用原有 id，不重复登记
  - 新来源按 ali-<sid>-<序号> 编号，reliability 依域名判断：
      官方域名（gov.cn / neea / 考试院 / edu.cn / 人大网 等）→ primary
      encyclopedic / 教辅 / 机构 → secondary
  - 幂等：重复运行不新增行

    python3 scripts/register_align_sources.py            # 只报告
    python3 scripts/register_align_sources.py --write    # 写入台账
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
META = ROOT / '知识点元数据'
ALIGN = ROOT / '.build/sdd/align/out'

PRIMARY = re.compile(
    r'(gov\.cn|neea\.edu\.cn|\.edu\.cn|shmeea|bjeea|ynau\.edu|12371\.cn|news\.cn|'
    r'npc\.gov\.cn|moe\.gov\.cn|kaoyan\.cn/file)')
BLOCK = re.compile(r'(xdf\.cn|koolearn|buu\.edu\.cn)')


def load_ledger_rows(path):
    """→ [(id, url, title)]"""
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 6 or cells[0] == 'id' or set(cells[0]) <= {'-'}:
            continue
        rows.append((cells[0], cells[5] if len(cells) > 5 else '', cells[3]))
    return rows


def main(write):
    align = {}
    for f in sorted(ALIGN.glob('*.jsonl')):
        for line in f.read_text(encoding='utf-8').splitlines():
            if line.strip():
                r = json.loads(line)
                align[r['point_id']] = r
    for sid in ('101', '204'):
        seen = {}
        for pid, r in align.items():
            if not pid.startswith(sid):
                continue
            for s in r.get('sources') or []:
                url = (s.get('url') or '').strip()
                title = (s.get('title') or '').strip()
                if not title:
                    continue
                seen[(url, title)] = seen.get((url, title), 0) + 1
        path = META / 'research' / f'{sid}-sources.md'
        known = load_ledger_rows(path)
        by_url = {u: i for i, u, _t in known if u}
        by_title = {t: i for i, _u, t in known if t}
        new, blocked = [], []
        for (url, title), n in sorted(seen.items(), key=lambda x: -x[1]):
            if (url and url in by_url) or title in by_title:
                continue
            if (url and BLOCK.search(url)) or 'buu.edu.cn' in url:
                blocked.append((url, title, n))
                continue
            # 大纲原文整理（本地大源）等同官方大纲文本
            official = (url and PRIMARY.search(url)) or '统考三科大纲知识点全景' in title
            rel = 'primary' if official else 'secondary'
            new.append((url, title, rel, n))
        if blocked:
            print(f'   跳过污染源 {len(blocked)} 个: ' + ', '.join(t[:30] for _u, t, _n in blocked[:3]))
        print(f'{sid}: 对齐来源 {len(seen)} 个，已登记 {len(seen) - len(new) - len(blocked)}，'
              f'新增 {len(new)}（primary {sum(1 for x in new if x[2] == "primary")}）')
        for url, title, rel, n in new[:8]:
            print(f'   + {rel} {title[:52]}  ({n} 处引用)')
        if len(new) > 8:
            print(f'   …其余 {len(new) - 8} 个')
        if not write or not new:
            continue
        n0 = 0
        for i, _u, _t in known:
            m = re.fullmatch(rf'ali-{sid}-(\d+)', i)
            if m:
                n0 = max(n0, int(m.group(1)))
        lines = []
        for k, (url, title, rel, n) in enumerate(new, 1):
            n0 += 1
            uid = f'ali-{sid}-{n0:03d}'
            title_c = title.replace('|', '｜')
            lines.append(f'| {uid} | align | {rel} | {title_c} | 全文 | {url} | 2026-10-28 | '
                         f'条款级对齐引用 {n} 处 |')
        block = '\n'.join(lines) + '\n'
        text = path.read_text(encoding='utf-8')
        marker = '\n## 对齐来源（2026-10-28 条款级对齐新增）\n\n'
        if marker not in text:
            text = text.rstrip('\n') + '\n' + marker + '| id | type | reliability | title | locator | url | accessed | note |\n|---|---|---|---|---|---|---|---|\n' + block
        else:
            text = text.rstrip('\n') + '\n' + block
        path.write_text(text, encoding='utf-8')
        print(f'   已写 {path.relative_to(ROOT)}（+{len(new)} 行）')


if __name__ == '__main__':
    main('--write' in sys.argv)
