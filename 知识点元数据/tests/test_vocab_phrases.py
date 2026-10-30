#!/usr/bin/env python3
"""从词条聚合词组与易混辨析（不再额外调模型）。"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'phr_mod', ROOT / '知识点元数据/scripts/vocab_phrases.py')
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)

ENTRIES = [
    {"word": "adopt", "phrases": [{"en": "adopt a policy", "cn": "采纳政策"}],
     "confusables": [{"word": "adapt", "diff": "adapt 适应或改编，adopt 采纳或收养"}]},
    {"word": "adapt", "phrases": [{"en": "adapt to", "cn": "适应"}],
     "confusables": [{"word": "adopt", "diff": "adopt 采纳；adapt 侧重调整以适应"}]},
    {"word": "boost", "phrases": [{"en": "boost the economy", "cn": "提振经济"},
                                  {"en": "a boost to", "cn": "对…的推动"}],
     "confusables": [{"word": "boom", "diff": "boom 是繁荣本身，boost 是推动的动作"}]},
]

CORPUS = [
    {"en": "The government decided to adopt a policy on housing."},
    {"en": "Firms must adapt to the new rules quickly."},
    {"en": "A tax cut could boost the economy."},
]


def main():
    phrases = v.collect_phrases(ENTRIES, CORPUS, limit=3)
    assert [p['phrase'] for p in phrases] == ['adapt to', 'adopt a policy', 'boost the economy'], phrases
    assert all(p['hits'] == 1 for p in phrases), phrases
    assert phrases[1]['cn'] == '采纳政策'

    pairs = v.collect_confusables(ENTRIES, limit=5)
    first = pairs[0]
    assert set(first['group']) == {'adapt', 'adopt'}, first
    assert 'adapt' in first['diff'] and 'adopt' in first['diff']
    assert len(pairs) == 2, pairs  # adapt/adopt 互为一条；boost/boom 只有单向也算

    print('vocab phrases ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FAIL: {type(exc).__name__}: {exc}')
        sys.exit(1)
