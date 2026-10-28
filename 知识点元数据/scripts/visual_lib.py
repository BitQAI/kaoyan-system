#!/usr/bin/env python3
"""图示视觉基础库：画布、坐标轴、节点、箭头、图标、文字测量。"""
import html
import math
import re

W, H = 640, 300
CJK = re.compile(r'[㐀-鿿　-〿＀-￯]')

ACCENT = {'812': '#2f8f5b', '315': '#2563eb', '101': '#d9485f', '204': '#7c5cff'}


def esc(s):
    return html.escape(str(s), quote=False)


def measure(s, size):
    return sum(size if CJK.match(ch) else size * 0.56 for ch in str(s))


def cut(s, max_w, size):
    s = str(s).strip()
    if measure(s, size) <= max_w:
        return s
    out = ''
    for ch in s:
        if measure(out + ch + '…', size) > max_w:
            break
        out += ch
    return out.rstrip('，。；：、,;: ') + '…'


def wrap(s, max_w, size, max_lines=2):
    s = str(s).strip()
    lines, cur = [], ''
    for ch in s:
        if measure(cur + ch, size) > max_w:
            lines.append(cur)
            cur = ch
            if len(lines) == max_lines:
                break
        else:
            cur += ch
    else:
        lines.append(cur)
    if len(lines) == max_lines and measure(''.join(lines), size) < measure(s, size):
        lines[-1] = cut(lines[-1] + s[sum(len(x) for x in lines):], max_w, size)
    return lines[:max_lines]


def svg(accent, body, title):
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}" '
            'xmlns="http://www.w3.org/2000/svg" fill="currentColor" '
            'style="font-family:inherit;color:inherit">'
            f'<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{accent}"/>'
            '</marker></defs>' + body + '</svg>')


def title(s, accent, y=26):
    return (f'<text x="320" y="{y}" text-anchor="middle" font-size="15.5" font-weight="700">'
            f'{esc(cut(s, 560, 15.5))}</text>')


def takeaway(s, accent):
    if not s:
        return ''
    lines = wrap(s, 556, 11, 2)
    y0 = 276 if len(lines) == 1 else 264
    out = (f'<rect x="20" y="252" width="600" height="38" rx="8" fill="{accent}" fill-opacity="0.08"/>'
           f'<rect x="20" y="252" width="4" height="38" rx="2" fill="{accent}"/>')
    for i, ln in enumerate(lines):
        out += (f'<text x="34" y="{y0 + i * 15}" font-size="11" fill="currentColor">'
                f'{esc(ln)}</text>')
    return out


def axes(x, y, w, h, xlabel, ylabel, accent):
    out = (f'<path d="M{x} {y + h} L{x + w} {y + h}" stroke="currentColor" stroke-opacity=".55" fill="none"/>'
           f'<path d="M{x} {y + h} L{x} {y}" stroke="currentColor" stroke-opacity=".55" fill="none"/>'
           f'<path d="M{x + w} {y + h} l-7 -4 v8 z" fill="currentColor" fill-opacity=".55"/>'
           f'<path d="M{x} {y} l-4 7 h8 z" fill="currentColor" fill-opacity=".55"/>')
    out += f'<text x="{x + w}" y="{y + h + 18}" text-anchor="end" font-size="10.5">{esc(xlabel)}</text>'
    out += (f'<text x="{x - 10}" y="{y + 8}" text-anchor="middle" font-size="10.5" '
            f'transform="rotate(-90 {x - 10} {y + 8})">{esc(ylabel)}</text>')
    return out


def curve(pts, accent, dashed=False, fill=False):
    d = 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in pts)
    dash = ' stroke-dasharray="6 5"' if dashed else ''
    if fill:
        area = d + f' L{pts[-1][0]:.1f} 230 L{pts[0][0]:.1f} 230 Z'
        return (f'<path d="{area}" fill="{accent}" fill-opacity=".12" stroke="none"/>'
                f'<path d="{d}" stroke="{accent}" stroke-width="2.5" fill="none"{dash}/>')
    return f'<path d="{d}" stroke="{accent}" stroke-width="2.5" fill="none"{dash}/>'


