#!/usr/bin/env python3
"""词条生成：释义/音标/易混/例句 + 真题出处回填。"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'enrich_mod', ROOT / '知识点元数据/scripts/vocab_enrich.py')
e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e)

CORPUS = [
    {"year": 2018, "part": "readingA", "text": "Text 2", "sent": 3,
     "en": "The move to renewables is picking up momentum around the world."},
    {"year": 2021, "part": "translation", "text": "", "sent": 1,
     "en": "Momentum keeps building as more cities adopt the policy."},
]


def fake_llm(word):
    return {
        "word": word,
        "phonetic": "/məˈmentəm/",
        "meanings": [{"pos": "n", "cn": "势头"}, {"pos": "", "cn": "  "}],
        "confusables": [{"word": "moment", "diff": "片刻"}],
        "phrases": [{"en": "gain momentum", "cn": "势头增强"}],
        "examples": [
            {"kind": "真题", "quote": "The move to renewables is picking up momentum around the world."},
            {"kind": "真题", "quote": "This sentence was rewritten and is not in the corpus."},
        ],
    }


def main():
    index = e.build_index(CORPUS)
    assert 'momentum' in index and len(index['momentum']) == 2

    assert e.verify_example("The move to renewables is picking up momentum around the world.", CORPUS)
    assert not e.verify_example("The move to renewables picks up momentum worldwide.", CORPUS)

    entry = e.normalize(fake_llm('momentum'))
    assert entry['meanings'] == [{"pos": "n.", "cn": "势头"}], entry['meanings']

    got = e.attach_occurrences(entry, index)
    real = [x for x in got['examples'] if x['kind'] == '真题']
    fake = [x for x in got['examples'] if x['kind'] == '例句']
    assert len(real) == 1 and real[0]['year'] == 2018, real
    assert real[0]['text'] == 'Text 2' and real[0]['part'] == 'readingA'
    assert len(fake) == 1 and fake[0]['note'] == '例句（非真题原句）', fake

    # 语料里没有该词：真题例句全部降级，且不重复
    got2 = e.attach_occurrences(e.normalize(fake_llm('momentum')), {})
    assert all(x['kind'] == '例句' for x in got2['examples'])
    assert len(got2['examples']) == 2
    print('vocab enrich ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FAIL: {type(exc).__name__}: {exc}')
        sys.exit(1)
