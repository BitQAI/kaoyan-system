#!/usr/bin/env python3
"""Task 5: audit_v3 必须产出 research/812-audit.md 并报告重复设问。"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    spec = importlib.util.spec_from_file_location(
        'audit_mod', ROOT / '知识点元数据/scripts/audit_v3.py')
    a = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(a)
    a.audit('812')
    out = ROOT / '知识点元数据/research/812-audit.md'
    assert out.exists(), '未生成 812-audit.md'
    text = out.read_text(encoding='utf-8')
    assert '# 812 v3 质量审计' in text
    assert '重复设问' in text
    assert 'unit 覆盖' in text
    print('audit v3 ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAIL: {type(e).__name__}: {e}')
        sys.exit(1)
