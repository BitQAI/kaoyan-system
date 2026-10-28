#!/usr/bin/env python3
"""locator 回溯自检：source.ref → 源文档原文，验证与 point 逐字一致。

抽取配方（顺序不可颠倒）：
  1. 定位 <section class="section" id="{section}">
  2. 按容器切块：812 → <div class="chapter">；315/101/204 → <h3> 起始的 topic 块
  3. 取块内第一个无 class 的 <p>（排除 <p class="small"> / <p class="mech">）
  4. 剥标签 → HTML 实体反转义 → 空白归一
  5. 按 [；;] 切分，取第 M 片（0 基）
"""
import html as H
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chem  # noqa: E402
M = ROOT / '知识点元数据'
SRC = ROOT / '2027考研_四科知识全景与章节权重.html'


def text_of(frag):
    frag = re.sub(r'<br\s*/?>', ' ', frag)
    frag = re.sub(r'<[^>]+>', '', frag)
    return re.sub(r'\s+', ' ', H.unescape(frag)).strip()


def section(t, anchor):
    i = t.find(f'<section class="section" id="{anchor}"')
    j = t.find('<section class="section" id="', i + 10)
    return t[i:j]


def blocks_812(sec):
    return [b for b in re.split(r'(?=<div class="chapter">)', sec)
            if b.lstrip().startswith('<div class="chapter">')]


def blocks_topic(sec):
    return [b for b in re.split(r'(?=<h3)', sec) if b.lstrip().startswith('<h3')]


def resolve(t, ref):
    """ref → 原文文本（按章名锚定，应用化学式规范化后比对）

    定位符格式：{section}#{章名}/p[0]/split[M]  或  {section}#{章名}/mech[M]
    """
    sec_name, path = ref.split('#', 1)
    sec = section(t, sec_name)
    chap, rest = path.split('/', 1)
    # 812 的章节在 <div class="chapter"> 里；其余在 <h3> 起始的 topic 块里
    blk = None
    for b in blocks_812(sec):
        m = re.search(r'<h3>(.*?)</h3>', b, re.S)
        if m and text_of(m.group(1)) == chap:
            blk = b
            break
    if blk is None:
        for b in blocks_topic(sec):
            m = re.search(r'<h3>(.*?)</h3>', b, re.S)
            if m and text_of(m.group(1)) == chap:
                blk = b
                break
    if blk is None:
        raise ValueError(f'未找到章名 {chap!r}')
    if rest.startswith('mech['):
        mi = int(re.match(r'mech\[(\d+)\]', rest).group(1))
        return text_of(re.findall(r'<p class="mech">(.*?)</p>', blk, re.S)[mi])
    m = re.search(r'<p>(.*?)</p>', blk, re.S)
    body = text_of(m.group(1))
    si = int(re.search(r'split\[(\d+)\]', rest).group(1))
    return [x.strip() for x in re.split(r'[；;]', body) if x.strip()][si]


def main():
    t = SRC.read_text(encoding='utf-8')
    total = ok = skipped = 0
    fails = []
    for sid in ('812', '315', '101', '204'):
        doc = json.loads((M / 'subjects' / sid / f'{sid}.json').read_text(encoding='utf-8'))
        for p in doc['points']:
            if (p.get('source') or {}).get('kind', 'html') != 'html':
                skipped += 1
                continue
            total += 1
            ref = (p.get('source') or {}).get('ref')
            if not ref:
                fails.append((sid, p['id'], '无 ref'))
                continue
            try:
                got = resolve(t, ref)
            except Exception as e:  # noqa: BLE001
                fails.append((sid, p['id'], f'解析失败 {e}'))
                continue
            if chem.normalize_formulas(got) == p['point']:
                ok += 1
            else:
                fails.append((sid, p['id'], f'不一致 got={got[:36]!r} want={p["point"][:36]!r}'))
    print(f'locator 回溯自检：{ok}/{total} 逐字一致 ({ok / total * 100:.2f}%)')
    print(f'跳过非 html 溯源 {skipped} 点')
    if fails:
        print(f'不一致 {len(fails)} 条：')
        for f in fails[:15]:
            print('  ', f)
        sys.exit(1)


if __name__ == '__main__':
    main()
