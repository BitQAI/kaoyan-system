#!/usr/bin/env python3
"""Task 6: 考纲结构化文件必须 12 章、≥30 条、每行 3 列。"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / '知识点元数据/research/812-syllabus.md'


def main():
    assert P.exists(), '缺少 research/812-syllabus.md'
    t = P.read_text(encoding='utf-8')
    chs = re.findall(r'^## (ch\d{2})', t, re.M)
    rows = re.findall(r'^\| (ch\d{2}-\d+) \|', t, re.M)
    assert chs == [f'ch{i:02d}' for i in range(12)], chs
    assert len(rows) >= 30, len(rows)
    for line in t.splitlines():
        if re.match(r'^\| ch\d{2}-\d+ \|', line):
            assert line.count('|') == 4, f'列数不对: {line}'
    print(f'syllabus ok: {len(chs)} chapters, {len(rows)} clauses')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAIL: {type(e).__name__}: {e}')
        sys.exit(1)
