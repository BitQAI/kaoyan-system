#!/usr/bin/env python3
"""真题目录 → sentences.jsonl / questions.jsonl。"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'corpus_mod', ROOT / '知识点元数据/scripts/vocab_corpus.py')
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)

SAMPLE = """# year: 2018
# part: readingA-2
# source: https://example.com/x
# verified: yes

While fossil fuels still generate most of the world's energy, the future belongs to
renewable sources. The cost of solar panels has dropped by 80 percent. Is that enough?

## Questions
1. What does the author suggest?
   A. Fossil fuels will last.
   B. Renewables are the future.
   C. Prices are rising.
   D. Nothing will change.
   Answer: B
   Explain: 首句对比即可看出。
"""


def main():
    meta, body, questions = c.parse_file(SAMPLE)
    assert meta == {'year': 2018, 'part': 'readingA-2',
                    'source': 'https://example.com/x', 'verified': 'yes'}
    assert 'renewable sources' in body
    assert '## Questions' not in body

    sents = c.split_sentences(body)
    assert len(sents) == 3, sents
    assert sents[1].startswith('The cost of solar panels')
    assert sents[2].endswith('?')

    assert len(questions) == 1
    q = questions[0]
    assert q['qno'] == 1
    assert q['answer'] == 'B'
    assert q['options'][1] == 'Renewables are the future.'
    assert q['stem'] == 'What does the author suggest?'

    rows = c.build_rows(meta, body, questions)
    assert rows['sentences'][0]['part'] == 'readingA-2'
    assert rows['sentences'][0]['text'] == 'Text 2'
    assert rows['sentences'][0]['sent'] == 1
    assert rows['questions'][0]['year'] == 2018

    # 缩写与小数不能切开
    assert len(c.split_sentences('Dr. Smith spent 3.5 hours there. Then he left.')) == 2
    print('corpus parser ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAIL: {type(e).__name__}: {e}')
        sys.exit(1)
