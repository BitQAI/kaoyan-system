#!/usr/bin/env python3
"""从 master_eaxm 成品 HTML 抽取全部知识点 → .build/extract.json。

权威真源：master_eaxm/2027考研_四科知识全景与章节权重.html
产出：科目 > 模块 > 章节 > 知识点 四级结构，含 locator、权重、标签、优先级、溯源。

硬约束
------
- 源文件只读。
- 切分顺序固定：剥标签 → HTML 实体反转义 → 空白归一 → 按「；」切分。
  （必须先反转义再切分：`&lt;` 中的 `;` 若不先反转义会把实体切成两半。）
- 机制段（`<p class="mech">`）独立成点，不并入正文。
- 不做「<5 字符碎片合并」——该规则是旧管线的缺陷，会导致语义错乱与 id 空洞。
"""
import collections
import hashlib
import html as H
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chem            # noqa: E402
import outline_align as oa   # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent   # master_eaxm/
BUILD = ROOT / '.build'
SRC = ROOT / '2027考研_四科知识全景与章节权重.html'
META = ROOT / '知识点元数据'

# ── 受控词表 ──────────────────────────────────────────────────────────────
MODULES = {
    '101': ['马原', '毛中特', '习概', '史纲', '思修法治', '时政当代'],
    '204': ['考试结构', '词汇语法', '完形', '阅读A', '阅读B', '翻译', '写作A', '写作B'],
    '315': ['无机及分析化学', '有机化学'],
    '812': ['植物生理学'],
}
# 101 章名前缀 → 模块（与官方六科制一致；章名存在「习近平/新思想」「思修法基」等变体）
MOD101_PREFIX = [
    ('马原', '马原'), ('毛中特', '毛中特'), ('习近平', '习概'), ('新思想', '习概'),
    ('史纲', '史纲'), ('思修', '思修法治'), ('形势与政策', '时政当代'),
]
# 101 模块官方分值（p1-1 表：≥2024 六科制百分比 = 分数，合计 100）
MOD101_WEIGHT = {'马原': 22, '毛中特': 13, '习概': 22, '史纲': 15,
                 '思修法治': 15, '时政当代': 13}
TIER_CN = {1: '第一梯队', 2: '第二梯队', 3: '第三梯队'}
LV_TO_TAG = {'掌握': '必掌握', '理解': '理解', '了解': '了解'}

# 优先级判定（D3：章级 + 点级双输入；大纲层级优先于章级梯队）
PRIORITY_HOT = {'高频', '常考', '必掌握', '重点'}


# ── HTML 基础工具 ────────────────────────────────────────────────────────
def text_of(frag: str) -> str:
    """剥标签 → 实体反转义 → 空白归一。注意顺序：必须先反转义。"""
    frag = re.sub(r'<br\s*/?>', ' ', frag)
    frag = re.sub(r'<[^>]+>', '', frag)
    return re.sub(r'\s+', ' ', H.unescape(frag)).strip()


def section(html: str, anchor: str) -> str:
    i = html.find(f'<section class="section" id="{anchor}"')
    if i < 0:
        raise SystemExit(f'缺少 section {anchor}')
    j = html.find('<section class="section" id="', i + 10)
    return html[i:j if j > i else len(html)]


def split_points(text: str):
    """按中文/英文分号切分。不做碎片合并。"""
    return [p.strip() for p in re.split(r'[；;]', text) if p.strip()]


def h3_blocks(html: str):
    """按 <h3> 切块，返回 [(标题, 块内容)]。"""
    out = []
    for blk in re.split(r'(?=<h3)', html):
        if not blk.lstrip().startswith('<h3'):
            continue
        m = re.search(r'<h3>(.*?)</h3>', blk, re.S)
        if not m:
            continue
        out.append((text_of(m.group(1)), blk))
    return out


def plain_p(blk: str):
    """取块内第一个无 class 的 <p>（排除 <p class="small"> / <p class="mech">）。"""
    m = re.search(r'<p>(.*?)</p>', blk, re.S)
    return text_of(m.group(1)) if m else ''


def small_p(blk: str):
    m = re.search(r'<p class="small">(.*?)</p>', blk, re.S)
    return text_of(m.group(1)) if m else ''


