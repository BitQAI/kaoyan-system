#!/usr/bin/env python3
"""Task 7: 来源台账与覆盖矩阵骨架必须存在且结构完整。"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RES = ROOT / '知识点元数据/research'


def main():
    src = RES / '812-sources.md'
    cov = RES / '812-coverage.md'
    assert src.exists(), '缺少 812-sources.md'
    assert cov.exists(), '缺少 812-coverage.md'
    s = src.read_text(encoding='utf-8')
    assert '| id | type | reliability | title | locator | url | accessed | note |' in s
    for sid in ('syl-812', 'book-taiz', 'book-wwh', 'book-lhs', 'book-wz', 'book-mzc'):
        assert re.search(rf'^\| {sid} \|', s, re.M), f'缺少来源 {sid}'
    c = cov.read_text(encoding='utf-8')
    assert '| 考纲条目 | 现有知识点 | 新增知识点 | 覆盖状态 | 缺口说明 |' in c
    assert '## 理解性补充 unit 清单' in c
    rows = re.findall(r'^\| ch\d{2}-\d+ \|', c, re.M)
    assert len(rows) >= 30, len(rows)
    print(f'research files ok: {len(rows)} coverage rows')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAIL: {type(e).__name__}: {e}')
        sys.exit(1)
