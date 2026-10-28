#!/usr/bin/env python3
"""按视觉原型重生成图示：曲线/机制链/循环/对比/层级/时间轴/结构示意/矩阵/概念网络。"""
import json
import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import visual_lib as V  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据/subjects'
TPL = ('· 对比图', '· 流程图', '· 清单图', '· 知识结构图', '· 关系曲线图', '· 机制流程图',
       '· 循环图', '· 对比矩阵', '· 层级结构图', '· 时间轴', '· 结构示意图', '· 二维矩阵', '· 概念网络图')


def kws(p, n=6):
    out = [k for k in (p.get('keywords') or []) if k]
    for u in p.get('units') or []:
        for part in re.split(r'[，。；：、,;:]', str(u)):
            part = part.strip()
            if 2 <= len(part) <= 8 and part not in out:
                out.append(part)
            if len(out) >= n + 2:
                break
    return out[:n]


def subs(p, n=4):
    out = []
    for u in p.get('units') or []:
        clause = re.split(r'[，。；：]', str(u))[0]
        if len(clause) >= 4:
            out.append(clause)
        if len(out) >= n:
            break
    return out


def pick(p):
    t = p['title'] + ' ' + ' '.join(p.get('units') or [])[:400]
    if re.search(r'曲线|随.{0,6}变化|最适|饱和|补偿|日变化|吸收光谱|滴定曲线|S 形|S形', t):
        return 'curve'
    if re.search(r'循环|回路|周转|循环途径', t):
        return 'cycle'
    if re.search(r'区别|比较|异同|辨析|对比| vs ', t):
        return 'compare'
    if re.search(r'分类|类型|构成|组成|体系|层次|包括|分为', t):
        return 'hierarchy'
    if re.search(r'历史|进程|演变|时间|阶段|先后|发展历程', t):
        return 'timeline'
    if re.search(r'机理|机制|过程|途径|传导|步骤|流程|反应|组装|合成', t):
        return 'flow'
    if re.search(r'结构|构象|模型|装置|示意|形态|解剖', t):
        return 'structure'
    return 'map'


# ---------- 1 曲线 ----------
def shape_of(p):
    t = p['title'] + ' '.join(p.get('units') or [])[:200]
    if re.search(r'最适|温度.*速率|速率.*温度', t):
        return 'hump'
    if re.search(r'日变化|午休|双峰', t):
        return 'double'
    if re.search(r'S 形|S形|生长大周期|生长曲线', t):
        return 'sigmoid'
    if re.search(r'饱和|补偿|浓度.*吸光|吸光.*浓度|米氏|酶促', t):
        return 'sat'
    if re.search(r'下降|减少|降低|抑制', t):
        return 'down'
    return 'up'


def curve_svg(p, ac):
    x0, y0, w, h = 74, 66, 492, 150
    shape = shape_of(p)
    xs = [x0 + w * i / 40 for i in range(41)]
    def f(t):
        if shape == 'hump':
            return y0 + h * (1 - math.exp(-((t - .55) ** 2) / .045))
        if shape == 'double':
            return y0 + h * (1 - .55 * math.exp(-((t - .28) ** 2) / .01) - .45 * math.exp(-((t - .72) ** 2) / .012))
        if shape == 'sigmoid':
            return y0 + h * (1 - 1 / (1 + math.exp((t - .5) * 12)))
        if shape == 'sat':
            return y0 + h * (1 - .78 * (1 - math.exp(-t * 3.2)))
        if shape == 'down':
            return y0 + h * (.15 + .8 * t)
        return y0 + h * (1 - .9 * t)
    pts = [(x, f((x - x0) / w)) for x in xs]
    lab = kws(p, 4)
    body = V.title(p['title'], ac) + V.axes(x0, y0, w, h, lab[1] if len(lab) > 1 else '横轴',
                                            lab[0] if lab else '纵轴', ac)
    body += V.curve(pts, ac, fill=True)
    marks = {'hump': [.55, '最适'], 'double': [.28, '峰'], 'sigmoid': [.5, '转折'],
             'sat': [.62, '饱和'], 'down': [.7, '下降'], 'up': [.6, '上升']}[shape]
    mx = x0 + w * marks[0]
    my = f(marks[0])
    body += V.dot(mx, my, marks[1], ac)
    if len(lab) > 2:
        body += V.dot(x0 + w * .18, f(.18), lab[2], ac, dy=18)
    if len(lab) > 3:
        body += V.dot(x0 + w * .85, f(.85), lab[3], ac, dy=-14)
    body += V.takeaway(p['point'], ac)
    return V.svg(ac, body, p['title'])


