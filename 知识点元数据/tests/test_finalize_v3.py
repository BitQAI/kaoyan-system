#!/usr/bin/env python3
"""Task 22: finalize 赋 card_id、exam_types、listen。"""
import importlib.util
import json
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]


def card(kind, q):
    return {
        'kind': kind, 'card_type': '定义', 'question': q, 'answer': '答案',
        'answer_points': ['要点一', '要点二'],
        'analysis': '答题结构：先定义再展开。得分点：概念准确。常见失分点：只写名称。',
        'unit_refs': [1], 'front': q, 'back': '答案',
    }


def main():
    spec = importlib.util.spec_from_file_location(
        'fin_mod', ROOT / '知识点元数据/scripts/finalize_cards_v3.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        pts = td / 'pts.json'
        pts.write_text(json.dumps({'points': [{'id': '8120201', 'units': ['u1']}]},
                                  ensure_ascii=False), encoding='utf-8')
        src = td / 'cards-v3.jsonl'
        src.write_text(json.dumps({'id': '8120201', 'cards': [
            card('名解', '名词解释：水势'), card('简答', '简述水势的组成')]},
            ensure_ascii=False) + '\n', encoding='utf-8')
        dst = td / 'cards.jsonl'
        n = m.finalize(src, dst, pts, allow_partial=True)
        assert n == 1
        row = json.loads(dst.read_text(encoding='utf-8').splitlines()[0])
        assert row['exam_types'] == ['名解', '简答'], row['exam_types']
        assert row['listen']['card_id'] == 'c8120201-2', row['listen']
        assert row['listen']['audio'] == 'pending'
        assert row['cards'][0]['card_id'] == 'c8120201-1'
    print('finalize v3 ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAIL: {type(e).__name__}: {e}')
        raise SystemExit(1)
