#!/usr/bin/env python3
"""把词表、词条、词组、辨析与范文装配成 204.json（幂等，可重跑）。

输入（都在 subjects/204/ 下）：
  204-vocab-list.jsonl  选词结果（决定顺序）
  204-vocab.jsonl       词条（释义/音标/例句/易混/词组）
  204-phrases.jsonl     词组卡
  204-confusable.jsonl  辨析卡
  204-essay-points.json 范文知识点
  chapters/204-08.json、chapters/204-09.json  基础章节
输出：chapters/204-10.json、204-11.json 与合并后的 204.json。
"""
import json
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from split_subject import split_doc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
GROUP = 30                     # 每点卡片上限（schema 约束）
PENDING = {'level': 'pending', 'basis': '由词表与语料自动装配，待人工复核',
           'sources': []}


def _src(essay_ref: str, kind: str) -> dict:
    return {'ref': essay_ref, 'file': '204-vocab.jsonl', 'section': kind,
            'basis': '真题语料与模型生成', 'kind': 'jsonl'}


def _listen(card_id: str, kind: str, script: str) -> dict:
    return {'card_id': card_id, 'kind': kind, 'script': script, 'audio': 'pending'}


def _meaning_text(meanings: list[dict]) -> str:
    return '；'.join(f'{m.get("pos", "")}{m.get("cn", "")}'.strip() for m in meanings if m.get('cn'))


def word_card(pid: str, n: int, entry: dict, unit: str) -> dict:
    word = entry['word']
    meanings = entry.get('meanings') or []
    answer = _meaning_text(meanings) or word
    points = [f'{m.get("pos", "")}{m.get("cn", "")}'.strip() for m in meanings][:4]
    example = (entry.get('examples') or [{}])[0]
    if example.get('kind') == '真题':
        points.append('真题考法：' + (example.get('part') or '阅读'))
    points.append('易混：' + (entry['confusables'][0]['word'] if entry.get('confusables') else '无'))
    question = f'{word}（{entry.get("phonetic", "")}）'
    analysis = (f'{word}：{answer}。' +
                ('易混 ' + entry['confusables'][0]['word'] + '，' +
                 entry['confusables'][0]['diff'] if entry.get('confusables') else
                 '注意常见搭配与词性变化。'))
    if len(analysis) < 30:
        analysis += ' 背诵时结合真题原句记搭配，比单记中文释义更牢。'
    return {
        'card_id': f'c{pid}-{n}', 'kind': '词汇', 'card_type': '记忆',
        'question': question, 'front': question,
        'answer': answer, 'back': answer,
        'options': [], 'answer_points': points[:6] if len(points) >= 2 else points + ['释义'],
        'analysis': analysis, 'unit_refs': [n],
        'payload': {'type': 'word', 'word': word, 'phonetic': entry.get('phonetic', ''),
                    'meanings': meanings, 'examples': (entry.get('examples') or [])[:2],
                    'confusables': entry.get('confusables') or [],
                    'phrases': entry.get('phrases') or []},
    }


def build_word_points(entries: list[dict]) -> list[dict]:
    points = []
    for gi in range(0, len(entries), GROUP):
        chunk = entries[gi:gi + GROUP]
        pid = f'2041{gi // GROUP + 1:03d}'
        lo, hi = gi + 1, gi + len(chunk)
        units = [f'{e["word"]}：{_meaning_text(e.get("meanings") or [])[:36]}' for e in chunk]
        cards = [word_card(pid, i, e, units[i - 1]) for i, e in enumerate(chunk, start=1)]
        title = f'核心词汇 {gi // GROUP + 1:02d}（第 {lo}–{hi}）'
        points.append({
            'id': pid, 'chapter': '204-10', 'order': gi // GROUP + 1,
            'point': title, 'title': title,
            'explain': f'本组 {len(chunk)} 词按真题词频排序：{chunk[0]["word"]} 到 {chunk[-1]["word"]}。'
                       f'每张卡正面是词与音标，背面是释义、真题原句与考法、易混近义与必要搭配。',
            'exam': '词汇不单独设题，但阅读、翻译、完形的失分多来自这些词的熟词僻义与固定搭配。',
            'keywords': ['核心词汇', f'第 {lo}–{hi}', '真题例句', '易混辨析'][:8],
            'priority': '○', 'tags': [], 'exam_types': ['词汇'],
            'spoken': f'这一组是第 {lo} 到 {hi} 高频词，共 {len(chunk)} 个，先看真题句再看释义。',
            'units': units,
            'listen': _listen(cards[0]['card_id'], '词汇',
                              f'第 {lo} 到 {hi} 高频词，共 {len(chunk)} 个。'),
            'cards': cards, 'source': _src('204-vocab.jsonl', 'vocab'),
            'exam_evidence': dict(PENDING), 'tts': {'enabled': False},
        })
    return points


