#!/usr/bin/env python3
"""把 知识点元数据/subjects/*/*.json 导入 SQLite。

用法：
    backend/.venv/bin/python backend/scripts/import_meta.py [--db data/ky.db]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db, importer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(config.DB_PATH))
    parser.add_argument("--meta", default=str(config.META_DIR))
    args = parser.parse_args()

    conn = db.connect(args.db)
    db.create_tables(conn)
    got = importer.import_all(conn, Path(args.meta))
    want = importer.expected_counts(Path(args.meta))
    conn.close()

    bad = 0
    print(f"{'表':<12}{'导入':>8}{'期望':>8}")
    for key in ("subject", "chapter", "point", "unit", "card", "media",
                "relation", "point_fts", "card_fts"):
        mark = "" if got[key] == want[key] else "  ← 不一致"
        if got[key] != want[key]:
            bad += 1
        print(f"{key:<12}{got[key]:>8}{want[key]:>8}{mark}")
    if bad:
        print(f"\n{bad} 张表与源不一致", file=sys.stderr)
        return 1
    print(f"\n导入完成：{args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