# ── 权重表（315，p3-5 各章权重总表）─────────────────────────────────────
def parse_315_weights(html: str):
    sec = section(html, 'p3-5')
    target = None
    for tb in re.findall(r'<table[^>]*>(.*?)</table>', sec, re.S):
        if '权重中心' in tb and '梯队' in tb and len(re.findall(r'<tr[^>]*>', tb)) >= 20:
            target = tb
            break
    if target is None:
        raise SystemExit('p3-5 未找到 26 章权重总表')
    out = {}
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', target, re.S):
        cells = [text_of(c) for c in re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)]
        if len(cells) < 7 or cells[0] == '章节' or cells[0].startswith('合计'):
            continue
        name, _block, _cnt, _pct, center, rng, tier = cells[:7]
        mr = re.search(r'([\d.]+)\s*[–\-—~至]\s*([\d.]+)', rng)
        out[re.sub(r'\s+', '', name)] = {
            'center': float(center) if center else 0,
            'range': [float(mr.group(1)), float(mr.group(2))] if mr else None,
            'tier': {'第一梯队': 1, '第二梯队': 2, '第三梯队': 3}.get(tier, 3),
        }
    return out


# ── 315 大纲条目（p3-2 / p3-3）──────────────────────────────────────────
def parse_315_outline(html: str):
    """→ {归一化章名: [(层级, 条目文本), ...]}"""
    outline = {}
    for anchor in ('p3-2', 'p3-3'):
        for blk in re.split(r'(?=<details)', section(html, anchor)):
            if '<summary>' not in blk:
                continue
            ti = re.search(r'<span class="t">(.*?)</span>', blk, re.S)
            if not ti:
                continue
            names = [oa.norm_chapter_name(x)
                     for x in re.split(r'[｜|]', text_of(ti.group(1)))]
            ols = re.findall(r'<ol class="req">(.*?)</ol>', blk, re.S)
            if len(names) != len(ols):
                continue
            for nm, ol in zip(names, ols):
                items = []
                for li in re.finditer(r'<li>(.*?)</li>', ol, re.S):
                    lm = re.search(r'<span class="lv lv-(\w)">(.*?)</span>', li.group(1))
                    if lm:
                        items.append((lm.group(2), text_of(li.group(1))))
                if items:
                    outline.setdefault(nm, []).extend(items)
    return outline


# ── 101 必会清单（p1-4）─────────────────────────────────────────────────
def parse_101_must(html: str):
    """→ {模块: [必会词条, ...]}"""
    sec = section(html, 'p1-4')
    k = sec.find('高频')
    if k < 0:
        return {}
    seg = text_of(sec[k:k + 3000])
    out = {}
    for mod in MODULES['101']:
        m = re.search(mod + r'必会\s*(.*?)(?=' + '|'.join(
            [x for x in MODULES['101'] if x != mod]) + r'必会|$)', seg)
        if not m:
            continue
        body = m.group(1).strip()
        # 按「；」与「→」切句，再按「、」切词条（保留组合词）
        units = []
        for piece in re.split(r'[；。]|→', body):
            piece = piece.strip()
            if not piece:
                continue
            for u in re.split(r'[、,]', piece):
                u = u.strip()
                if len(u) >= 2:
                    units.append(u)
        out[mod] = units
    return out


# ══ 抽取主流程 ═════════════════════════════════════════════════════════
def _src(ref, section, basis='', outline=None):
    """精简溯源对象：合并原先的 sources / locator / merged_from / rationale 四字段。"""
    o = {'ref': ref, 'file': SRC.name, 'section': section}
    if basis:
        o['basis'] = basis
    if outline:
        o['outline'] = outline
    return o


def _point(pid, frag, cid, order, ref, section, tags, kind='正文', basis='', outline=None):
    return {
        'id': pid,
        'chapter': cid,
        'point': chem.normalize_formulas(frag),
        'title': '', 'explain': '', 'exam': '', 'keywords': [],
        'priority': '', 'tags': list(tags),
        'source': _src(ref, section, basis, outline),
        'spoken': '', 'tts': {},
        '_kind': kind,
    }


