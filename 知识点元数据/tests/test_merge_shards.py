#!/usr/bin/env python3
"""Task 21: 合并子代理卡片分片，校验并剔除非法卡。"""
import importlib.util
import json
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]


def card(ct, kind, q, ans, refs):
    return {
        'kind': kind, 'card_type': ct, 'question': q, 'answer': ans,
        'answer_points': ['要点一', '要点二'],
        'analysis': '答题结构：先定义再展开。得分点：概念准确、逻辑清楚。常见失分点：只写名称不解释。',
        'unit_refs': refs, 'difficulty': 2,
    }


def main():
    spec = importlib.util.spec_from_file_location(
        'merge_mod', ROOT / '知识点元数据/scripts/merge_card_shards.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    pts = {
        '8120201': {'units': ['u1', 'u2']},
        '8120202': {'units': ['u1']},
    }
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        shard = td / 'shard1.jsonl'
        good = {'id': '8120201', 'cards': [
            card('定义', '名解', '名词解释：水势', '水势是……', [1]),
            card('原理', '简答', '为什么水从高水势流向低水势？', '因为……', [1, 2]),
        ]}
        bad_card = card('定义', '名解', '名词解释：坏卡', '……', [1])
        del bad_card['card_type']
        bad = {'id': '8120202', 'cards': [bad_card, card('原理', '简答', 'q2', 'a2', [1])]}
        shard.write_text(json.dumps(good, ensure_ascii=False) + '\n' +
                         json.dumps(bad, ensure_ascii=False) + '\n', encoding='utf-8')
        out = td / 'out.jsonl'
        written, errors = m.merge(td, out, pts)
        assert written == 1, written
        assert any('8120202' in e for e in errors), errors
        rows = [json.loads(l) for l in out.read_text(encoding='utf-8').splitlines() if l.strip()]
        assert [r['id'] for r in rows] == ['8120201']
        assert rows[0]['cards'][0]['card_id'] == 'c8120201-1'
    print('merge shards ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAIL: {type(e).__name__}: {e}')
        raise SystemExit(1)
