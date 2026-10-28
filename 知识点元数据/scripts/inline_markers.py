#!/usr/bin/env python3
"""把 SVG 里的 <marker> 箭头改成内联三角形。

marker 需要 <defs> + 唯一 id，多张图拼在同一页面时会撞号。内联三角形不依赖
id，也不受 markerUnits 在不同渲染器下的差异影响。

用法：
  python3 scripts/inline_markers.py --dry-run    # 只报告
  python3 scripts/inline_markers.py             # 写回 *-media.json
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SUBJ = ROOT / '知识点元数据/subjects'

MARKER_DEF = re.compile(
    r'<marker\b(?P<attrs>[^>]*)>(?P<body>.*?)</marker>', re.S)
DEFS_EMPTY = re.compile(r'<defs>\s*</defs>')
PATH_WITH_MARKER = re.compile(
    r'<path\b(?P<attrs>[^>]*?)\s*marker-(?:end|start)="url\(#(?P<mid>[^)]+)\)"(?P<tail>[^>]*)/>')
NUM = re.compile(r'-?\d+(?:\.\d+)?')


def parse_d(d):
    """返回 (命令列表, 终点, 终点切向)。

    只处理本库用到的 M/L/Q/C/Z。切线取进入终点的那一段的导数方向。
    """
    toks = re.findall(r'[MLQCZmlqcz]|-?\d+(?:\.\d+)?', d)
    i = 0
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    tangent = (1.0, 0.0)
    while i < len(toks):
        c = toks[i]
        i += 1
        if c in 'ML':
            x, y = float(toks[i]), float(toks[i + 1]); i += 2
            if c == 'L':
                tangent = (x - cur[0], y - cur[1])
            cur = (x, y)
            if c == 'M':
                start = cur
        elif c in 'QC':
            if c == 'Q':
                cx, cy = float(toks[i]), float(toks[i + 1]); i += 2
            else:
                float(toks[i]); float(toks[i + 1]); i += 2
                cx, cy = float(toks[i]), float(toks[i + 1]); i += 2
            x, y = float(toks[i]), float(toks[i + 1]); i += 2
            tangent = (x - cx, y - cy)
            cur = (x, y)
        elif c in 'Zz':
            cur = start
        else:
            raise ValueError(f'不支持的命令 {c!r} in {d!r}')
    return cur, tangent


def triangle(end, tangent, size=7.0, color='currentColor'):
    ex, ey = end
    tx, ty = tangent
    n = (tx * tx + ty * ty) ** 0.5 or 1.0
    ux, uy = tx / n, ty / n
    # 底边中心退后 size*0.8，底边半宽 size*0.45
    bx, by = ex - ux * size * 0.8, ey - uy * size * 0.8
    px, py = -uy, ux
    w = size * 0.45
    pts = [(ex, ey), (bx + px * w, by + py * w), (bx - px * w, by - py * w)]
    s = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
    return f'<polygon points="{s}" fill="{color}"/>'


def convert(svg):
    if '<marker' not in svg:
        return svg, 0
    fills = {}
    for m in MARKER_DEF.finditer(svg):
        mid = re.search(r'id="([^"]+)"', m.group('attrs'))
        f = re.search(r'fill="([^"]+)"', m.group('body'))
        if mid:
            fills[mid.group(1)] = f.group(1) if f else 'currentColor'
    svg = MARKER_DEF.sub('', svg)
    svg = DEFS_EMPTY.sub('', svg)

    count = 0

    def rep(m):
        nonlocal count
        attrs, mid = m.group('attrs'), m.group('mid')
        tail = m.group('tail')
        dd = re.search(r'\sd="([^"]*)"', attrs)
        if not dd:
            return m.group(0)
        end, tan = parse_d(dd.group(1))
        tri = triangle(end, tan, color=fills.get(mid, 'currentColor'))
        attrs = re.sub(r'\s*marker-(?:end|start)="[^"]*"', '', attrs)
        count += 1
        return f'<path{attrs}{tail}/>{tri}'

    svg = PATH_WITH_MARKER.sub(rep, svg)
    return svg, count


def main(dry):
    total = 0
    for path in sorted(SUBJ.glob('*/*-media.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        changed = 0
        for pid, items in doc.items():
            if not isinstance(items, list):
                continue
            for it in items:
                s = it.get('svg') or ''
                if '<marker' not in s:
                    continue
                new, n = convert(s)
                if '<marker' in new:
                    print(f'  残留 marker: {path.name} {pid}')
                it['svg'] = new
                changed += n
        if changed:
            total += changed
            print(f'{path.relative_to(ROOT)}: {changed} 个箭头内联')
            if not dry:
                path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    print('总计', total, '（dry-run，未写回）' if dry else '（已写回）')


if __name__ == '__main__':
    main('--dry-run' in sys.argv)