# ---------- 2 机制链 ----------
def flow_svg(p, ac):
    lab = kws(p, 4)
    body = V.title(p['title'], ac)
    n = max(2, min(4, len(lab)))
    bw, gap = 124, 28
    total = n * bw + (n - 1) * gap
    x = (V.W - total) / 2
    y = 74
    for i in range(n):
        body += V.node(x + i * (bw + gap), y, bw, 92, lab[i], ac,
                       sub=(subs(p, n)[i][:10] if i < len(subs(p, n)) else ''))
        body += V.badge(x + i * (bw + gap) + 13, y + 13, i + 1, ac, r=9)
        if i < n - 1:
            body += V.arrow(x + i * (bw + gap) + bw + 3, y + 46, x + (i + 1) * (bw + gap) - 3, y + 46, ac)
    body += V.takeaway(p['point'], ac)
    return V.svg(ac, body, p['title'])


# ---------- 3 循环 ----------
def cycle_svg(p, ac):
    lab = kws(p, 4)
    body = V.title(p['title'], ac)
    cx, cy, r = 320, 150, 78
    pts = [(cx + r * math.cos(math.radians(-90 + i * 90)),
            cy + r * math.sin(math.radians(-90 + i * 90))) for i in range(4)]
    for i, (x, y) in enumerate(pts):
        body += V.node(x - 58, y - 26, 116, 52, lab[i], ac, icon='gear' if i == 0 else None)
        nx, ny = pts[(i + 1) % 4]
        body += V.arrow(x + (nx - x) * .32, y + (ny - y) * .32,
                        x + (nx - x) * .68, y + (ny - y) * .68, ac, curve_bend=18)
    body += f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" font-size="11" fill-opacity=".7">循环</text>'
    body += V.takeaway(p['point'], ac)
    return V.svg(ac, body, p['title'])


# ---------- 4 对比 ----------
def compare_svg(p, ac):
    t = p['title']
    parts = re.split(r'\s*(?:与|和|、|vs|VS)\s*', t, maxsplit=1)
    left, right = (parts[0], parts[1]) if len(parts) == 2 else (kws(p, 2) + ['A', 'B'])[:2]
    body = V.title(t, ac)
    body += V.node(56, 52, 240, 46, left, ac, fill_opacity=.16)
    body += V.node(344, 52, 240, 46, right, ac, fill_opacity=.16)
    body += f'<text x="320" y="82" text-anchor="middle" font-size="11" fill-opacity=".7">vs</text>'
    rows = kws(p, 6)[2:5] or kws(p, 3)
    for i, r in enumerate(rows[:3]):
        y = 118 + i * 42
        body += (f'<rect x="56" y="{y}" width="528" height="34" rx="8" fill="{ac}" fill-opacity=".05"/>'
                 f'<text x="320" y="{y + 22}" text-anchor="middle" font-size="11">{V.esc(V.cut(r, 240, 11))}</text>')
        body += f'<circle cx="76" cy="{y + 17}" r="3.5" fill="{ac}"/>'
        body += f'<circle cx="564" cy="{y + 17}" r="3.5" fill="{ac}" fill-opacity=".5"/>'
    body += V.takeaway(p['point'], ac)
    return V.svg(ac, body, p['title'])


# ---------- 5 层级 ----------
def hierarchy_svg(p, ac):
    lab = kws(p, 6)
    body = V.title(p['title'], ac)
    body += V.node(200, 46, 240, 44, V.cut(p['title'], 210, 11.5), ac, fill_opacity=.18)
    n = min(4, len(lab))
    bw, gap = 124, 22
    total = n * bw + (n - 1) * gap
    x = (V.W - total) / 2
    for i in range(n):
        bx = x + i * (bw + gap)
        body += f'<path d="M320 90 L320 104 L{bx + bw / 2} 104 L{bx + bw / 2} 120" stroke="{ac}" stroke-opacity=".5" fill="none"/>'
        body += V.node(bx, 120, bw, 58, lab[i], ac)
        if len(lab) > n + i:
            body += f'<text x="{bx + bw / 2}" y="196" text-anchor="middle" font-size="10" fill-opacity=".7">{V.esc(V.cut(lab[n + i], bw - 6, 10))}</text>'
    body += V.takeaway(p['point'], ac)
    return V.svg(ac, body, p['title'])


