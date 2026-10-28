#!/usr/bin/env python3
"""Task 3: front matter / 关联表 / source.file 覆盖的解析测试。"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'build_mod', ROOT / '知识点元数据/scripts/build.py')
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)

MD = '''---
schema: ky-point/3.0
---

# 812 · 章节表

| id | name | module | tier | weight_center | weight_range | weight_basis | entry_count |
|---|---|---|---|---|---|---|---|
| 812-02 | 第二章 | 植物生理学 | 1 | 10 | [8,12] | 推算 | 2 |

# 812 · 知识点表

| id | chapter | point | title | explain | exam | keywords | priority | tags | source | spoken |
|---|---|---|---|---|---|---|---|---|---|---|
| 8120201 | 812-02 | p1 | t1 | e1 | x1 | [a/b] | ★ | [] | p4#c/p[0]/split[0];basis | |
| 8120202 | 812-02 | p2 | t2 | e2 | x2 | [c/d] | ○ | [] | p4#c/p[0]/split[1];basis | |

# 812 · 知识点关联表

| id | prerequisites | related | confusables | evidence |
|---|---|---|---|---|
| 8120201 | — | 8120202 | [{"name":"A","point_id":"8120202","distinction":"d"}] | {"level":"verified","basis":"b","sources":[{"id":"syl-812-ch02"}]} |
| 8120202 | 8120201 | — | — | {"level":"pending","basis":"b","sources":[]} |
'''


def main():
    fm = b.front_matter(MD)
    assert fm['schema'] == 'ky-point/3.0', fm
    ch, pts, assoc = b.parse_md(MD)
    assert len(ch) == 1 and len(pts) == 2 and len(assoc) == 2
    assert assoc['8120201']['confusables'][0]['name'] == 'A'
    assert assoc['8120201']['exam_evidence']['level'] == 'verified'
    assert assoc['8120202']['prerequisites'] == ['8120201']
    assert assoc['8120201']['related'] == ['8120202']
    s = b._src('syllabus:812#ch02;basis;file=考纲.pdf;section=第二章')
    assert s['file'] == '考纲.pdf'
    assert s['section'] == '第二章'
    assert s['basis'] == 'basis'
    print('build v3 parse ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAIL: {type(e).__name__}: {e}')
        sys.exit(1)
