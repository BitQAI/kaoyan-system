#!/usr/bin/env python3
"""范文配图：6 张图表 + 6 张情景示意图，输出 204-essay-figures.json。

图内文字用 currentColor，强调色用 204 主题紫；只画与范文一致的数据与场景，
不加入正文没有的信息。图表按题面数字绘制，示意图用图标卡片表示情境。
"""
import html
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / '知识点元数据' / 'subjects' / '204' / '204-essay-figures.json'

W, H = 640, 300
ACC = '#7c5cff'
GOOD = '#2f8f5b'

BASE_Y = 244


def esc(s) -> str:
    return html.escape(str(s), quote=False)


def svg(body: str, alt: str) -> str:
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(alt)}" '
            'xmlns="http://www.w3.org/2000/svg" fill="currentColor" '
            'style="font-family:inherit;color:inherit">' + body + '</svg>')


def t(x, y, s, size=13, weight=400, anchor='middle', fill=None, opacity=1.0):
    f = f' fill="{fill}"' if fill else ''
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{f} opacity="{opacity}">{esc(s)}</text>')


def panel(x, y, w, h, r=14, stroke='currentColor', stroke_opacity=.16, fill=.045):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
            f'fill="currentColor" fill-opacity="{fill}" stroke="{stroke}" '
            f'stroke-opacity="{stroke_opacity}"/>')


def bar(x, y, w, h, fill=ACC, op=.9):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" fill-opacity="{op}"/>'


def axis_ticks(max_v, step, label_fmt='{:.0f}'):
    out = []
    for v in range(0, int(max_v) + 1, step):
        y = BASE_Y - v / max_v * 180
        out.append(f'<line x1="70" y1="{y:.1f}" x2="600" y2="{y:.1f}" '
                   'stroke="currentColor" stroke-opacity=".10"/>')
        out.append(t(56, y + 4, label_fmt.format(v), 11, opacity=.55, anchor='end'))
    return ''.join(out)


def legend(x, y, items):
    out, cx = [], x
    for color, label in items:
        out.append(f'<rect x="{cx}" y="{y}" width="12" height="12" rx="3" fill="{color}" fill-opacity=".9"/>')
        out.append(t(cx + 18, y + 10, label, 12, anchor='start', opacity=.7))
        cx += 18 + len(label) * 13 + 22
    return ''.join(out)


def arc(cx, cy, r, a0, a1):
    x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
    x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
    large = 1 if a1 - a0 > math.pi else 0
    return (f'M {cx} {cy} L {x0:.2f} {y0:.2f} A {r} {r} 0 {large} 1 '
            f'{x1:.2f} {y1:.2f} Z')


# ---------- 图表 ----------

def fig_0906():
    vals = [('独自', 54.3), ('与朋友', 47.7), ('与家人', 23.9), ('团体', 15.8)]
    body = [axis_ticks(60, 20, '{:.0f}%')]
    for i, (name, v) in enumerate(vals):
        x = 100 + i * 125
        h = v / 60 * 180
        body.append(bar(x, BASE_Y - h, 72, h))
        body.append(t(x + 36, BASE_Y - h - 10, f'{v}%', 13, 700))
        body.append(t(x + 36, BASE_Y + 20, name, 13, 500, opacity=.75))
    body.append(t(320, 34, '某市居民偏好的锻炼方式', 16, 700))
    return svg(''.join(body), '柱状图：独自锻炼 54.3%，与朋友 47.7%，与家人 23.9%，团体 15.8%')


def fig_0907():
    groups = [
        ('就业', 68.1, 60.7, '68.1% / 60.7%'),
        ('深造', 26.5, 35.3, '约 +1/3'),
        ('创业', 10.0, 20.0, '约 ×2'),
    ]
    body = [axis_ticks(80, 20, '{:.0f}%')]
    for i, (name, a, b, lab) in enumerate(groups):
        x = 125 + i * 175
        ha, hb = a / 80 * 180, b / 80 * 180
        body.append(bar(x, BASE_Y - ha, 44, ha, '#7c5cff', .45))
        body.append(bar(x + 54, BASE_Y - hb, 44, hb))
        body.append(t(x + 49, BASE_Y + 20, name, 13, 500, opacity=.75))
        body.append(t(x + 49, BASE_Y - max(ha, hb) - 10, lab, 12, 700))
    body.append(legend(430, 44, [(ACC, '2018'), ('#b9a8ff', '2013')]))
    body.append(t(320, 34, '某高校 2013 与 2018 届毕业生去向', 16, 700))
    return svg(''.join(body), '对比柱状图：就业 68.1% 降至 60.7%，深造增加约三分之一，创业翻倍')


