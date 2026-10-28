#!/usr/bin/env python3
"""为未配图的点生成四类模板图（概念/流程/清单/对比）。

按画布宽度换行、断句不截词；对比图支持 2–3 项。
用法：python3 scripts/gen_media_templates.py
只重写 caption 以「· 对比图/流程图/清单图/知识结构图」结尾的条目。
"""
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = ROOT / '知识点元数据/subjects/812/812-media.json'
JSON = ROOT / '知识点元数据/subjects/812/812.json'
GREEN = '#2f8f5b'
AMBER = '#b26a00'
BADGE = '#256b47'
SOFT = 'rgba(47,143,91,.10)'
TPL_SUFFIX = ('· 对比图', '· 流程图', '· 清单图', '· 知识结构图')

CJK = re.compile(r'[㐀-鿿　-〿＀-￯]')
ORPHAN = re.compile(r'^[，。；：、,;:.!?！？…·“”"‘’\'「」『』（）()《》〈〉【】\[\]—–]+$')


def esc(s):
    return html.escape(str(s), quote=False)


def measure(s, size):
    w = 0.0
    for ch in s:
        w += size if CJK.match(ch) else size * 0.56
    return w


def cut_width(s, size, max_w):
    out, w = '', 0.0
    for ch in s:
        cw = size if CJK.match(ch) else size * 0.56
        if w + cw > max_w:
            break
        out += ch
        w += cw
    return out


def wrap_all(s, size, max_w):
    s = str(s).strip()
    clauses = re.findall(r'[^，。；：、,;:]+[，。；：、,;:]?', s) or [s]
    lines, cur = [], ''
    for c in clauses:
        if measure(cur + c, size) <= max_w:
            cur += c
            continue
        if cur:
            lines.append(cur.strip())
        while measure(c, size) > max_w:
            head = cut_width(c, size, max_w)
            if not head:
                break
            lines.append(head)
            c = c[len(head):]
        cur = c
    if cur.strip():
        lines.append(cur.strip())
    out = []
    for ln in lines:
        if out and ORPHAN.match(ln):
            merged = out[-1] + ln
            if measure(merged, size) <= max_w:
                out[-1] = merged
            # 合并会溢出时直接丢弃孤立标点行，避免半括号/引号单独成行
        else:
            out.append(ln)
    return out or [s]


def text_lines(s, size, max_w, max_lines):
    lines = wrap_all(s, size, max_w)
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    last = kept[-1]
    while last and measure(last + '…', size) > max_w:
        last = last[:-1]
    kept[-1] = last.rstrip('，。；：、,;: ') + '…'
    return kept


def txt(x, y, s, size=11, weight=None, anchor='middle', fill=None):
    w = f' font-weight="{weight}"' if weight else ''
    f = f' fill="{fill}"' if fill else ''
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}"{w}{f}>'
            f'{esc(s)}</text>')


def block(cx, cy, lines, size=11, lh=None, weight=None, fill=None):
    lh = lh or size * 1.45
    n = len(lines)
    y0 = cy - (n - 1) * lh / 2 + size * 0.35
    return ''.join(txt(cx, y0 + i * lh, s, size, weight, fill=fill)
                   for i, s in enumerate(lines))


def rect(x, y, w, h, fill=SOFT, stroke=GREEN):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}"/>'


def arrow(x1, y, x2):
    head = f'<path d="M{x2} {y} L{x2 - 9} {y - 4.5} L{x2 - 9} {y + 4.5} z" fill="currentColor"/>'
    return f'<path d="M{x1} {y} L{x2 - 7} {y}" stroke="currentColor" fill="none"/>{head}'


def svg(title, body):
    return ('<svg viewBox="0 0 640 280" role="img" aria-label="' + esc(title) +
            '" xmlns="http://www.w3.org/2000/svg" fill="currentColor" '
            'style="font-family:inherit;color:inherit">' + body + '</svg>')


def footer(keywords, note=''):
    left = ' · '.join(list(keywords)[:4])
    s = txt(20, 272, text_lines(left, 9.5, 480, 1)[0], 9.5, anchor='start')
    if note:
        s += txt(620, 272, note, 9, anchor='end')
    return s


def header(title):
    return txt(320, 27, title, 15.5, 700)