def extract_812(html, issues):
    """p4-2：<div class="chapter"> 块；正文分句 + 机制段各自成点。"""
    sec = section(html, 'p4-2')
    blocks = [b for b in re.split(r'(?=<div class="chapter">)', sec)
              if b.lstrip().startswith('<div class="chapter">')]
    chapters, points = [], []
    for ci, blk in enumerate(blocks):
        name = text_of(re.search(r'<h3>(.*?)</h3>', blk, re.S).group(1))
        w_m = re.search(r'class="w">\s*(\d+(?:\.\d+)?)\s*分', blk)
        sm = small_p(blk)
        mt = re.search(r'(第[一二三]梯队)', sm)
        mr = re.search(r'区间\s*([\d.]+)\s*[–\-—~至]+\s*([\d.]+)', sm)
        tier = {v: k for k, v in TIER_CN.items()}.get(mt.group(1), 3) if mt else 3
        cid = f'812-{ci:02d}'
        # 章级标签（长格式「易错：xxx」降级为短标签，详细文本落到章级 note）
        raw_tags = [text_of(x) for x in re.findall(r'<span class="tag[^"]*">(.*?)</span>', blk)]
        chap_tags, chap_note = [], []
        for tg in raw_tags:
            if ':' in tg or '：' in tg:
                k, v = re.split(r'[:：]', tg, 1)
                chap_tags.append(k.strip())
                chap_note.append(f'{k.strip()}：{v.strip()}')
            else:
                chap_tags.append(tg.strip())
        chap_tags = [x for x in chap_tags if x in ('基础', '重点', '易错')]

        ch_points = []
        mp = re.search(r'<p>(.*?)</p>', blk, re.S)
        if mp:
            for si, frag in enumerate(split_points(text_of(mp.group(1)))):
                pid = f'812{ci:02d}{si + 1:02d}'
                ch_points.append(_point(
                    pid, frag, cid, len(ch_points) + 1,
                    f'p4-2#{name}/p[0]/split[{si}]', 'p4-2', chap_tags,
                    basis=f'812 第{ci + 1}章，权重中心 {w_m.group(1) if w_m else "?"} 分，{TIER_CN[tier]}'))
        for mi, mm in enumerate(re.finditer(r'<p class="mech">(.*?)</p>', blk, re.S)):
            pid = f'812{ci:02d}M{mi + 1:02d}'
            ch_points.append(_point(
                pid, text_of(mm.group(1)), cid, len(ch_points) + 1,
                f'p4-2#{name}/mech[{mi}]', 'p4-2', ['机制'], kind='机制',
                basis=f'812 第{ci + 1}章机制段'))
        chapters.append({
            'id': cid, 'module': '植物生理学', 'name': name, 'order': ci,
            'tier': tier,
            'weight_center': float(w_m.group(1)) if w_m else 0,
            'weight_range': [float(mr.group(1)), float(mr.group(2))] if mr else None,
            'weight_basis': '推算',
            'entry_count': len(ch_points),
            'note': '；'.join(chap_note),
        })
        points.extend(ch_points)
    return chapters, points


def extract_315(html, issues):
    """p3-4：<div class="topic"> 块；权重来自 p3-5 总表；大纲层级来自 p3-2/p3-3。"""
    sec = section(html, 'p3-4')
    i = sec.find('A. 315')
    j = sec.find('<h2', i + 10)
    blk = sec[i:j if j > i else len(sec)]
    weights = parse_315_weights(html)
    outline = parse_315_outline(html)
    chapters, points = [], []
    for idx, (name, b) in enumerate(h3_blocks(blk), 1):
        cid = f'315-{idx:02d}'
        key = re.sub(r'\s+', '', name)
        w = weights.get(key)
        if not w:
            for k2, v2 in weights.items():
                if k2.endswith(key) or key.endswith(k2):
                    w = v2
                    break
        if w is None:
            w = {'center': 0, 'range': None, 'tier': 3}
            issues.append({'level': 'W', 'code': 'W-CH-WEIGHT',
                           'subject': '315', 'chapter': cid,
                           'msg': f'章「{name}」在 p3-5 权重总表中未匹配到权重条目'})
        frags = split_points(plain_p(b))
        items = outline.get(oa.norm_chapter_name(name), [])
        aligns = oa.align_chapter(frags, items) if items else [(None, 0.0)] * len(frags)
        ch_points = []
        for si, (frag, (oi, conf)) in enumerate(zip(frags, aligns)):
            pid = f'315{idx:02d}{si + 1:02d}'
            tags = []
            outline_ref = None
            if oi is not None and conf >= oa.CONF_THRESHOLD:
                t = LV_TO_TAG.get(items[oi][0], '')
                if t:
                    tags.append(t)
                outline_ref = f'{cid}#syllabus[{oi}]'
            ch_points.append(_point(
                pid, frag, cid, len(ch_points) + 1,
                f'p3-4#{name}/p[0]/split[{si}]', 'p3-4', tags,
                basis=(f'大纲条目「{items[oi][1][:24]}」要求 {items[oi][0]}'
                       f'（对齐置信度 {conf:.2f}）' if outline_ref else
                       f'权重中心 {w["center"]:g} 分，{TIER_CN[w["tier"]]}'),
                outline=outline_ref))
        chapters.append({
            'id': cid,
            'module': '无机及分析化学' if idx <= 11 else '有机化学',
            'name': name, 'order': idx - 1,
            'tier': w['tier'],
            'weight_center': w['center'],
            'weight_range': w['range'],
            'weight_basis': '推算',
            'entry_count': len(ch_points),
            'note': '',
            'outline': [{'index': k, 'level': lv, 'text': tx}
                        for k, (lv, tx) in enumerate(items)],
        })
        points.extend(ch_points)
    return chapters, points


