#!/usr/bin/env python3
"""合并子代理产出的卡片分片，校验后写入 812-cards-v3.jsonl。

分片格式：每行 {"id":"8120201","cards":[...]}
用法：python3 scripts/merge_card_shards.py --shards .build/sdd/812-v3/cards
"""
import argparse
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'
KINDS = {'名解', '简答', '论述'}
CARD_TYPES = {'定义', '原理', '条件', '公式', '过程', '辨析', '应用', '易错', '记忆'}


def norm(s):
    return re.sub(r'\s+', '', s or '')


def validate_point(pid, cards, n_units):
    errs = []
    if not isinstance(cards, list) or len(cards) < 2:
        return ['cards < 2']
    kinds, qs = set(), set()
    for i, c in enumerate(cards, 1):
        tag = f'card{i}'
        if c.get('kind') not in KINDS:
            errs.append(f'{tag} kind 非法 {c.get("kind")!r}')
        if c.get('card_type') not in CARD_TYPES:
            errs.append(f'{tag} card_type 非法 {c.get("card_type")!r}')
        for f in ('question', 'answer', 'analysis'):
            if not (c.get(f) or '').strip():
                errs.append(f'{tag} 缺 {f}')
        if len(c.get('analysis') or '') < 40:
            errs.append(f'{tag} analysis < 40')
        ap = c.get('answer_points')
        if not isinstance(ap, list) or not (2 <= len(ap) <= 6):
            errs.append(f'{tag} answer_points 非 2–6 条')
        elif any(len(x) > 40 for x in ap):
            errs.append(f'{tag} answer_points 有超 40 字项')
        refs = c.get('unit_refs')
        if not isinstance(refs, list) or not refs or len(refs) > 3:
            errs.append(f'{tag} unit_refs 非 1–3 个')
        elif any(not isinstance(r, int) or not (1 <= r <= n_units) for r in refs):
            errs.append(f'{tag} unit_refs 越界 (units={n_units})')
        q = norm(c.get('question'))
        if q in qs:
            errs.append(f'{tag} 点内重复设问')
        qs.add(q)
        kinds.add(c.get('kind'))
    if not {'名解', '简答'} <= kinds:
        errs.append('缺名解或简答')
    return errs


def merge(shard_dir, out_path, points):
    rows, errors = {}, []
    for f in sorted(pathlib.Path(shard_dir).glob('*.jsonl')):
        for line in f.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f'{f.name}: JSON 解析失败 {e}')
                continue
            pid = obj.get('id')
            if pid not in points:
                errors.append(f'{f.name}: 未知知识点 {pid}')
                continue
            errs = validate_point(pid, obj.get('cards'), len(points[pid].get('units') or []))
            if errs:
                errors.append(f'{pid}: ' + '; '.join(errs))
                continue
            if pid in rows:
                errors.append(f'{pid}: 多个分片重复，保留后一个')
            rows[pid] = {'id': pid, 'cards': obj['cards']}

    all_q = collections.Counter(
        norm(c.get('question')) for r in rows.values() for c in r['cards'])
    for q, n in all_q.items():
        if q and n > 1:
            errors.append(f'跨点重复设问 {q[:30]}… ×{n}')

    out = []
    for pid in sorted(rows):
        cards = rows[pid]['cards']
        for i, c in enumerate(cards, 1):
            c['card_id'] = f'c{pid}-{i}'
            c['point_id'] = pid
            c['front'] = c.get('question', '')
            c['back'] = c.get('answer', '')
        out.append({'id': pid, 'cards': cards})
    out_path.write_text(
        ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in out), encoding='utf-8')
    return len(out), errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shards', default=str(ROOT / '.build/sdd/812-v3/cards'))
    ap.add_argument('--out', default=str(META / 'subjects/812/812-cards-v3.jsonl'))
    args = ap.parse_args()
    d = json.loads((META / 'subjects/812/812.json').read_text(encoding='utf-8'))
    points = {p['id']: p for p in d['points']}
    written, errors = merge(args.shards, pathlib.Path(args.out), points)
    print(f'合并 {written} 点')
    if errors:
        print(f'问题 {len(errors)} 条：')
        for e in errors[:40]:
            print('  ', e)
        sys.exit(1 if written == 0 else 0)


if __name__ == '__main__':
    main()