def fig_0908():
    groups = [('全国', 51, 83), ('农村', 12, 30)]
    body = [axis_ticks(90, 30, '{:.0f}')]
    for i, (name, a, b) in enumerate(groups):
        x = 170 + i * 190
        ha, hb = a / 90 * 180, b / 90 * 180
        body.append(bar(x, BASE_Y - ha, 52, ha, '#7c5cff', .45))
        body.append(bar(x + 62, BASE_Y - hb, 52, hb))
        body.append(t(x + 57, BASE_Y + 20, name, 13, 500, opacity=.75))
        body.append(t(x + 26, BASE_Y - ha - 9, f'{a}', 12, 700))
        body.append(t(x + 88, BASE_Y - hb - 9, f'{b}', 12, 700))
    body.append(legend(430, 44, [(ACC, '2020'), ('#b9a8ff', '2018')]))
    body.append(t(320, 34, '中国快递业务量（十亿件）', 16, 700))
    return svg(''.join(body), '柱状图：全国快递量 51 增至 83，农村 12 增至 30（十亿件）')


def fig_0909():
    data = [('为学习', 59.5, '#7c5cff'), ('娱乐', 21.3, '#9b82ff'),
            ('获取信息', 17.0, '#c1b1ff'), ('其他', 2.2, '#ded5ff')]
    cx, cy, r = 190, 155, 95
    body, a = [], -math.pi / 2
    for name, v, color in data:
        sweep = v / 100 * 2 * math.pi
        body.append(f'<path d="{arc(cx, cy, r, a, a + sweep)}" fill="{color}" fill-opacity=".9" '
                    'stroke="currentColor" stroke-opacity=".25" stroke-width="1"/>')
        a += sweep
    body.append(t(cx, cy + 5, '手机阅读', 13, 700, opacity=.8))
    ly = 96
    for name, v, color in data:
        body.append(f'<rect x="360" y="{ly}" width="12" height="12" rx="3" fill="{color}"/>')
        body.append(t(380, ly + 10, f'{name} {v}%', 13, anchor='start', opacity=.8))
        ly += 32
    body.append(t(320, 34, '大学生手机阅读的目的占比', 16, 700))
    return svg(''.join(body), '饼图：学习 59.5%，娱乐 21.3%，获取信息 17.0%，其他 2.2%')


def fig_0910():
    pts = [8.8, 9.6, 10.4, 11.5, 12.8, 14.6, 16.8, 19.4, 22.3, 25.4]
    body = [axis_ticks(30, 10, '{:.0f}%')]
    step = 500 / (len(pts) - 1)
    xy = [(70 + i * step, BASE_Y - v / 30 * 180) for i, v in enumerate(pts)]
    path = ' '.join(('M' if i == 0 else 'L') + f'{x:.1f} {y:.1f}' for i, (x, y) in enumerate(xy))
    body.append(f'<path d="{path}" fill="none" stroke="{ACC}" stroke-width="3" '
                'stroke-linecap="round" stroke-linejoin="round"/>')
    for i, (x, y) in enumerate(xy):
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{ACC}"/>')
        if i in (0, len(xy) - 1):
            body.append(t(x, y - 12, f'{pts[i]}%', 13, 700))
        body.append(t(x, BASE_Y + 20, str(2012 + i), 11, opacity=.6))
    body.append(t(320, 34, '中国居民健康素养水平（2012–2021）', 16, 700))
    return svg(''.join(body), '折线图：健康素养从 2012 年 8.8% 稳步升至 2021 年 25.4%')


def fig_0911():
    rows = [('工作环境', 4.5), ('薪酬', 3.9), ('晋升机会', 3.1)]
    body = [t(110, 72, '项目', 12, 700, anchor='start', opacity=.6),
            t(360, 72, '满意度（满分 5）', 12, 700, anchor='start', opacity=.6),
            '<line x1="90" y1="84" x2="550" y2="84" stroke="currentColor" stroke-opacity=".18"/>']
    for i, (name, v) in enumerate(rows):
        y = 108 + i * 54
        body.append(t(110, y, name, 14, 600, anchor='start'))
        body.append(f'<rect x="300" y="{y - 13}" width="150" height="16" rx="8" '
                    'fill="currentColor" fill-opacity=".08"/>')
        body.append(bar(300, y - 13, max(18, v / 5 * 150), 16, GOOD if v >= 4 else ACC, .85))
        body.append(t(470, y, f'{v}', 14, 700, anchor='start'))
    body.append(t(320, 34, '员工满意度调查（5 分制）', 16, 700))
    return svg(''.join(body), '表格：工作环境 4.5，薪酬 3.9，晋升机会 3.1（满分 5）')


# ---------- 情景示意图 ----------

