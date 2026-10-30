#!/usr/bin/env python3
"""范文 JSON → 知识点：整篇朗读 / 回译 / 默写 / 句式迁移四类卡。"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'essay_mod', ROOT / '知识点元数据/scripts/essay_build.py')
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)

SAMPLE = {
    "id": "2040805", "chapter": "204-08", "type": "建议信",
    "title": "建议信：二选一（艺术展 / 机器人展）",
    "point": "建议信范文：二选一的理由展开",
    "paragraphs": [
        {"en": "Dear David, I am writing to suggest that you go to the art exhibition.",
         "cn": "我写信是想建议你去艺术展。"},
        {"en": "The exhibition offers a rare chance to engage with different cultures, and it is likely to be more memorable.",
         "cn": "展览提供接触不同文化的机会，也更难忘。"},
    ],
    "blanks": [
        {"para": 1, "en": "I am writing to ____ that you ____ to the art exhibition.",
         "answers": ["suggest", "go"]},
        {"para": 2, "en": "The exhibition offers a rare ____ to engage with different cultures, and it is ____ to be more memorable.",
         "answers": ["chance", "likely"]},
    ],
    "transfer": ["I am writing to suggest that… 换成 congratulate / apologize / complain 即改题型",
                 "is likely to be more… 比较句，图表作文可用"],
}


def main():
    points = b.build_points([SAMPLE])
    assert len(points) == 1
    p = points[0]
    assert p['id'] == '2040805' and p['chapter'] == '204-08'
    assert len(p['paragraphs']) == 2

    cards = p['cards']
    kinds = [c['kind'] for c in cards]
    # 1 整篇 + 2 回译 + 2 默写 + 1 句型
    assert kinds.count('模板') == 1 and kinds.count('回译') == 2
    assert kinds.count('默写') == 2 and kinds.count('句型') == 1
    assert [c['card_id'] for c in cards] == [f'c2040805-{i}' for i in range(1, 7)]

    for c in cards:
        assert len(c['analysis']) >= 30, c['card_id']
        assert 2 <= len(c['answer_points']) <= 6, c['card_id']
        assert c['unit_refs'] and all(1 <= r <= len(p['units']) for r in c['unit_refs'])
        assert c['front'] and c['back']

    cloze = [c for c in cards if c['kind'] == '默写']
    for c in cloze:
        assert c['question'].count('____') == len(c['answer_points']), c['card_id']

    assert p['exam_types'] == ['模板', '回译', '默写', '句型']
    assert p['listen']['card_id'] == 'c2040805-1'
    assert 'exhibition' in p['listen']['script'].lower() or p['listen']['script']
    print('essay build ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FAIL: {type(exc).__name__}: {exc}')
        sys.exit(1)