def extract_101(html, issues):
    """p1-4：<div class="topic"> 块；模块由章名前缀确定；tier 由模块官方分值推导。"""
    sec = section(html, 'p1-4')
    i = sec.find('B. 101')
    j = sec.find('<h2', i + 10)
    blk = sec[i:j if j > i else len(sec)]
    must = parse_101_must(html)
    groups = h3_blocks(blk)
    mod_count = {}
    for name, _ in groups:
        mod = next((v for k, v in MOD101_PREFIX if name.startswith(k)), None)
        if mod:
            mod_count[mod] = mod_count.get(mod, 0) + 1
    chapters, points = [], []
    for idx, (name, b) in enumerate(groups, 1):
        cid = f'101-{idx:02d}'
        mod = next((v for k, v in MOD101_PREFIX if name.startswith(k)), None)
        if mod is None:
            mod = '待定'
            issues.append({'level': 'W', 'code': 'W-MODULE',
                           'subject': '101', 'chapter': cid,
                           'msg': f'章「{name}」无法判定所属模块'})
        mw = MOD101_WEIGHT.get(mod, 0)
        tier = 1 if mw >= 22 else (2 if mw >= 15 else 3)
        cnt = mod_count.get(mod, 1) or 1
        frags = split_points(plain_p(b))
        words = must.get(mod, [])
        ch_points = []
        for si, frag in enumerate(frags):
            pid = f'101{idx:02d}{si + 1:02d}'
            tags = []
            hit = sum(1 for w in words if w in frag)
            if words and hit / len(words) >= 0.55:
                tags.append('高频')
                basis = f'命中「{mod}必会」清单 {hit}/{len(words)} 项'
            elif tier == 1:
                tags.append('高频')
                basis = f'{mod}模块官方 {mw} 分，{TIER_CN[tier]}'
            else:
                basis = f'{mod}模块官方 {mw} 分，{TIER_CN[tier]}'
            ch_points.append(_point(
                pid, frag, cid, len(ch_points) + 1,
                f'p1-4#{name}/p[0]/split[{si}]', 'p1-4', tags, basis=basis))
        chapters.append({
            'id': cid, 'module': mod, 'name': name, 'order': idx - 1,
            'tier': tier,
            'weight_center': round(mw / cnt, 2) if mw else 0,
            'weight_range': None,
            'weight_basis': '官方',
            'entry_count': len(ch_points),
            'note': '',
        })
        points.extend(ch_points)
    return chapters, points


def extract_204(html, issues):
    """p2-8：<div class="topic"> 块（由 make_204_fragment.py 生成，含模块与权重）。"""
    sec = section(html, 'p2-8')
    chapters, points = [], []
    for idx, (name, b) in enumerate(h3_blocks(sec), 1):
        cid = f'204-{idx:02d}'
        sm = small_p(b)
        mod = re.search(r'模块\s*(\S+?)\s*·', sm)
        w = re.search(r'权重中心\s*([\d.]+)\s*分', sm)
        mt = re.search(r'(第[一二三]梯队)', sm)
        tier = {v: k for k, v in TIER_CN.items()}.get(mt.group(1), 3) if mt else 3
        frags = split_points(plain_p(b))
        ch_points = []
        for si, frag in enumerate(frags):
            pid = f'204{idx:02d}{si + 1:02d}'
            ch_points.append(_point(
                pid, frag, cid, len(ch_points) + 1,
                f'p2-8#{name}/p[0]/split[{si}]', 'p2-8', [],
                basis=f'权重中心 {w.group(1) if w else "?"} 分（人工估计），{TIER_CN[tier]}'))
        chapters.append({
            'id': cid, 'module': mod.group(1) if mod else '待定', 'name': name,
            'order': idx - 1, 'tier': tier,
            'weight_center': float(w.group(1)) if w else 0,
            'weight_range': None,
            'weight_basis': '人工估计',
            'entry_count': len(ch_points),
            'note': '',
        })
        points.extend(ch_points)
    return chapters, points


