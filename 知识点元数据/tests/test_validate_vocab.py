#!/usr/bin/env python3
"""词卡 payload 与默写卡空格校验（E28/E29）。"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'validate_mod', ROOT / '知识点元数据/scripts/validate.py')
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)

WORD_OK = {
    "card_id": "c2041001-1", "kind": "词汇",
    "payload": {"type": "word", "word": "momentum",
                "meanings": [{"pos": "n.", "cn": "势头"}],
                "examples": [{"kind": "例句", "quote": "x"}]},
}
WORD_NO_EXAMPLES = {
    "card_id": "c2041001-1", "kind": "词汇",
    "payload": {"type": "word", "word": "momentum",
                "meanings": [{"pos": "n.", "cn": "势头"}]},
}
CONFUSABLE_OK = {
    "card_id": "c2041104-1", "kind": "词汇",
    "payload": {"type": "confusable", "group": ["adapt", "adopt"],
                "stem": "x ____ y", "answer": "adopt", "diff": "d"},
}
CONFUSABLE_BAD = {
    "card_id": "c2041104-2", "kind": "词汇",
    "payload": {"type": "confusable", "group": ["adapt"]},
}
PHRASE_OK = {
    "card_id": "c2041101-1", "kind": "词汇",
    "payload": {"type": "phrase", "word": "account for",
                "meanings": [{"pos": "phr.", "cn": "占比"}]},
}
CLOZE_BAD = {
    "card_id": "c2040805-3", "kind": "默写",
    "question": "a ____ b ____ c", "answer_points": ["x", "y", "z"],
}
CLOZE_OK = {
    "card_id": "c2040805-4", "kind": "默写",
    "question": "a ____ b ____ c", "answer_points": ["x", "y"],
}


def codes(items):
    return {e.split()[0] for e in items}


def main():
    assert v.check_payload('204', '2041001', WORD_OK) == []
    assert 'E28' in codes(v.check_payload('204', '2041001', WORD_NO_EXAMPLES))
    assert v.check_payload('204', '2041104', CONFUSABLE_OK) == []
    assert 'E28' in codes(v.check_payload('204', '2041104', CONFUSABLE_BAD))
    assert v.check_payload('204', '2041101', PHRASE_OK) == []
    assert v.check_cloze('204', '2040805', CLOZE_BAD)
    assert v.check_cloze('204', '2040805', CLOZE_OK) == []
    print('validate vocab fixture ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAIL: {type(e).__name__}: {e}')
        sys.exit(1)