def person(cx, cy, s=1.0):
    return (f'<circle cx="{cx}" cy="{cy}" r="{12 * s}" fill="currentColor" fill-opacity=".75"/>'
            f'<path d="M {cx - 22 * s} {cy + 40 * s} q {22 * s} {-26 * s} {44 * s} 0" '
            'fill="none" stroke="currentColor" stroke-opacity=".75" stroke-width="3" stroke-linecap="round"/>')


def scene_frame(title, alt, body):
    return svg(t(320, 34, title, 16, 700) + ''.join(body), alt)


def fig_0805():
    body = [
        panel(80, 70, 220, 180, 18),
        panel(340, 70, 220, 180, 18, stroke=ACC, stroke_opacity=.55, fill=.06),
        '<rect x="112" y="98" width="156" height="96" rx="8" fill="none" stroke="currentColor" stroke-opacity=".6" stroke-width="2"/>',
        '<path d="M120 178 L162 138 L192 166 L216 146 L258 182" fill="none" stroke="currentColor" stroke-opacity=".6" stroke-width="2"/>',
        '<circle cx="232" cy="118" r="9" fill="currentColor" fill-opacity=".5"/>',
        t(190, 226, '艺术展', 14, 700),
        '<rect x="412" y="104" width="76" height="66" rx="14" fill="none" stroke="currentColor" stroke-opacity=".6" stroke-width="2"/>',
        '<circle cx="434" cy="130" r="7" fill="currentColor" fill-opacity=".7"/>',
        '<circle cx="466" cy="130" r="7" fill="currentColor" fill-opacity=".7"/>',
        '<path d="M426 150 h48" stroke="currentColor" stroke-opacity=".6" stroke-width="3" stroke-linecap="round"/>',
        '<path d="M450 104 v-14" stroke="currentColor" stroke-opacity=".6" stroke-width="2"/>',
        '<circle cx="450" cy="86" r="5" fill="currentColor" fill-opacity=".6"/>',
        t(450, 226, '机器人展', 14, 700),
        t(450, 246, '（备选）', 12, opacity=.55),
        f'<circle cx="284" cy="160" r="12" fill="{GOOD}"/>',
        f'<path d="M278 160 l5 6 l9 -11" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
    ]
    return scene_frame('建议信：艺术展还是机器人展', '一张示意图：艺术展被勾选为推荐，机器人展作为备选', body)


def fig_0806():
    body = [
        panel(150, 68, 340, 190, 18),
        '<rect x="180" y="92" width="280" height="34" rx="8" fill="currentColor" fill-opacity=".10"/>',
        t(320, 114, '下周 · 会面', 13, 600, opacity=.7),
    ]
    for r in range(3):
        for c in range(6):
            x, y = 186 + c * 44, 142 + r * 36
            body.append(f'<rect x="{x}" y="{y}" width="34" height="26" rx="6" fill="currentColor" fill-opacity=".05"/>')
    body.append('<line x1="452" y1="144" x2="480" y2="168" stroke="#d9485f" stroke-width="3" stroke-linecap="round"/>')
    body.append('<line x1="480" y1="144" x2="452" y2="168" stroke="#d9485f" stroke-width="3" stroke-linecap="round"/>')
    body.append(f'<path d="M504 214 q-30 26 -66 4" fill="none" stroke="{ACC}" stroke-width="2.5" stroke-linecap="round"/>')
    body.append(f'<path d="M446 210 l-10 6 l10 8" fill="none" stroke="{ACC}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>')
    body.append(t(474, 244, '另约时间', 13, 600, fill=ACC))
    return scene_frame('道歉信：取消会面并另约时间', '一张示意图：日历上的会面被划掉，箭头指向另约时间', body)


def fig_0807():
    body = [
        panel(95, 72, 190, 168, 18),
        panel(355, 72, 190, 168, 18, stroke=ACC, stroke_opacity=.5, fill=.06),
        t(190, 112, '中国', 15, 700),
        t(450, 112, '美国', 15, 700),
        person(160, 156), person(220, 156),
        person(420, 156), person(480, 156),
        f'<path d="M300 150 q20 -18 40 0" fill="none" stroke="{ACC}" stroke-width="2.5"/>',
        f'<path d="M330 144 l10 8 l-12 4" fill="none" stroke="{ACC}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>',
        t(320, 196, '接待与交流', 13, 600, fill=ACC),
    ]
    return scene_frame('感谢信：文化交流接待', '一张示意图：中方与美方两组人物之间的交流箭头', body)


