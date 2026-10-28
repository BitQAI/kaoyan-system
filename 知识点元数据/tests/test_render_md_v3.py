#!/usr/bin/env python3
"""Task 4: render_md 输出必须包含知识点关联表。"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'render_mod', ROOT / '知识点元数据/scripts/render_md.py')
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)

SUB = {
    'id': '812', 'name': '植物生理学', 'score': 150, 'source_file': 'x.html',
    'chapters': [], 'points': [{
        'id': '8120201', 'chapter': '812-02', 'point': 'p', 'title': '',
        'explain': '', 'exam': '', 'keywords': [], 'priority': '★',
        'tags': [], 'source': {'ref': 'r'}, 'spoken': '',
    }],
}


def main():
    out = r.render_subject(SUB, {})
    assert 'schema: ky-point/2.0' in out, 'front matter schema 应为 2.0'
    assert '# 812 植物生理学 · 知识点关联表' in out, '缺少关联表标题'
    assert '| id | prerequisites | related | confusables | evidence |' in out
    assert '| 8120201 | — | — | — | — |' in out
    print('render_md meta table ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAIL: {type(e).__name__}: {e}')
        sys.exit(1)
