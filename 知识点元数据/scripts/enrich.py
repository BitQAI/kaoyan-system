#!/usr/bin/env python3
"""LLM 增强：生成 title / explain / exam / keywords（D13=B 全量重生成）。

用法：
  python scripts/enrich.py --subject 812 --limit 3       # 试点
  python scripts/enrich.py --all --concurrency 4         # 全量

断点续跑：结果逐条追加到 subjects/<sid>/<sid>-enrich.jsonl，已有 id 跳过（--force 重生成）。
"""
import argparse
import json
import os
import pathlib
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import llm  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'
BUILD = ROOT / '.build'
MODEL = 'deepseek-v4.1-flash'

SYSTEM = (
    '你是考研辅导助教，为备战 2027 考研（云南农业大学 095400 林业）的学生生成考点精讲卡。'
    '只输出 JSON 对象本身，不要代码块标记、不要多余文字。'
    '内容必须依据考研大纲与标准教材，不确定的内容写「请对照教材核验」，不要编造。'
    '涉及化学式、离子、公式时一律使用 Unicode 下标与上标（如 H₂O、CO₂、SO₄²⁻、c₁V₁=c₂V₂），'
    '禁止写成 ASCII 形态（H2O、CO2、SO42-）。'
)

STYLE = {
    '101': '政治理论：explain 讲清概念的内涵与逻辑关系；exam 指明单选/多选/分析题怎么考、'
           '常见设问、易混概念辨析与答题要点。',
    '315': '化学（农）：explain 讲清定义、适用条件与内在联系；exam 指明计算题/判断题的考法与'
           '常见陷阱。涉及公式、数值用 Unicode 符号，化学式、常数、计算结果必须准确。',
    '812': '植物生理学：explain 用因果链讲清机制（刺激→信号→响应）；exam 覆盖名词解释/'
           '简答/论述的作答结构与常考角度。',
    '204': '英语（二）：explain 用中文讲清考点含义与训练方法；exam 指明对应题型（完形/阅读A/B/'
           '翻译/写作）的解题步骤、定位方法与常见失分点。',
}

_lock = threading.Lock()



def build_prompt(sub, chap_name, p):
    return (
        f"科目：{sub['name']}\n"
        f"章节：{chap_name}\n"
        f"考点：{p['point']}\n"
        f"本章权重：中心 {p.get('_chapter_weight', '?')} 分；"
        f"本章标签：{'、'.join(p.get('_chapter_tags') or []) or '无'}\n\n"
        f"请输出 JSON 对象，含四个字段：\n"
        f"① title：≤14 字的检索/卡面短标题，只提示「考的是什么」，"
        f"绝不能包含答案、数字结论或判断方向（例：水势的组成与各分势含义）。\n"
        f"② explain：3–6 句理解解析，面向备考学生可直接当讲解稿。"
        f"讲清是什么、为什么重要、内在逻辑。{STYLE[sub['id']]}\n"
        f"③ exam：考点怎么考，3–4 条，用半角分号 ; 分隔、不换行。"
        f"含常考题型、设问方式、答题要点、易错点。\n"
        f"④ keywords：3–5 个关键词的数组。\n"
        f"三字段缺一不可。{STYLE[sub['id']]}"
    )


def clean(rec):
    """规范化与校验；不合格返回 None 以触发重试。"""
    if not isinstance(rec, dict):
        return None
    title = (rec.get('title') or '').strip()
    explain = (rec.get('explain') or '').strip()
    exam = (rec.get('exam') or '').strip()
    kws = rec.get('keywords')
    if not isinstance(kws, list):
        kws = []
    kws = [str(k).strip() for k in kws if str(k).strip()][:6]
    if not title or not explain or not exam or len(kws) < 3:
        return None
    if len(title) > 20:
        return None
    explain = re.sub(r'\s*\n\s*', '', explain)
    exam = re.sub(r'\s*\n\s*', '；', exam).replace('；；', '；')
    return {'title': title, 'explain': explain, 'exam': exam, 'keywords': kws}


def load_done(path):
    done = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                done[r['id']] = r
            except json.JSONDecodeError:
                continue
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--subject', action='append', default=[])
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--concurrency', type=int, default=4)
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    ext = json.loads((BUILD / 'extract.json').read_text(encoding='utf-8'))
    subjects = ext['subjects']
    if not args.all:
        subjects = [s for s in subjects if s['id'] in args.subject]
    if not subjects:
        raise SystemExit('用 --all 或 --subject 指定科目')

    for sub in subjects:
        sid = sub['id']
        chap_meta = {c['id']: c for c in sub['chapters']}
        out_dir = META / 'subjects' / sid
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f'{sid}-enrich.jsonl'
        done = {} if args.force else load_done(out_file)
        todo = [p for p in sub['points'] if p['id'] not in done]
        if args.limit:
            todo = todo[:args.limit]
        print(f'{sid} {sub["name"]}：待生成 {len(todo)}（已缓存 {len(done)}）')

        def one(p):
            cm = chap_meta.get(p['chapter'], {})
            pp = dict(p)
            pp['_chapter_weight'] = cm.get('weight_center')
            pp['_chapter_tags'] = cm.get('note')
            got = llm.call_llm([
                {'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': build_prompt(sub, cm.get('name', ''), pp)},
            ])
            c = clean(got) if got else None
            return (p['id'], c)

        ok = fail = 0
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(one, p): p for p in todo}
            for i, fut in enumerate(as_completed(futs), 1):
                pid, c = fut.result()
                if c:
                    ok += 1
                    with _lock:
                        with out_file.open('a', encoding='utf-8') as f:
                            f.write(json.dumps({'id': pid, **c}, ensure_ascii=False) + '\n')
                else:
                    fail += 1
                if i % 20 == 0 or i == len(todo):
                    print(f'  进度 {i}/{len(todo)}（成功 {ok} · 失败 {fail}）')
        print(f'完成：成功 {ok} · 失败 {fail} → {out_file.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
