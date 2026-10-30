#!/usr/bin/env python3
"""装配：词表 + 词条 + 词组 + 辨析 + 范文 → 204.json（幂等）。"""
import json
import pathlib
import tempfile
import importlib.util
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'asm_mod', ROOT / '知识点元数据/scripts/vocab_assemble.py')
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)

WORD = {
    "word": "momentum", "phonetic": "/məˈmentəm/",
    "meanings": [{"pos": "n.", "cn": "势头"}],
    "examples": [{"kind": "真题", "quote": "The move picked up momentum.", "year": 2018,
                  "part": "readingA", "text": "Text 2"},
                 {"kind": "例句", "quote": "The campaign gained momentum.",
                  "note": "例句（非真题原句）"}],
    "confusables": [{"word": "moment", "diff": "片刻"}],
    "phrases": [{"en": "gain momentum", "cn": "势头增强"}],
}


def fixture(tmp: pathlib.Path):
    (tmp / 'subjects/204/chapters').mkdir(parents=True)
    (tmp / 'subjects/204/204-vocab-list.jsonl').write_text(
        json.dumps({"word": "momentum", "freq": 5, "years": [2018]}) + '\n', encoding='utf-8')
    (tmp / 'subjects/204/204-vocab.jsonl').write_text(
        json.dumps(WORD, ensure_ascii=False) + '\n', encoding='utf-8')
    (tmp / 'subjects/204/204-phrases.jsonl').write_text(
        json.dumps({"phrase": "pick up momentum", "cn": "势头增强", "hits": 2}) + '\n',
        encoding='utf-8')
    (tmp / 'subjects/204/204-confusable.jsonl').write_text(
        json.dumps({"group": ["adopt", "adapt"], "question": "辨析：adopt 与 adapt",
                    "answer": "adopt 采纳；adapt 适应", "diff": "adopt 采纳；adapt 适应"},
                   ensure_ascii=False) + '\n', encoding='utf-8')
    (tmp / 'subjects/204/204-essay-points.json').write_text(json.dumps([{
        "id": "2040805", "chapter": "204-08", "order": 1, "point": "p", "title": "t",
        "explain": "e", "exam": "x", "keywords": ["a", "b", "c"], "priority": "★",
        "tags": [], "exam_types": ["模板"], "spoken": "s", "units": ["u"],
        "listen": {"card_id": "c2040805-1", "kind": "模板", "script": "s", "audio": "pending"},
        "cards": [], "source": {"ref": "r", "file": "f", "section": "s", "basis": "b", "kind": "md"},
    }], ensure_ascii=False), encoding='utf-8')
    for cid, name in (("204-08", "写作 A（应用文）"), ("204-09", "写作 B（短文）")):
        (tmp / 'subjects/204/chapters' / f'{cid}.json').write_text(json.dumps({
            "schema": "ky-point/3.0", "subject": "204", "name": name,
            "chapter": {"id": cid, "name": name, "module": cid[-2:], "tier": 2,
                        "weight_center": 10, "weight_range": None,
                        "weight_basis": "人工估计", "entry_count": 0},
            "points": [],
        }, ensure_ascii=False), encoding='utf-8')


def main():
    tmp = pathlib.Path(tempfile.mkdtemp())
    fixture(tmp)
    counts = a.assemble(tmp, now="2026-10-30T00:00:00+00:00")
    doc = json.loads((tmp / 'subjects/204/204.json').read_text(encoding='utf-8'))
    ids = [p['id'] for p in doc['points']]
    assert '2041001' in ids and '2041101' in ids and '2041104' in ids, ids
    assert '2040805' in ids, ids  # 范文点并入 08 章

    word_point = next(p for p in doc['points'] if p['id'] == '2041001')
    assert len(word_point['cards']) == 1 and word_point['cards'][0]['kind'] == '词汇'
    card = word_point['cards'][0]
    assert card['payload']['type'] == 'word'
    assert card['unit_refs'] == [1]
    assert 2 <= len(card['answer_points']) <= 6
    assert len(card['analysis']) >= 30
    assert card['front'] and card['back']

    ch10 = next(c for c in doc['chapters'] if c['id'] == '204-10')
    assert ch10['entry_count'] == 1 and ch10['module'] == '词汇语法'
    ch08 = next(c for c in doc['chapters'] if c['id'] == '204-08')
    assert ch08['entry_count'] == 1

    before = (tmp / 'subjects/204/204.json').read_bytes()
    a.assemble(tmp, now="2026-10-30T00:00:00+00:00")
    after = (tmp / 'subjects/204/204.json').read_bytes()
    assert before == after, '装配必须幂等'
    assert counts['points'] == len(doc['points'])
    print('vocab assemble ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FAIL: {type(exc).__name__}: {exc}')
        sys.exit(1)
