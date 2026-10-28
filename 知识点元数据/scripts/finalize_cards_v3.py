#!/usr/bin/env python3
"""把 812-cards-v3.jsonl 合并为正式 812-cards.jsonl。

赋值 card_id、生成 front/back、计算 exam_types、生成 listen（audio=pending）。
"""
import argparse
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'
PREF = ['简答', '名解', '论述']


def finalize(src, dst, points_json, allow_partial=False):
    src = pathlib.Path(src)
    dst = pathlib.Path(dst)
    pts = json.loads(pathlib.Path(points_json).read_text(encoding='utf-8'))['points']
    rows = {}
    for line in src.read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r['id']] = r
    if not allow_partial:
        missing = [p['id'] for p in pts if p['id'] not in rows]
        if missing:
            raise SystemExit(f'缺少卡片的知识点 {len(missing)} 个：{missing[:10]}')
        extra = sorted(set(rows) - {p['id'] for p in pts})
        if extra:
            raise SystemExit(f'卡片指向不存在的知识点：{extra[:10]}')

    out = []
    for p in pts:
        r = rows.get(p['id'])
        if not r:
            continue
        cards = r['cards']
        for i, c in enumerate(cards, 1):
            c['card_id'] = f"c{p['id']}-{i}"
            c['point_id'] = p['id']
            c['front'] = c.get('question', '')
            c['back'] = c.get('answer', '')
        kinds = []
        for c in cards:
            if c['kind'] not in kinds:
                kinds.append(c['kind'])
        pick = next((c for k in PREF for c in cards if c['kind'] == k), cards[0])
        listen = {
            'card_id': pick['card_id'],
            'kind': pick['kind'],
            'script': (f"设问：{pick['question']} 答案：{pick['answer']} "
                       f"解析：{pick['analysis']}"),
            'audio': 'pending',
        }
        out.append({'id': p['id'], 'cards': cards,
                    'exam_types': kinds, 'listen': listen})

    if dst.exists():
        shutil.copy2(dst, dst.with_suffix('.bak'))
    dst.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in out),
                   encoding='utf-8')
    return len(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=str(META / 'subjects/812/812-cards-v3.jsonl'))
    ap.add_argument('--dst', default=str(META / 'subjects/812/812-cards.jsonl'))
    ap.add_argument('--points', default=str(META / 'subjects/812/812.json'))
    ap.add_argument('--allow-partial', action='store_true')
    args = ap.parse_args()
    n = finalize(args.src, args.dst, args.points, args.allow_partial)
    print(f'finalize {n} points')
    if n == 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