def phrase_card(pid: str, n: int, p: dict) -> dict:
    phrase = p['phrase']
    ans = p.get('cn') or phrase
    return {
        'card_id': f'c{pid}-{n}', 'kind': '词汇', 'card_type': '记忆',
        'question': phrase, 'front': phrase, 'answer': ans, 'back': ans,
        'options': [], 'answer_points': [ans, '搭配：' + phrase][:6],
        'analysis': f'{phrase}：{ans}。词组题看搭配落点，先判断后面跟的是名词、副词还是介词结构。',
        'unit_refs': [n],
        'payload': {'type': 'phrase', 'word': phrase, 'phonetic': '',
                    'meanings': [{'pos': 'phr.', 'cn': ans}], 'examples': [],
                    'confusables': [], 'phrases': []},
    }


def build_phrase_points(phrases: list[dict]) -> list[dict]:
    points = []
    for gi in range(0, len(phrases), GROUP):
        chunk = phrases[gi:gi + GROUP]
        pid = f'20411{gi // GROUP + 1:02d}'
        units = [f'{p["phrase"]}：{p.get("cn", "")[:36]}' for p in chunk]
        cards = [phrase_card(pid, i, p) for i, p in enumerate(chunk, start=1)]
        idx = gi // GROUP + 1
        points.append({
            'id': pid, 'chapter': '204-11', 'order': idx,
            'point': f'高频词组 {idx:02d}', 'title': f'高频词组 {idx:02d}',
            'explain': f'{len(chunk)} 条真题高频搭配，按语料出现次数排序。',
            'exam': '完形的固定搭配题、翻译的介词结构、写作的高分词块都直接受益。',
            'keywords': ['高频词组', f'第 {idx} 组', '固定搭配'],
            'priority': '○', 'tags': [], 'exam_types': ['词汇'],
            'spoken': f'第 {idx} 组高频词组，共 {len(chunk)} 条。',
            'units': units,
            'listen': _listen(cards[0]['card_id'], '词汇', f'{len(chunk)} 条高频搭配。'),
            'cards': cards, 'source': _src('204-phrases.jsonl', 'phrase'),
            'exam_evidence': dict(PENDING), 'tts': {'enabled': False},
        })
    return points


def confusable_card(pid: str, n: int, c: dict) -> dict:
    group = c.get('group') or []
    diff = c.get('diff') or c.get('answer') or ''
    return {
        'card_id': f'c{pid}-{n}', 'kind': '词汇', 'card_type': '辨析',
        'question': c.get('question') or f'辨析：{" 与 ".join(group)}',
        'front': c.get('question') or f'辨析：{" 与 ".join(group)}',
        'answer': diff, 'back': diff,
        'options': [], 'answer_points': [diff[:40] or '两词区别', f'组：{" / ".join(group)}'][:6],
        'analysis': f'辨析 {" / ".join(group)}：{diff} 考场先看搭配与词性，再看语义侧重。',
        'unit_refs': [n],
        'payload': {'type': 'confusable', 'group': group,
                    'stem': c.get('stem') or '', 'answer': c.get('answer') or '',
                    'diff': diff},
    }


