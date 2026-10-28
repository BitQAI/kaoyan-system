#!/usr/bin/env python3
"""把 <sid>-cards-v2.jsonl 合并为正式 <sid>-cards.jsonl。

职责：
1. 赋全局唯一 card_id = c{point_id}-{n}
2. 生成 front/back 兼容字段
3. 计算 exam_types（cards[].kind 去重）
4. 选代表题并拼「设问 → 答案 → 解析」朗读稿 listen
5. 812 章级配额核验
6. 生成失败的点回退到旧卡片（解析写占位，明确标注）

用法：python3 scripts/finalize_cards.py
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chem  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'
BACKUP = ROOT / '.build' / 'backup' / '2026-10-26-cards-v1'

KINDS = {
    '315': ['选择', '填空', '计算', '分析', '合成'],
    '812': ['名解', '简答', '论述'],
    '101': ['名词解释', '简答', '分析'],
    '204': ['词汇', '句型', '技巧', '模板'],
}
LISTEN_PREF = {
    '315': ['选择', '填空', '计算', '分析', '合成'],
    '812': ['简答', '名解', '论述'],
    '101': ['简答', '分析', '名词解释'],
    '204': ['技巧', '句型', '词汇', '模板'],
}
OLD_KIND = {
    '315': {'名词解释': '填空', '简答': '分析', '公式速记': '填空', '综合': '分析'},
    '812': {'名解': '名解', '简答': '简答', '论述': '论述'},
    '101': {'名词解释': '名词解释', '简答': '简答', '分析': '分析'},
    '204': {'词汇': '词汇', '句型': '句型', '技巧': '技巧', '模板': '模板'},
}
QUOTA_812 = {'名解': 2, '简答': 2, '论述': 1}
PLACEHOLDER = ('本题沿用旧版卡片，题型化解析尚未生成；'
               '请重跑 scripts/gen_cards.py 补齐该知识点。')


def load_jsonl(path: pathlib.Path) -> dict:
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            out[r['id']] = r
        except (json.JSONDecodeError, KeyError):
            continue
    return out


_SUP = str.maketrans('0123456789+-n()', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ⁽⁾')


def _math(s: str) -> str:
    """把模型常见的 ^{...} 指数写法转成可读的 Unicode 上标。"""
    s = s.replace('^{1/2}', '^½').replace('^{-1/2}', '^⁻½')
    def sup(m):
        inner = m.group(1)
        if all(ch in '0123456789+-n()' for ch in inner):
            body = inner.translate(_SUP)
            if len(inner) > 1 and any(ch in '+-' for ch in inner):
                return '^⁽' + body + '⁾'
            return '^' + body
        return '^(' + inner + ')'
    return re.sub(r'\^\{([^{}]+)\}', sup, s)


def _clean(s: str, limit: int = 800) -> str:
    s = re.sub(r'\s+', ' ', str(s or '')).replace('|', '｜').strip()
    return _math(chem.normalize_formulas(s))[:limit]


def _option_text(card: dict) -> str:
    letter = card.get('answer', '')
    opts = card.get('options') or []
    if letter in 'ABCD' and len(opts) == 4:
        t = re.sub(r'^[A-D]\s*[.、．]\s*', '', opts['ABCD'.index(letter)])
        return f"{letter}，{t}"
    return letter


LETTER_CTX = re.compile(r'''
    (?:
        (?:选项|项)\s*(?P<l1>[A-D])
      | (?P<l2>[A-D])\s*(?:项|错|正确|错误|不对|对|符合|不符合|均)
      | [（(](?P<l3>[A-D])[）)]
      | (?:故选|答案(?:为|是)?|应选|选)\s*(?P<l4>[A-D])
      | (?P<l5>[A-D])(?=\s*[、,，和与及]\s*[A-D])
      | (?<=\s)(?P<l6>[A-D])(?=\s*[、,，和与及])
    )
''', re.X)


def _rewrite_letters(text: str, perm: dict) -> str:
    def repl(m):
        for g in ('l1', 'l2', 'l3', 'l4', 'l5', 'l6'):
            if m.group(g):
                return m.group(0).replace(m.group(g), perm.get(m.group(g), m.group(g)))
        return m.group(0)
    return LETTER_CTX.sub(repl, text)


def _unhandled_letters(text: str) -> bool:
    rest = LETTER_CTX.sub('', text)
    return bool(re.search(r'(?<![A-Za-z])[A-D](?![A-Za-z])', rest))


def analysis_consistent(answer: str, analysis: str) -> bool:
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


def _option_contents(card: dict) -> list[str]:
    return [re.sub(r'^[A-D]\s*[.、．]\s*', '', o) for o in card['options']]


def _set_options(card: dict, contents: list[str]) -> None:
    card['options'] = [f"{'ABCD'[i]}. {s}" for i, s in enumerate(contents)]


def rebalance_choices(cards: list[dict]) -> None:
    """把正确答案位置轮换到最少出现的字母，并同步重写解析字母。"""
    counts = collections.Counter()
    for card in cards:
        if card['kind'] != '选择' or len(card.get('options') or []) != 4:
            continue
        old = card['answer']
        if old not in 'ABCD':
            counts[old] += 1
            continue
        target = min('ABCD', key=lambda L: (counts[L], 'ABCD'.index(L)))
        if target == old:
            counts[old] += 1
            continue
        analysis = card['analysis']
        if _unhandled_letters(analysis):
            counts[old] += 1
            continue
        old_i, new_i = 'ABCD'.index(old), 'ABCD'.index(target)
        contents = _option_contents(card)
        contents[old_i], contents[new_i] = contents[new_i], contents[old_i]
        perm = {old: target, target: old}
        new_analysis = _rewrite_letters(analysis, perm)
        if not analysis_consistent(target, new_analysis):
            counts[old] += 1
            continue
        _set_options(card, contents)
        card['answer'] = target
        card['analysis'] = new_analysis
        counts[target] += 1


def listen_script(card: dict) -> str:
    q, a, x = card['question'], card['answer'], card['analysis']
    if card['kind'] == '选择' and card.get('options'):
        opts = ' '.join(card['options'])
        return f"设问：{q} 选项：{opts} 答案：{_option_text(card)}。解析：{x}"
    return f"设问：{q} 答案：{a}。解析：{x}"


def pick_listen(sid: str, cards: list[dict]) -> dict:
    for k in LISTEN_PREF[sid]:
        for c in cards:
            if c['kind'] == k:
                return c
    return cards[0]


def fallback_cards(sid: str, pid: str, old: dict) -> list[dict]:
    out = []
    for c in old.get(pid, {}).get('cards', []):
        kind = OLD_KIND[sid].get(c.get('kind'), KINDS[sid][-1])
        out.append({
            'kind': kind,
            'question': _clean(c.get('front'), 500),
            'answer': _clean(c.get('back'), 800),
            'analysis': PLACEHOLDER,
        })
    return out


def main() -> int:
    problems = []
    fallback_n = 0
    for sid in ('812', '315', '101', '204'):
        doc = json.loads((META / 'subjects' / sid / f'{sid}.json').read_text(encoding='utf-8'))
        v2 = load_jsonl(META / 'subjects' / sid / f'{sid}-cards-v2.jsonl')
        old = load_jsonl(BACKUP / f'{sid}-cards.jsonl')
        lines, kinds_all = [], collections.Counter()

        for p in doc['points']:
            pid = p['id']
            cards = v2.get(pid, {}).get('cards') or []
            if not cards:
                cards = fallback_cards(sid, pid, old)
                if cards:
                    fallback_n += 1
                    problems.append(f'{sid} {pid} 无 v2 卡片，已回退旧卡')
            clean = []
            for i, c in enumerate(cards[:4], 1):
                kind = c.get('kind')
                if kind not in KINDS[sid]:
                    problems.append(f'{sid} {pid} kind 非法 {kind}')
                    continue
                question = _clean(c.get('question'), 500)
                answer = _clean(c.get('answer'), 800)
                analysis = _clean(c.get('analysis'), 600)
                if not (question and answer and analysis):
                    problems.append(f'{sid} {pid} 卡片字段为空')
                    continue
                obj = {
                    'card_id': f'c{pid}-{len(clean) + 1}',
                    'kind': kind,
                    'question': question,
                    'answer': answer,
                    'analysis': analysis,
                    'front': question,
                    'back': answer,
                    'point_id': pid,
                }
                if kind == '选择':
                    opts = c.get('options') or []
                    if len(opts) != 4 or any(not str(o).strip() for o in opts):
                        problems.append(f'{sid} {pid} 选择题选项不是 4 项')
                        continue
                    obj['options'] = [_clean(o, 160) for o in opts]
                clean.append(obj)
                kinds_all[kind] += 1
            if not clean:
                problems.append(f'{sid} {pid} 最终无可用卡片')
                continue
            exam_types = []
            for c in clean:
                if c['kind'] not in exam_types:
                    exam_types.append(c['kind'])
            lc = pick_listen(sid, clean)
            listen = {
                'card_id': lc['card_id'],
                'kind': lc['kind'],
                'script': _clean(listen_script(lc), 2000),
                'audio': 'pending',
            }
            lines.append({'id': pid, 'cards': clean,
                          'exam_types': exam_types, 'listen': listen})

        # 全科统一轮换答案位置（计数器必须跨点共享），再重算听稿
        if sid == '315':
            rebalance_choices([c for line in lines for c in line['cards']])
            for line in lines:
                lc = pick_listen(sid, line['cards'])
                line['listen'] = {
                    'card_id': lc['card_id'], 'kind': lc['kind'],
                    'script': _clean(listen_script(lc), 2000),
                    'audio': 'pending',
                }

        out = META / 'subjects' / sid / f'{sid}-cards.jsonl'
        with out.open('w', encoding='utf-8') as f:
            for r in lines:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')

        n_cards = sum(len(r['cards']) for r in lines)
        print(f'{sid}: 点 {len(lines)} · 卡 {n_cards} · '
              f'题型 {dict(kinds_all)}', flush=True)

        if sid == '812':
            per = collections.defaultdict(collections.Counter)
            chap_of = {p['id']: p['chapter'] for p in doc['points']}
            for r in lines:
                for c in r['cards']:
                    per[chap_of[r['id']]][c['kind']] += 1
            for chid, cnt in sorted(per.items()):
                for k, need in QUOTA_812.items():
                    if cnt.get(k, 0) < need:
                        problems.append(f'812 {chid} {k} 仅 {cnt.get(k, 0)} 张 < 配额 {need}')

        # 答案分布
        letters = collections.Counter(
            c['answer'] for r in lines for c in r['cards']
            if c['kind'] == '选择' and c.get('answer') in 'ABCD')
        if letters:
            total = sum(letters.values())
            top = letters.most_common(1)[0]
            print(f'  选择题 {total} 道 · 答案分布 {dict(letters)}'
                  + ('  ← 偏斜' if top[1] / total > 0.4 else ''), flush=True)

    print(f'\n回退旧卡 {fallback_n} 点')
    if problems:
        print(f'问题 {len(problems)} 条：')
        for p in problems[:30]:
            print('  ', p)
        if len(problems) > 30:
            print(f'   …其余 {len(problems) - 30} 条省略')
    else:
        print('合并校验通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