def dot(x, y, label, accent, dx=0, dy=-12, anchor='middle'):
    return (f'<circle cx="{x}" cy="{y}" r="4.5" fill="{accent}"/>'
            f'<circle cx="{x}" cy="{y}" r="8" fill="{accent}" fill-opacity=".18"/>'
            f'<text x="{x + dx}" y="{y + dy}" text-anchor="{anchor}" font-size="10.5" '
            f'font-weight="600">{esc(cut(label, 130, 10.5))}</text>')


def node(x, y, w, h, label, accent, sub='', icon=None, fill_opacity=.10):
    out = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{accent}" '
           f'fill-opacity="{fill_opacity}" stroke="{accent}" stroke-opacity=".65"/>')
    if icon:
        out += icon_svg(icon, x + 16, y + 16, 20, accent)
        tx, ty = x + w / 2 + 10, y + h / 2 + 4
    else:
        tx, ty = x + w / 2, y + h / 2 + 4
    out += (f'<text x="{tx}" y="{ty - (7 if sub else 0)}" text-anchor="middle" font-size="12.5" '
            f'font-weight="650">{esc(cut(label, w - 16, 12.5))}</text>')
    if sub:
        out += (f'<text x="{tx}" y="{ty + 13}" text-anchor="middle" font-size="10" '
                f'fill-opacity=".75">{esc(cut(sub, w - 14, 10))}</text>')
    return out


def arrow(x1, y1, x2, y2, accent, curve_bend=0):
    if curve_bend:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 + curve_bend
        d = f'M{x1} {y1} Q{mx} {my} {x2} {y2}'
    else:
        d = f'M{x1} {y1} L{x2} {y2}'
    return (f'<path d="{d}" stroke="{accent}" stroke-width="2" fill="none" '
            f'marker-end="url(#ar)"/>')


def badge(x, y, n, accent, r=10, text_color='#fff'):
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{accent}"/>'
            f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-size="10" '
            f'font-weight="700" fill="{text_color}">{n}</text>')


def icon_svg(name, x, y, size, accent):
    s = size / 24
    paths = {
        'leaf': 'M20 4C11 4 5 9 5 17c0 2 1 4 2 5 1-7 6-11 12-13-5 3-9 7-10 13 9 0 13-6 13-18z',
        'drop': 'M12 3C9 8 6 11 6 15a6 6 0 0012 0c0-4-3-7-6-12z',
        'sun': 'M12 7a5 5 0 100 10 5 5 0 000-10zM12 1v3M12 20v3M1 12h3M20 12h3M4 4l2 2M18 18l2 2M20 4l-2 2M6 18l-2 2',
        'flask': 'M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3',
        'gear': 'M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2',
        'book': 'M4 4h7a3 3 0 013 3v13a3 3 0 00-3-3H4zM20 4h-7a3 3 0 00-3 3v13a3 3 0 013-3h7z',
        'clock': 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 7v5l3 2',
        'chart': 'M4 20V10M10 20V4M16 20v-7M22 20H2',
        'check': 'M4 12l5 5L20 6',
        'cross': 'M6 6l12 12M18 6L6 18',
        'arrow': 'M4 12h14M13 6l6 6-6 6',
        'person': 'M12 4a4 4 0 100 8 4 4 0 000-8zM4 21c0-4 4-6 8-6s8 2 8 6',
        'brain': 'M9 4a3 3 0 00-3 3 3 3 0 00-2 5 3 3 0 002 5 3 3 0 003 3c2 0 3-1 3-3V7c0-2-1-3-3-3zM15 4a3 3 0 013 3 3 3 0 012 5 3 3 0 01-2 5 3 3 0 01-3 3c-2 0-3-1-3-3V7c0-2 1-3 3-3z',
    }
    d = paths.get(name, paths['arrow'])
    if name == 'sun':
        return (f'<g transform="translate({x} {y}) scale({s})" stroke="{accent}" stroke-width="2" '
                f'fill="none" stroke-linecap="round"><path d="{d}"/></g>')
    return (f'<g transform="translate({x} {y}) scale({s})"><path d="{d}" fill="{accent}" '
            f'fill-opacity=".18" stroke="{accent}" stroke-width="1.6" stroke-linejoin="round"/></g>')