def grid_svg(title, units, keywords, icon=None, note=''):
    body = header(title)
    for i, u in enumerate(units[:6]):
        x = 21 + (i % 2) * 300
        y = 42 + (i // 2) * 72
        body += rect(x, y, 298, 64)
        lines = text_lines(u, 10.5, 264, 4)
        body += block(x + 149, y + 32, lines, 10.5, 15)
        if icon:
            body += txt(x + 12, y + 18, icon, 10.5, 700, anchor='start', fill=GREEN)
    body += footer(keywords, note)
    return svg(title, body)


def concept_svg(title, units, keywords):
    return grid_svg(title, units, keywords, note='共 %d 条，示 %d 条' % (len(units), min(len(units), 6)))


def list_svg(title, units, keywords):
    return grid_svg(title, units, keywords, icon='✓', note='共 %d 条，示 %d 条' % (len(units), min(len(units), 6)))


def process_svg(title, units, keywords):
    body = header(title)
    steps = units[:4]
    for i, u in enumerate(steps):
        x = 20 + i * 160
        body += rect(x, 46, 138, 190)
        body += f'<circle cx="{x + 16}" cy="{64}" r="9.5" fill="{BADGE}"/>'
        body += txt(x + 16, 68, str(i + 1), 10.5, 700, fill='#fff')
        lines = text_lines(u, 10.5, 116, 7)
        body += block(x + 69, 140, lines, 10.5, 16.5)
        if i < len(steps) - 1:
            body += arrow(x + 139, 140, x + 158)
    body += footer(keywords, '共 %d 条，示 %d 步' % (len(units), len(steps)))
    return svg(title, body)


def split_items(name):
    for sep in (' vs ', ' VS ', '、', ' vs', 'vs ', '与', '和', '/'):
        if sep in name:
            parts = [p.strip() for p in name.split(sep) if p.strip()]
            if len(parts) >= 2 and all(len(p) >= 2 for p in parts):
                return parts[:3]
    return [name]


def compare_svg(title, conf, units, keywords):
    items = split_items(conf.get('name') or title)
    body = header(title)
    n = len(items)
    if n == 2:
        xs, w = [45, 345], 250
    else:
        xs, w = [25, 230, 435], 180
    for i, it in enumerate(items):
        body += rect(xs[i], 40, w, 46, 'rgba(47,143,91,.16)')
        body += txt(xs[i] + w / 2, 68, text_lines(it, 12.5, w - 24, 1)[0], 12.5, 700)
        if i and n == 2:
            body += txt(320, 68, 'vs', 11, 700)
    body += rect(40, 98, 560, 62, 'rgba(178,106,0,.08)', AMBER)
    body += txt(320, 118, '最关键区别', 10.5, 700)
    body += block(320, 140, text_lines(conf.get('distinction') or '', 11, 528, 2), 11, 16)
    for i, u in enumerate(units[:3]):
        x = 32 + i * 196
        body += rect(x, 172, 184, 64)
        body += block(x + 92, 204, text_lines(u, 10, 158, 4), 10, 15)
    body += footer(keywords, '示 %d 条要点' % len(units[:3]))
    return svg(title, body)


def classify(p):
    types = {c.get('card_type') for c in p.get('cards') or []}
    if p.get('confusables'):
        return 'compare'
    if '过程' in types:
        return 'process'
    if '记忆' in types:
        return 'list'
    return 'concept'


def build_one(p):
    units = [u for u in (p.get('units') or []) if str(u).strip()]
    kw = p.get('keywords') or []
    kind = classify(p)
    if kind == 'compare':
        return compare_svg(p['title'], p['confusables'][0], units, kw), p['title'] + ' · 对比图'
    if kind == 'process':
        return process_svg(p['title'], units, kw), p['title'] + ' · 流程图'
    if kind == 'list':
        return list_svg(p['title'], units, kw), p['title'] + ' · 清单图'
    return concept_svg(p['title'], units, kw), p['title'] + ' · 知识结构图'


def main():
    data = json.loads(JSON.read_text(encoding='utf-8'))
    media = json.loads(OUT.read_text(encoding='utf-8'))
    pts = {p['id']: p for p in data['points']}
    rep = 0
    for pid, items in media.items():
        if not items[0].get('caption', '').endswith(TPL_SUFFIX):
            continue
        p = pts[pid]
        svg_txt, cap = build_one(p)
        items[0].update({'kind': 'diagram', 'caption': cap, 'svg': svg_txt,
                         'alt': p['title'] + '；关键要点：' + '；'.join(p['units'][:2])})
        rep += 1
    OUT.write_text(json.dumps(media, ensure_ascii=False, indent=1), encoding='utf-8')
    print('regenerated', rep, 'template diagrams')


if __name__ == '__main__':
    main()
