#!/usr/bin/env python3
"""生成旧 point_id → 新 id 映射（mappings/legacy-point-map.json）。

只读 kaoyan-system/content/content.json，按**考点文本逐字匹配**对齐新旧数据。
用途：为后续新项目提供「旧数据去哪了」的追溯线索（不作为核心字段，不承担主键职责）。
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'
OLD = pathlib.Path('/Users/huajun/Sync/kaoyan-system/content/content.json')


def main():
    ext = json.loads((ROOT / '.build' / 'extract.json').read_text(encoding='utf-8'))
    new = []
    for s in ext['subjects']:
        for p in s['points']:
            new.append((s['id'], p['id'], p['point'], p['chapter']))

    old = []
    if OLD.exists():
        c = json.loads(OLD.read_text(encoding='utf-8'))
        for s in c['subjects']:
            for ch in s['chapters']:
                for p in ch['points']:
                    old.append((s['id'], p['id'], p['text'], ch['id']))

    by_text = {}
    for sid, nid, txt, ch in new:
        by_text.setdefault((sid, txt), []).append((nid, ch))

    mapping, ambiguous, unmapped, many_to_one = [], [], [], []
    for sid, oid, txt, och in old:
        hits = by_text.get((sid, txt), [])
        if len(hits) == 1:
            mapping.append({'legacy_id': oid, 'new_id': hits[0][0],
                            'chapter': hits[0][1], 'status': '一对一'})
        elif len(hits) > 1:
            ambiguous.append({'legacy_id': oid, 'text': txt, 'candidates': hits})
        else:
            unmapped.append({'legacy_id': oid, 'chapter': och, 'text': txt})

    # 新增（旧无对应）
    old_texts = {(sid, txt) for sid, _, txt, _ in old}
    added = [{'new_id': nid, 'chapter': ch, 'text': txt}
             for sid, nid, txt, ch in new if (sid, txt) not in old_texts]

    out = {
        'schema': 'ky-legacy-map/1.0',
        'note': '旧 content.json point_id → 新元数据 id；按考点文本逐字匹配。'
                '一对一 = 旧点在新数据中原样保留；新增 = 新数据有而旧数据没有。',
        'counts': {'legacy_total': len(old), 'new_total': len(new),
                   'one_to_one': len(mapping), 'legacy_unmapped': len(unmapped),
                   'ambiguous': len(ambiguous), 'new_added': len(added)},
        'one_to_one': mapping,
        'legacy_unmapped': unmapped,
        'ambiguous': ambiguous,
        'new_added': added,
    }
    p = META / 'mappings' / 'legacy-point-map.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    c = out['counts']
    print(f"  {p.relative_to(ROOT)}  {p.stat().st_size:,} bytes")
    print(f"  旧 {c['legacy_total']} · 新 {c['new_total']} · 一对一 {c['one_to_one']} · "
          f"旧无对应 {c['legacy_unmapped']} · 一对多歧义 {c['ambiguous']} · 新增 {c['new_added']}")
    if unmapped:
        print('  旧点无对应（前 8）:')
        for u in unmapped[:8]:
            print(f"    {u['legacy_id']}  {u['text'][:52]}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