# ---------- 6 时间轴 ----------
def timeline_svg(p, ac):
    lab = kws(p, 4)
    body = V.title(p['title'], ac)
    y = 150
    body += f'<path d="M50 {y} L590 {y}" stroke="{ac}" stroke-opacity=".45" stroke-width="2"/>'
    body += f'<path d="M590 {y} l-9 -5 v10 z" fill="{ac}"/>'
    n = min(4, len(lab))
    for i in range(n):
        x = 80 + i * (480 / max(n - 1, 1))
        up = i % 2 == 0
        body += f'<circle cx="{x}" cy="{y}" r="7" fill="{ac}"/>'
        body += f'<path d="M{x} {y - 8 if up else y + 8} L{x} {y - 70 if up else y + 70}" stroke="{ac}" stroke-opacity=".45"/>'
        ty = y - 78 if up else y + 86
        body += (f'<rect x="{x - 62}" y="{ty - 16}" width="124" height="32" rx="8" fill="{ac}" fill-opacity=".10"/>'
                 f'<text x="{x}" y="{ty + 4}" text-anchor="middle" font-size="11.5" font-weight="600">{V.esc(V.cut(lab[i], 110, 11.5))}</text>')
    body += V.takeaway(p['point'], ac)
    return V.svg(ac, body, p['title'])


# ---------- 7 结构示意 ----------
def structure_svg(p, ac):
    lab = kws(p, 5)
    body = V.title(p['title'], ac)
    t = p['title']
    if re.search(r'叶|光合|气孔|蒸腾', t):
        body += f'<path d="M250 190 C250 110 340 70 430 78 C420 160 350 205 250 190 Z" fill="{ac}" fill-opacity=".12" stroke="{ac}" stroke-width="2"/>'
        body += f'<path d="M260 186 C310 150 370 118 420 92" stroke="{ac}" stroke-opacity=".5" fill="none"/>'
        body += f'<path d="M320 160 L300 140 M350 140 L330 120 M380 120 L360 102" stroke="{ac}" stroke-opacity=".4"/>'
    elif re.search(r'细胞|膜|器|核', t):
        body += f'<circle cx="330" cy="145" r="86" fill="{ac}" fill-opacity=".08" stroke="{ac}" stroke-width="2"/>'
        body += f'<circle cx="330" cy="145" r="34" fill="{ac}" fill-opacity=".18" stroke="{ac}"/>'
        for i in range(5):
            a = math.radians(i * 72 + 15)
            body += f'<ellipse cx="{330 + 58 * math.cos(a):.0f}" cy="{145 + 58 * math.sin(a):.0f}" rx="16" ry="9" fill="{ac}" fill-opacity=".22" transform="rotate({i * 72} {330 + 58 * math.cos(a):.0f} {145 + 58 * math.sin(a):.0f})"/>'
    elif re.search(r'装置|仪器|滴定|蒸馏|萃取|层析', t):
        body += f'<path d="M300 80 h60 v46 l38 74 a12 12 0 0 1 -11 18 h-114 a12 12 0 0 1 -11 -18 l38 -74 z" fill="{ac}" fill-opacity=".10" stroke="{ac}" stroke-width="2"/>'
        body += f'<path d="M286 186 h100" stroke="{ac}" stroke-opacity=".6"/>'
    else:
        body += f'<circle cx="320" cy="148" r="74" fill="{ac}" fill-opacity=".08" stroke="{ac}" stroke-width="2"/>'
        body += f'<circle cx="320" cy="148" r="40" fill="{ac}" fill-opacity=".16" stroke="{ac}"/>'
    for i, k in enumerate(lab[:4]):
        y = 78 + i * 42
        body += f'<circle cx="96" cy="{y}" r="4" fill="{ac}"/>'
        body += f'<text x="108" y="{y + 4}" font-size="11">{V.esc(V.cut(k, 120, 11))}</text>'
        body += f'<path d="M200 {y} L236 {y}" stroke="{ac}" stroke-opacity=".35" stroke-dasharray="3 3"/>'
    body += V.takeaway(p['point'], ac)
    return V.svg(ac, body, p['title'])