# ── 优先级与 TTS ─────────────────────────────────────────────────────────
def assign_priority(chapters, points):
    """D3：章级 tier 与点级 tags 双输入；大纲层级（必掌握）优先于章级梯队。"""
    tier_by_ch = {c['id']: c['tier'] for c in chapters}
    for p in points:
        tags = set(p.get('tags') or [])
        if '必掌握' in tags:
            p['priority'] = '★'
        elif tier_by_ch.get(p['chapter']) == 1 or (tags & PRIORITY_HOT):
            p['priority'] = '★'
        elif '易错' in tags:
            p['priority'] = '●'
        else:
            p['priority'] = '○'


def add_tts(points, subject):
    """补齐 spoken 与 tts。

    204 的朗读稿是**人工撰写**的（subjects/204/204-readings.json），
    覆盖默认的 point 直读；其余科目由 chem.to_speech 从 point 派生。
    """
    readings = {}
    rf = META / 'subjects' / subject / f'{subject}-readings.json'
    if rf.exists():
        raw = json.loads(rf.read_text(encoding='utf-8'))
        readings = {k: v for k, v in raw.items() if not k.startswith('_')}

    for p in points:
        if p['id'] in readings:
            sp = readings[p['id']]
        else:
            sp = chem.to_speech(p['point'], subject=subject)
        p['spoken'] = sp
        clips = chem.split_clips(sp)
        p['tts'] = {
            'enabled': True, 'max_chars': 220,
            'est_sec': chem.est_seconds(sp),
            'clips': [
                {'clip_id': p['id'] if len(clips) == 1 else f"{p['id']}-p{i + 1}",
                 'text': c, 'est_sec': chem.est_seconds(c)}
                for i, c in enumerate(clips)],
        }


def main():
    html = SRC.read_text(encoding='utf-8')
    sha = hashlib.sha256(html.encode()).hexdigest()
    issues = []
    subs = []
    for sid, name, score, fn in (
            ('812', '植物生理学', 150, extract_812),
            ('315', '315 化学（农）', 150, extract_315),
            ('101', '思想政治理论', 100, extract_101),
            ('204', '英语（二）', 100, extract_204)):
        chs, pts = fn(html, issues)
        assign_priority(chs, pts)
        add_tts(pts, sid)
        subs.append({'id': sid, 'name': name, 'score': score,
                     'modules': MODULES[sid], 'chapters': chs, 'points': pts})

    out = {
        'schema': 'ky-point-extract/1.0',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source': {'file': SRC.name, 'sha256': sha,
                   'sections': {'812': 'p4-2', '315': 'p3-4',
                                '101': 'p1-4', '204': 'p2-8'}},
        'subjects': subs,
        'issues': issues,
    }
    BUILD.mkdir(exist_ok=True)
    (BUILD / 'extract.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')

    print(f'源文件 sha256 {sha[:16]}…  （只读，未修改）')
    total = 0
    for s in subs:
        ids = [p['id'] for p in s['points']]
        holes = []
        for c in s['chapters']:
            seqs = sorted(int(p['id'][-2:]) for p in s['points']
                          if p['chapter'] == c['id'] and p['_kind'] == '正文')
            if seqs and seqs != list(range(1, len(seqs) + 1)):
                holes.append(c['id'])
        prio = collections.Counter(p['priority'] for p in s['points'])
        tags = collections.Counter(t for p in s['points'] for t in p['tags'])
        print(f"  {s['id']} {s['name']:<10} 章 {len(s['chapters']):>2} · 点 {len(s['points']):>3} · "
              f"模块 {len(set(c['module'] for c in s['chapters']))} · "
              f"id唯一 {len(set(ids)) == len(ids)} · 空洞 {holes or '无'}")
        print(f"      优先级 {dict(prio)}  标签 {dict(tags)}")
        total += len(s['points'])
    print(f'合计知识点 {total}   问题 {len(issues)} 条')


if __name__ == '__main__':
    main()