def build_confusable_point(confs: list[dict]) -> list[dict]:
    if not confs:
        return []
    pid = '2041104'
    chunk = confs[:GROUP]
    units = [f'{" / ".join(c["group"])}：{(c.get("diff") or "")[:30]}' for c in chunk]
    cards = [confusable_card(pid, i, c) for i, c in enumerate(chunk, start=1)]
    return [{
        'id': pid, 'chapter': '204-11', 'order': 4,
        'point': '易混词辨析', 'title': '易混词辨析',
        'explain': f'{len(chunk)} 组形近或义近词，每组一张卡，正面给两个词，背面给一句话区别。',
        'exam': '完形的近义词辨析与写作的用词准确性都依赖这类区分。',
        'keywords': ['易混词', '近义词', '辨析'],
        'priority': '○', 'tags': [], 'exam_types': ['词汇'],
        'spoken': f'{len(chunk)} 组易混词辨析。',
        'units': units,
        'listen': _listen(cards[0]['card_id'], '词汇', f'{len(chunk)} 组易混词。'),
        'cards': cards, 'source': _src('204-confusable.jsonl', 'confusable'),
        'exam_evidence': dict(PENDING), 'tts': {'enabled': False},
    }]


def _chapter(cid: str, name: str, module: str, tier: int, weight: int,
             basis: str, entry_count: int) -> dict:
    return {'id': cid, 'name': name, 'module': module, 'tier': tier,
            'weight_center': weight, 'weight_range': None, 'weight_basis': basis,
            'entry_count': entry_count}


def assemble(meta_dir: pathlib.Path | None = None, now: str | None = None) -> dict:
    meta = pathlib.Path(meta_dir or ROOT / '知识点元数据')
    base = meta / 'subjects' / '204'
    read = lambda name: [json.loads(l) for l in (base / name).read_text(encoding='utf-8').splitlines()
                         if l.strip()] if (base / name).exists() else []
    entries = read('204-vocab.jsonl')
    phrases = read('204-phrases.jsonl')
    confs = read('204-confusable.jsonl')
    essays = json.loads((base / '204-essay-points.json').read_text(encoding='utf-8')) \
        if (base / '204-essay-points.json').exists() else []

    word_points = build_word_points(entries)
    phrase_points = build_phrase_points(phrases[:GROUP * 3])
    conf_points = build_confusable_point(confs)

    chapters, points = [], []
    for cid in ('204-08', '204-09'):
        doc = json.loads((base / 'chapters' / f'{cid}.json').read_text(encoding='utf-8'))
        ch = dict(doc['chapter'])
        own = [e for e in essays if e['chapter'] == cid]
        ch['entry_count'] = len(own)
        chapters.append(ch)
        points += own
    chapters.append(_chapter('204-10', '核心词汇（1500）', '词汇语法', 2, 30,
                             '词汇是各题型基础，不单独计分，分值计在阅读/翻译/写作内',
                             len(word_points)))
    chapters.append(_chapter('204-11', '高频词组与易混辨析', '词汇语法', 2, 20,
                             '搭配与辨析服务于完形、翻译与写作表达',
                             len(phrase_points) + len(conf_points)))
    points += word_points + phrase_points + conf_points

    doc = {
        'schema': 'ky-point/3.0', 'subject': '204', 'name': '英语（二）',
        'score': 100, 'status': 'draft',
        'generated_at': now or datetime.now(timezone.utc).isoformat(),
        'source_file': '204-vocab-list.jsonl / 204-essays.jsonl',
        'chapters': chapters, 'points': points,
    }
    (base / '204.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')

    manifest, parts = split_doc(doc)
    outdir = base / 'chapters'
    (outdir / '_manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for cid, chunk in parts.items():
        (outdir / f'{cid}.json').write_text(
            json.dumps(chunk, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return {'chapters': len(chapters), 'points': len(points),
            'cards': sum(len(p['cards']) for p in points)}


if __name__ == '__main__':
    print(assemble())
