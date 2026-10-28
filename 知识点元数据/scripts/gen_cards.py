#!/usr/bin/env python3
"""题型化问答卡生成（ky-point/2.0）。

每点生成 2–3 张卡，字段：kind / question / options? / answer / analysis。
- 315：选择（四选一）+ 填空，适合时加 计算/分析/合成
- 812：名解 + 简答，第一梯队/适合展开的点加 论述
- 101：名词解释/简答/分析 任选两类
- 204：词汇/句型/技巧/模板 任选两类

产出：subjects/<sid>/<sid>-cards-v2.jsonl（断点续跑）
用法：
  python3 scripts/gen_cards.py --subject 315 --limit 5
  python3 scripts/gen_cards.py --all --concurrency 5
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chem  # noqa: E402
import llm  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'

KINDS = {
    '315': ['选择', '填空', '计算', '分析', '合成'],
    '812': ['名解', '简答', '论述'],
    '101': ['名词解释', '简答', '分析'],
    '204': ['词汇', '句型', '技巧', '模板'],
}

ALIAS = {
    '315': {
        '选择题': '选择', '填空题': '填空', '计算题': '计算',
        '分析题': '分析', '合成题': '合成', '综合': '分析',
    },
    '812': {'名词解释': '名解', '名解': '名解'},
}

REQUIRED = {
    '315': ('选择', '填空'),
    '812': ('名解', '简答'),
}

SYSTEM = {
    '315': (
        '你是考研 315《化学（农）》命题研究员。严格参照真题设问方式出题：'
        '选择题四选一，设问可含计算、排序、判断、鉴别、现象推断；'
        '填空题填数值、填偏高/偏低/不影响、完成反应式、系统命名、填序号；'
        '计算题给足数据与条件；分析题解释现象/判断/鉴别/设计；合成题给原料与目标产物。'
        '每道题必须给出答案与解析；解析写清依据、步骤、易错点。'
        '只输出 JSON 对象本身，不要代码块与多余文字。'
        '化学式、离子、单位用 Unicode 角标（H₂O、SO₄²⁻、kJ·mol⁻¹）；'
        '机理代号 SN1/SN2/E1/E2 保持原样。'
    ),
    '812': (
        '你是云南农业大学 812《植物生理学》命题研究员。'
        '官方题型只有名词解释（约20%）、简答题（约60%）、论述题（约20%）。'
        '名词解释写「名词解释：X」；简答参照真题设问（简述/为什么/有哪些/举出证据并分析）；'
        '论述用论述/试述/分析/请阐述。每道题必须给出答案与解析。'
        '只输出 JSON 对象本身，不要代码块与多余文字。'
    ),
    '101': (
        '你是考研 101《思想政治理论》命题研究员。题型从名词解释、简答、分析中选取。'
        '严格依据现行统编教材与最新中央精神表述；教材有标准表述的考点请直接作答，'
        '不要附加「请核对教材」；只有确实无法确定的具体数据或新提法才标注。'
        '每道题必须给出答案与解析。只输出 JSON 对象本身，不要代码块与多余文字。'
    ),
    '204': (
        '你是考研 204《英语（二）》命题研究员。题型从词汇、句型、技巧、模板中选取。'
        '题目必须可操作、可自测；每道题必须给出答案与解析。'
        '只输出 JSON 对象本身，不要代码块与多余文字。'
    ),
}


def _is_inorganic(chapter_id: str) -> bool:
    try:
        return int(chapter_id.split('-')[1]) <= 11
    except (IndexError, ValueError):
        return True


def build_prompt(sid: str, p: dict, chap: dict) -> str:
    head = (
        f"科目：{sid}\n章节：{chap.get('name', '')}\n"
        f"考点：{p['point']}\n解析：{p.get('explain', '')}\n"
        f"这个考点通常怎么考：{p.get('exam', '')}\n优先级：{p.get('priority', '○')}\n\n"
    )
    if sid == '315':
        block = '无机及分析化学' if _is_inorganic(p['chapter']) else '有机化学'
        third = ('有机章优先「合成」或「填空（完成反应式/系统命名）」'
                 if block == '有机化学' else '无机章优先「计算」或「分析」')
        body = (
            f"板块：{block}\n"
            '生成 2–3 道题，严格按 315 真题设问：\n'
            '① 必出 1 道「选择」：四选一，设问参照真题（下列…正确的是/最…的是/排序/判断/鉴别/计算），'
            '4 个选项 A–D 互不重复，只有一个正确；\n'
            '② 必出 1 道「填空」：用 ______ 表示空，可填数值/偏高偏低/反应式/系统命名/序号；\n'
            f'③ 若考点适合，再出 1 道「计算」「分析」或「合成」之一（{third}）。\n'
            '答案：选择只写 A/B/C/D；填空写应填内容；计算给结果；分析/合成给完整答案。\n'
            '正确答案的位置请分散到 A/B/C/D，不要总放在 A；解析中的字母必须与选项顺序严格一致，'
            '不能出现“答案 A 但解析说 A 错”的矛盾。\n'
            '解析 60–400 字：选择说明正确项依据并逐项排除错误项；'
            '计算给公式、代入、结果与单位；其他写依据、步骤、易错点。\n'
            '只输出：{"cards":[{"kind":"选择","question":"…","options":["A. …","B. …","C. …","D. …"],'
            '"answer":"B","analysis":"…"},{"kind":"填空","question":"… ______。","answer":"…","analysis":"…"}]}'
        )
    elif sid == '812':
        tier = chap.get('tier', 3)
        body = (
            f"梯队：第 {tier} 梯队\n"
            '生成 2–3 道题，严格按官方题型：\n'
            '① 必出 1 道「名解」：question 写「名词解释：X」；\n'
            '② 必出 1 道「简答」：参照真题设问（简述/为什么/有哪些/举出证据并分析）；\n'
            f'③ {"本章为第一梯队，必须加 1 道「论述」" if tier == 1 else "若考点适合综合展开，可加 1 道「论述」"}'
            '（论述/试述/分析/请阐述）。\n'
            '答案：名解给定义+结构基础+功能意义；简答用 ①②③ 分点；论述按「立论—分论—结论」。\n'
            '解析 60–400 字：答题结构、得分点、常见失分点。\n'
            '只输出：{"cards":[{"kind":"名解","question":"名词解释：X","answer":"…","analysis":"…"},'
            '{"kind":"简答","question":"…？","answer":"…","analysis":"…"}]}'
        )
    elif sid == '101':
        body = (
            '生成 2 张卡，kind 从 名词解释 / 简答 / 分析 中选最贴合的两类。\n'
            '答案：名词解释给概念内涵；简答给 ①②③ 分点；分析给论证结构与落脚点。\n'
            '解析 60–300 字：得分点、失分点、易错辨析。\n'
            '只输出：{"cards":[{"kind":"简答","question":"…","answer":"…","analysis":"…"}]}'
        )
    else:
        body = (
            '生成 2 张卡，kind 从 词汇 / 句型 / 技巧 / 模板 中选最贴合的两类。\n'
            '答案：词汇给释义+语境+用法；句型给结构+例句；技巧给步骤；模板给可套用框架。\n'
            '解析 60–300 字：判断依据、解题步骤、易错点。\n'
            '只输出：{"cards":[{"kind":"技巧","question":"…","answer":"…","analysis":"…"}]}'
        )
    return head + body


def _text(v, limit: int = 800) -> str:
    s = str(v or '').replace('|', '｜')
    s = re.sub(r'\s+', ' ', s).strip()
    s = chem.normalize_formulas(s)
    return s[:limit]


def _kind(sid: str, raw: str) -> str | None:
    k = re.sub(r'\s+', '', str(raw or ''))
    k = ALIAS.get(sid, {}).get(k, k)
    return k if k in KINDS[sid] else None


def _split_inline_options(question: str) -> tuple[str, list[str]]:
    """从题干中拆出内联的 A–D 选项（模型偶尔把选项写进题干）。"""
    m = re.search(r'(?:^|\s)A[.、．]\s*', question)
    if not m:
        return question, []
    stem = question[:m.start()].strip()
    tail = question[m.start():]
    parts = re.split(r'(?:^|\s)([A-D])[.、．]\s*', tail)
    opts = {}
    for i in range(1, len(parts) - 1, 2):
        opts[parts[i]] = parts[i + 1].strip().rstrip('；;')
    if set(opts) == {'A', 'B', 'C', 'D'}:
        return stem, [opts[x] for x in 'ABCD']
    return question, []


def _options(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    out = []
    for o in raw[:6]:
        s = _text(o, 160)
        s = re.sub(r'^[A-Da-d]\s*[.、．,，:：\)）]\s*', '', s).strip()
        if s and s not in out:
            out.append(s)
    return out if len(out) == 4 else []


def _letter(raw: str, options: list[str]) -> str | None:
    s = _text(raw, 200)
    m = re.match(r'^[(（]?([A-Da-d])[)）]?\s*(?:[.、．,，:：\)）]|$|\s)', s)
    if m:
        return m.group(1).upper()
    m = re.search(r'(?:答案|选)\s*[:：]?\s*([A-Da-d])', s)
    if m:
        return m.group(1).upper()
    for i, o in enumerate(options):
        if o and (o in s or s in o) and len(s) >= 4:
            return 'ABCD'[i]
    return None


def _label(options: list[str]) -> list[str]:
    return [f"{'ABCD'[i]}. {s}" for i, s in enumerate(options)]


def _analysis_consistent(answer: str, analysis: str) -> bool:
    """解析里若明确判错/判对某个字母，必须与答案一致。"""
    wrong, right = set(), set()
    for m in re.finditer(
            r'(?:选项|项)?\s*([A-D])\s*(?:项|说法|叙述)?\s*(?:是|为)?\s*'
            r'(错|错误|不正确|不对|不符合)', analysis):
        wrong.add(m.group(1))
    for m in re.finditer(
            r'(?:选项|项)?\s*([A-D])\s*(?:项|说法|叙述)?\s*(?:是|为)?\s*'
            r'(正确|对|符合)', analysis):
        right.add(m.group(1))
    if answer in wrong:
        return False
    if right and answer not in right:
        return False
    return True


def clean(got, sid: str, pid: str) -> list[dict]:
    if not isinstance(got, dict) or not isinstance(got.get('cards'), list):
        return []
    out, seen = [], set()
    for idx, c in enumerate(got['cards']):
        if not isinstance(c, dict):
            continue
        kind = _kind(sid, c.get('kind'))
        if not kind:
            continue
        question = _text(c.get('question'), 500)
        opts = _options(c.get('options'))
        if kind == '选择' and not opts:
            question, opts = _split_inline_options(question)
            opts = [_text(x, 160) for x in opts]
        if kind == '选择' and len(opts) != 4:
            continue
        answer = _text(c.get('answer'), 800)
        analysis = _text(c.get('analysis'), 600)
        if not (question and answer and analysis):
            continue
        if len(analysis) < 30:
            continue
        card = {'kind': kind, 'question': question, 'answer': answer,
                'analysis': analysis}
        if kind == '选择':
            letter = _letter(answer, opts)
            if not letter:
                continue
            if not _analysis_consistent(letter, analysis):
                continue
            card['options'] = _label(opts)
            card['answer'] = letter
        key = re.sub(r'\s+', '', question).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(card)
    # 题型顺序：必出题型在前
    order = {k: i for i, k in enumerate(
        ['选择', '填空', '名解', '简答', '计算', '分析', '合成', '论述',
         '名词解释', '词汇', '句型', '技巧', '模板'])}
    out.sort(key=lambda c: order.get(c['kind'], 99))
    # 保留必出题型 + 最多 3 张
    keep = []
    for k in REQUIRED.get(sid, ()):
        for c in out:
            if c['kind'] == k and c not in keep:
                keep.append(c)
                break
    for c in out:
        if c not in keep and len(keep) < 3:
            keep.append(c)
    return keep[:3]


def load_done(path: pathlib.Path) -> set[str]:
    done = set()
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                try:
                    done.add(json.loads(line)['id'])
                except (json.JSONDecodeError, KeyError):
                    continue
    return done


_lock = threading.Lock()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--subject', action='append', default=[])
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--concurrency', type=int, default=5)
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    subjects = ['812', '315', '101', '204']
    if not args.all:
        subjects = [s for s in subjects if s in args.subject]
    if not subjects:
        raise SystemExit('用 --all 或 --subject 指定科目')

    for sid in subjects:
        doc = json.loads((META / 'subjects' / sid / f'{sid}.json').read_text(encoding='utf-8'))
        chap_meta = {c['id']: c for c in doc['chapters']}
        out_file = META / 'subjects' / sid / f'{sid}-cards-v2.jsonl'
        done = set() if args.force else load_done(out_file)
        if args.force and out_file.exists():
            out_file.unlink()
        todo = [p for p in doc['points'] if p['id'] not in done]
        if args.limit:
            todo = todo[:args.limit]
        print(f'{sid} {doc["name"]}：待生成 {len(todo)}（已缓存 {len(done)}）', flush=True)

        def one(p: dict):
            chap = chap_meta.get(p['chapter'], {})
            messages = [
                {'role': 'system', 'content': SYSTEM[sid]},
                {'role': 'user', 'content': build_prompt(sid, p, chap)},
            ]
            sess = f'ky-meta-{sid}'
            cards = clean(llm.call_llm(messages, max_tokens=5000, session=sess),
                          sid, p['id'])
            missing = [k for k in REQUIRED.get(sid, ()) if k not in {c['kind'] for c in cards}]
            if missing:
                messages.append({
                    'role': 'user',
                    'content': (f'上一版缺少必出题型：{", ".join(missing)}。'
                                f'请补齐并只输出完整 JSON，仍遵守原格式。'),
                })
                cards = clean(llm.call_llm(messages, max_tokens=5000, session=sess),
                              sid, p['id'])
            return p['id'], cards

        ok = fail = ncards = 0
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(one, p): p for p in todo}
            for i, fut in enumerate(as_completed(futs), 1):
                pid, cards = fut.result()
                if cards:
                    ok += 1
                    ncards += len(cards)
                    with _lock:
                        with out_file.open('a', encoding='utf-8') as f:
                            f.write(json.dumps({'id': pid, 'cards': cards},
                                               ensure_ascii=False) + '\n')
                else:
                    fail += 1
                    print(f'  ! {pid} 生成失败', flush=True)
                if i % 10 == 0 or i == len(todo):
                    print(f'  进度 {i}/{len(todo)}（成功 {ok} · 失败 {fail} · 卡 {ncards}）',
                          flush=True)
        print(f'{sid} 完成：成功 {ok} · 失败 {fail} · 共 {ncards} 张', flush=True)


if __name__ == '__main__':
    main()
