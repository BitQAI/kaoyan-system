#!/usr/bin/env python3
"""Task 5: validate_v3 必须报出 E21/E22/E23/E26。"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'validate_mod', ROOT / '知识点元数据/scripts/validate.py')
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)

BAD = {"schema": "ky-point/3.0", "points": [{
    "id": "8120201", "chapter": "812-02", "order": 1,
    "point": "x", "title": "x", "explain": "x", "exam": "x",
    "keywords": ["a", "b", "c"], "priority": "★", "tags": [], "units": ["u1"],
    "source": {"kind": "html", "ref": "r", "file": "f", "section": "s"},
    "exam_evidence": {"level": "verified", "basis": "b", "sources": []},
    "cards": [{
        "card_id": "c8120201-1", "kind": "名解", "question": "q",
        "answer": "a", "analysis": "x" * 31, "front": "q", "back": "a",
        "point_id": "8120201",
    }],
}]}


def main():
    errors, warns = [], []
    v.validate_v3('812', BAD, errors, warns)
    codes = {e.split()[0] for e in errors}
    assert {'E21', 'E22', 'E23', 'E26'} <= codes, (codes, errors)
    print('validate v3 fixture ok:', sorted(codes))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAIL: {type(e).__name__}: {e}')
        sys.exit(1)
