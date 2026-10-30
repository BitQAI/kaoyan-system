#!/usr/bin/env python3
"""例句缺译文的判定（纯函数，不联网）。"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'tr_mod', ROOT / '知识点元数据/scripts/vocab_translate.py')
t = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t)


def main():
    entry = {"word": "momentum", "examples": [
        {"kind": "真题", "quote": "A"}, {"kind": "例句", "quote": "B", "cn": "乙"},
        {"kind": "例句", "quote": "C", "cn": ""}]}
    assert t.missing(entry) == [0, 2]
    assert t.missing({"word": "x"}) == []
    print('vocab translate ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FAIL: {type(exc).__name__}: {exc}')
        sys.exit(1)
