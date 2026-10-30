#!/usr/bin/env python3
"""词频选词：sentences.jsonl → 1500 词表。"""
import importlib.util
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'pick_mod', ROOT / '知识点元数据/scripts/vocab_pick.py')
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)

ROWS = [
    {"year": 2018, "en": "The momentum of renewables is clear."},
    {"year": 2019, "en": "Momentum keeps building as renewables grow."},
    {"year": 2020, "en": "The of and to in it."},
]


def main():
    path = pathlib.Path(tempfile.mkdtemp()) / "s.jsonl"
    path.write_text('\n'.join(__import__('json').dumps(r) for r in ROWS),
                    encoding='utf-8')
    got = v.pick(path, limit=10, min_freq=2, basic=set())
    words = [r['word'] for r in got]
    assert words[0] == 'momentum', words
    assert 'renewables' in words
    assert 'the' not in words and 'of' not in words, words
    assert all(r['in_corpus'] is True for r in got)
    assert got[0]['years'] == [2018, 2019]

    # 语料不足时用补充词表填满，并标 in_corpus=False
    filled = v.pick(path, limit=10, min_freq=2, basic=set(),
                     supplemental=['abandon', 'benefit'])
    tail = [r for r in filled if not r['in_corpus']]
    assert [r['word'] for r in tail] == ['abandon', 'benefit'], tail
    assert len(filled) == len(got) + 2
    # 中学基础词即使语料高频也要排除
    filtered = v.pick(path, limit=10, min_freq=2, basic={'momentum'})
    assert 'momentum' not in [r['word'] for r in filtered], filtered
    print('vocab pick ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAIL: {type(e).__name__}: {e}')
        sys.exit(1)
