#!/usr/bin/env python3
"""按固定顺序跑完整条生成链，任何一步失败即中止并打印退出码。

    python3 scripts/pipeline.py            # 全流程
    python3 scripts/pipeline.py --check    # 只跑校验链（不重建 json）
    python3 scripts/pipeline.py --list     # 只列步骤

顺序（前置产物 → 派生层 → 机洗真源 → 校验）：
  1. build.py             md + units/cards/media 侧车 → <sid>.json，并按章写 chapters/
  2. inline_markers.py    SVG 里的 <marker> 箭头 → 内联三角形（幂等，无 marker 时零改动）
  3. split_subject.py     重建章节分片（build 已顺带做，此步保证单跑一致性）
  4. normalize_evidence.py 按统一口径复核 exam_evidence（只读报告）
  5. validate.py          E00–E27 校验
  6. audit_v3.py          原子度 / 覆盖率 / 重复设问
  7. check_locator.py     html 溯源逐字回溯
  8. 测试集               .build/sdd/812-v3/test_*.py
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / '知识点元数据/scripts'

BUILD = ['build.py', 'inline_markers.py', 'split_subject.py']
CHECK = ['split_subject.py --check', 'validate.py', 'audit_v3.py', 'check_locator.py',
         'normalize_evidence.py']
TESTS = ['test_schema_v3.py', 'test_validate_v3.py', 'test_build_v3.py',
         'test_audit_v3.py', 'test_merge_shards.py', 'test_finalize_v3.py']


def run(path, cwd=SCRIPTS):
    print(f'\n$ {path}')
    parts = path.split()
    argv = [sys.executable, str(cwd / parts[0])] + parts[1:]
    r = subprocess.run(argv, cwd=str(ROOT))
    if r.returncode != 0:
        print(f'失败：{path} 退出码 {r.returncode}')
        return False
    return True


def main(argv):
    steps = BUILD + CHECK
    if '--list' in argv:
        for s in steps:
            print(' ', s)
        return 0
    todo = CHECK if '--check' in argv else BUILD + CHECK
    for s in todo:
        if not run(s):
            return 1
    if '--check' not in argv:
        td = ROOT / '.build/sdd/812-v3'
        for t in TESTS:
            if (td / t).exists() and not run(t, td):
                return 1
    print('\n全部步骤通过')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