def fig_0808():
    body = [
        panel(110, 84, 200, 156, 18),
        '<path d="M210 96 L150 216 h120 Z" fill="none" stroke="currentColor" stroke-opacity=".65" stroke-width="2.5" stroke-linejoin="round"/>',
        f'<path d="M210 96 L210 216" stroke="currentColor" stroke-opacity=".35" stroke-width="2"/>',
        '<path d="M210 96 l34 20 l-34 14 Z" fill="none" stroke="currentColor" stroke-opacity=".65" stroke-width="2"/>',
        t(210, 264, '夏令营', 14, 700),
        panel(368, 84, 162, 156, 18),
        '<rect x="398" y="104" width="102" height="76" rx="8" fill="none" stroke="currentColor" stroke-opacity=".6" stroke-width="2"/>',
        '<path d="M414 124 h58 M414 142 h70 M414 160 h44" stroke="currentColor" stroke-opacity=".5" stroke-width="2.5" stroke-linecap="round"/>',
        f'<circle cx="500" cy="196" r="14" fill="{ACC}"/>',
        '<path d="M494 196 l4 5 l8 -9" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>',
        t(450, 264, '志愿者招募', 14, 700),
    ]
    return scene_frame('通知：夏令营招募志愿者', '一张示意图：夏令营帐篷与志愿者报名表', body)


def fig_0809():
    body = [
        panel(160, 70, 320, 186, 18),
        '<rect x="214" y="94" width="212" height="120" rx="12" fill="none" stroke="currentColor" stroke-opacity=".6" stroke-width="2.5"/>',
        '<path d="M320 94 l-18 40 l26 12 l-20 38 l18 24" fill="none" stroke="#d9485f" stroke-width="2.5" stroke-linejoin="round"/>',
        t(320, 232, '电子词典 · 屏幕故障', 13, 600, opacity=.75),
        f'<path d="M448 108 l26 46 h-52 Z" fill="none" stroke="{ACC}" stroke-width="2.5" stroke-linejoin="round"/>',
        t(448, 146, '!', 18, 700, fill=ACC),
        t(448, 178, '5 分钟后', 12, 600, opacity=.6),
    ]
    return scene_frame('投诉信：电子词典质量问题', '一张示意图：电子词典屏幕出现裂纹，旁边是警示标志', body)


def fig_0810():
    body = [
        panel(96, 84, 210, 158, 18),
        '<path d="M136 194 v-46 h130 v46" fill="none" stroke="currentColor" stroke-opacity=".65" stroke-width="2.5"/>',
        '<path d="M126 148 l75 -44 l75 44" fill="none" stroke="currentColor" stroke-opacity=".65" stroke-width="2.5" stroke-linejoin="round"/>',
        '<rect x="188" y="166" width="28" height="28" rx="4" fill="none" stroke="currentColor" stroke-opacity=".55" stroke-width="2"/>',
        '<rect x="150" y="158" width="24" height="20" rx="4" fill="none" stroke="currentColor" stroke-opacity=".45" stroke-width="2"/>',
        '<rect x="232" y="158" width="24" height="20" rx="4" fill="none" stroke="currentColor" stroke-opacity=".45" stroke-width="2"/>',
        t(200, 264, '乡村小学', 14, 700),
        panel(360, 100, 180, 126, 18),
        '<rect x="390" y="126" width="120" height="76" rx="8" fill="none" stroke="currentColor" stroke-opacity=".6" stroke-width="2"/>',
        '<path d="M390 130 l60 38 l60 -38" fill="none" stroke="currentColor" stroke-opacity=".6" stroke-width="2" stroke-linejoin="round"/>',
        f'<circle cx="512" cy="196" r="15" fill="{ACC}"/>',
        t(512, 202, '?', 18, 700, fill='#fff'),
        t(450, 264, '询问细节', 14, 700),
    ]
    return scene_frame('询问信：了解志愿项目', '一张示意图：乡村小学与一封带问号的信', body)


FIGURES = {
    '2040805': ('scene', '情景：艺术展与机器人展二选一', fig_0805),
    '2040806': ('scene', '情景：取消会面并另约时间', fig_0806),
    '2040807': ('scene', '情景：中美文化交流接待', fig_0807),
    '2040808': ('scene', '情景：夏令营招募志愿者', fig_0808),
    '2040809': ('scene', '情景：电子词典屏幕故障', fig_0809),
    '2040810': ('scene', '情景：咨询乡村支教项目', fig_0810),
    '2040906': ('chart', '图表：四种锻炼方式的偏好占比', fig_0906),
    '2040907': ('chart', '图表：毕业生去向的两年对比', fig_0907),
    '2040908': ('chart', '图表：快递业务量的增长', fig_0908),
    '2040909': ('chart', '图表：手机阅读目的的占比', fig_0909),
    '2040910': ('chart', '图表：健康素养的十年变化', fig_0910),
    '2040911': ('chart', '图表：员工满意度调查', fig_0911),
}


def main():
    out = {}
    for pid, (kind, caption, build) in FIGURES.items():
        out[pid] = {'kind': kind, 'caption': caption, 'alt': caption,
                    'svg': build()}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{OUT.relative_to(ROOT)}：{len(out)} 张')


if __name__ == '__main__':
    main()