# ---------- 8 矩阵 ----------
def matrix_svg(p, ac):
    lab = kws(p, 6)
    body = V.title(p['title'], ac)
    x0, y0, w, h = 150, 62, 340, 160
    body += f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="{ac}" fill-opacity=".04" stroke="{ac}" stroke-opacity=".35"/>'
    body += f'<path d="M{x0 + w / 2} {y0} V{y0 + h} M{x0} {y0 + h / 2} H{x0 + w}" stroke="{ac}" stroke-opacity=".35"/>'
    for i in range(4):
        cx = x0 + (w / 4 if i % 2 == 0 else w * 3 / 4)
        cy = y0 + (h / 4 if i < 2 else h * 3 / 4)
        if i < len(lab):
            body += f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" font-size="11">{V.esc(V.cut(lab[i], 140, 11))}</text>'
    body += f'<path d="M{x0 - 26} {y0 + h} V{y0 - 6}" stroke="currentColor" stroke-opacity=".45" fill="none"/>'
    body += f'<path d="M{x0 - 26} {y0 - 6} l-4 8 h8 z" fill="currentColor" fill-opacity=".45"/>'
    body += f'<text x="{x0 - 34}" y="{y0 + h / 2}" text-anchor="middle" font-size="10.5" transform="rotate(-90 {x0 - 34} {y0 + h / 2})">{V.esc(V.cut(lab[4] if len(lab) > 4 else "维度二", 90, 10.5))}</text>'
    body += f'<text x="{x0 + w / 2}" y="{y0 + h + 20}" text-anchor="middle" font-size="10.5">{V.esc(V.cut(lab[5] if len(lab) > 5 else "维度一", 120, 10.5))}</text>'
    body += V.takeaway(p['point'], ac)
    return V.svg(ac, body, p['title'])


# ---------- 9 概念网络 ----------
def map_svg(p, ac):
    lab = kws(p, 6)
    body = V.title(p['title'], ac)
    body += V.node(220, 118, 200, 56, V.cut(p['title'], 172, 12.5), ac, icon='brain', fill_opacity=.20)
    positions = [(70, 56), (70, 118), (70, 180), (430, 56), (430, 118), (430, 180)]
    for i, (x, y) in enumerate(positions[:len(lab)]):
        body += f'<path d="M{320 + (26 if x > 320 else -26)} {146} L{x + (100 if x < 320 else 0)} {y + 24}" stroke="{ac}" stroke-opacity=".35" stroke-dasharray="4 4"/>'
        body += V.node(x, y, 140, 48, lab[i], ac, icon='leaf' if i == 0 else None, fill_opacity=.08)
    body += V.takeaway(p['point'], ac)
    return V.svg(ac, body, p['title'])


BUILDERS = {'curve': curve_svg, 'flow': flow_svg, 'cycle': cycle_svg, 'compare': compare_svg,
            'hierarchy': hierarchy_svg, 'timeline': timeline_svg, 'structure': structure_svg,
            'matrix': matrix_svg, 'map': map_svg}

SUFFIX = {'curve': '关系曲线图', 'flow': '机制流程图', 'cycle': '循环图', 'compare': '对比矩阵',
          'hierarchy': '层级结构图', 'timeline': '时间轴', 'structure': '结构示意图',
          'matrix': '二维矩阵', 'map': '概念网络图'}


def main(sids):
    for sid in sids:
        ac = V.ACCENT[sid]
        doc = json.loads((META / sid / f'{sid}.json').read_text(encoding='utf-8'))
        mp = META / sid / f'{sid}-media.json'
        media = json.loads(mp.read_text(encoding='utf-8')) if mp.exists() else {}
        n = 0
        for p in doc['points']:
            items = media.get(p['id']) or []
            if items and not items[0].get('caption', '').endswith(TPL):
                continue  # 保留手绘图
            arch = pick(p)
            svg = BUILDERS[arch](p, ac)
            media[p['id']] = [{
                'kind': 'diagram',
                'caption': f"{p['title']} · {SUFFIX[arch]}",
                'alt': p['title'] + '；核心：' + p['point'][:60],
                'svg': svg,
            }]
            n += 1
        mp.write_text(json.dumps(media, ensure_ascii=False, indent=1), encoding='utf-8')
        print(sid, 'generated', n, 'total media', len(media))


if __name__ == '__main__':
    main(sys.argv[1:] or ['315', '101', '204'])
