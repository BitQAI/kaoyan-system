#!/usr/bin/env python3
"""范文 JSON → ky-point 知识点（整篇朗读 / 回译 / 默写 / 句式迁移）。

范文由人写进 204-essays.jsonl；本脚本只做结构转换与校验，不改文字。
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
META = ROOT / '知识点元数据'
SRC = META / 'subjects' / '204' / '204-essays.jsonl'
CHAPTERS = {'204-08': '写作 A（应用文）', '204-09': '写作 B（短文）'}
MAX_POINT = 40          # answer_points 单项字数上限（schema 约束）
MIN_WORDS = {'204-08': 100, '204-09': 150}   # 小作文 / 大作文字数下限
EXAM_LABEL = {'204-08': '小作文', '204-09': '大作文'}


def _cut(s: str, n: int = MAX_POINT) -> str:
    s = ' '.join((s or '').split())
    return s if len(s) <= n else s[:n - 1] + '…'


def _points(items: list[str], floor: int = 2, exact: bool = False) -> list[str]:
    if exact:
        return [_cut(x) for x in items if x]
    out = [_cut(x) for x in items if x][:6]
    while len(out) < floor:
        out.append('段意与句式要点')
    return out


def _card(pid: str, n: int, kind: str, question: str, answer: str,
          points: list[str], analysis: str, refs: list[int],
          payload: dict | None = None) -> dict:
    card = {
        'card_id': f'c{pid}-{n}', 'kind': kind, 'card_type': '应用' if kind in ('回译', '句型') else '记忆',
        'question': question, 'front': question,
        'answer': answer, 'back': answer,
        'options': [], 'answer_points': points, 'analysis': analysis,
        'unit_refs': refs,
    }
    if payload:
        card['payload'] = payload
    return card


def _format(essay: dict) -> str:
    full = ' '.join(p['en'].strip() for p in essay['paragraphs'])
    if essay.get('type') == '通知' or full.lstrip().startswith('Notice'):
        return 'notice'
    if full.lstrip().startswith('Dear'):
        return 'letter'
    return 'chart'


def _essay_payload(essay: dict, paras: list[dict], scope: str,
                   index: int | None = None) -> dict:
    """作文卡的结构化内容：段意、中英对照、好词好句、词数要求。"""
    data = {
        'type': 'essay',
        'format': _format(essay),
        'exam': EXAM_LABEL.get(essay['chapter'], ''),
        'title': essay['title'],
        'scope': scope,
        'paragraphs': [{
            'role': p.get('role', ''),
            'en': p['en'].strip(),
            'cn': p.get('cn', ''),
            'keys': p.get('keys') or [],
        } for p in paras],
    }
    if scope == 'full':
        full = ' '.join(p['en'] for p in essay['paragraphs'])
        data['word_count'] = len(full.split())
        data['min_words'] = MIN_WORDS.get(essay['chapter'])
    else:
        data['word_count'] = len(paras[0]['en'].split())
        data['index'] = index
        data['total'] = len(essay['paragraphs'])
    return data


def _validate(essays: list[dict]) -> None:
    bad = []
    for e in essays:
        words = len(' '.join(p['en'] for p in e['paragraphs']).split())
        floor = MIN_WORDS[e['chapter']]
        if words < floor:
            bad.append(f"{e['id']} {e['title']}：{words} 词 < {floor}")
    if bad:
        raise SystemExit('词数不达标：\n' + '\n'.join(bad))


def build_point(essay: dict, order: int) -> dict:
    pid = essay['id']
    paras = essay['paragraphs']
    units = [f'第 {i} 段：{_cut(p["cn"], 36)}' for i, p in enumerate(paras, start=1)]
    full = '\n\n'.join(p['en'].strip() for p in paras)
    cards, n = [], 0

    def add(kind, question, answer, points, analysis, refs, payload=None):
        nonlocal n
        n += 1
        cards.append(_card(pid, n, kind, question, answer, points, analysis, refs,
                           payload))

    add('模板', f'整篇朗读：{essay["title"]}', full,
        _points(essay.get('structure') or ['目的句', '主体展开', '收尾']),
        f'全篇 {len(paras)} 段、约 {len(full.split())} 词。先听整篇抓节奏，再用回译与默写逐段吃透；'
        f'考场按同一骨架换话题词即可复用。',
        list(range(1, len(paras) + 1)),
        _essay_payload(essay, paras, 'full'))

    for i, para in enumerate(paras, start=1):
        add('回译', para['cn'], para['en'],
            _points(para.get('keys') or para['en'].split(',')[:2]),
            f'本段功能：{para.get("role", "段落展开")}。回译时先想句子骨架再补内容，'
            f'对照原文只改表达不改逻辑。',
            [i],
            _essay_payload(essay, [para], 'paragraph', i))

    for blank in essay['blanks']:
        refs = [blank['para']]
        add('默写', blank['en'], paras[blank['para'] - 1]['en'],
            _points(blank['answers'], exact=True),
            f'挖空处是功能词与高分表达，默写时注意拼写与介词搭配；'
            f'错一格说明该句式还没进肌肉记忆，回到回译卡再过一遍。',
            refs,
            _essay_payload(essay, [paras[blank['para'] - 1]], 'paragraph', blank['para']))

    add('句型', f'本篇可迁移句式：{essay["type"]}', '\n'.join(essay['transfer']),
        _points(essay['transfer'][:3]),
        '换话题时只替换名词与理由，句式骨架保留；同一句式在图表作文与小作文里都能用。',
        [1])

    kinds = []
    for c in cards:
        if c['kind'] not in kinds:
            kinds.append(c['kind'])

    return {
        'id': pid, 'chapter': essay['chapter'], 'order': order,
        'point': essay['point'], 'title': essay['title'],
        'explain': essay.get('explain') or f'{essay["type"]}范文，共 {len(paras)} 段。'
                                           f'先听整篇，再做逐段回译与挖空默写，最后用句式卡换话题迁移。',
        'exam': essay.get('exam') or f'写作 {essay["chapter"][-2:]} 节常考题型：{essay["type"]}。'
                                     f'背诵后按题目要求替换收信人、事由与理由即可。',
        'keywords': essay.get('keywords') or [essay['type'], '范文背诵', '句式迁移'],
        'priority': '★', 'tags': [],
        'exam_types': kinds,
        'source': {'ref': f'204-essays#{pid}', 'file': '204-essays.jsonl',
                   'section': essay['type'], 'basis': '自写范文', 'kind': 'md'},
        'spoken': essay.get('spoken') or f'这是一篇{essay["type"]}范文，共 {len(paras)} 段，'
                                         f'背诵时先听整篇，再逐段回译。',
        'units': units,
        'paragraphs': paras,
        'listen': {'card_id': cards[0]['card_id'], 'kind': '模板',
                   'script': essay.get('spoken_long') or full, 'audio': 'pending'},
        'cards': cards,
        'exam_evidence': {'level': 'pending', 'basis': '自写范文，待人工审定', 'sources': []},
        'tts': {'enabled': False},
    }


def build_points(essays: list[dict]) -> list[dict]:
    return [build_point(e, i) for i, e in enumerate(essays, start=1)]


def main():
    essays = [json.loads(l) for l in SRC.read_text(encoding='utf-8').splitlines() if l.strip()]
    _validate(essays)
    points = build_points(essays)
    out = META / 'subjects' / '204' / '204-essay-points.json'
    out.write_text(json.dumps(points, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{out.relative_to(ROOT)}：{len(points)} 篇，'
          f'{sum(len(p["cards"]) for p in points)} 张卡')


if __name__ == '__main__':
    sys.exit(main())
