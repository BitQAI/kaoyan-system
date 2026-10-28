#!/usr/bin/env python3
"""为指定科目生成模板化知识结构图（概念/流程/清单/对比）。

用法：python3 scripts/gen_media_subjects.py 315 101 204
只重写 caption 以「· 对比图/流程图/清单图/知识结构图」结尾的条目，不动其他图示。
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_media_templates as G  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据/subjects'


def build_one(p):
    units = [u for u in (p.get('units') or []) if str(u).strip()]
    kw = p.get('keywords') or []
    kind = G.classify(p)
    if kind == 'compare':
        return G.compare_svg(p['title'], p['confusables'][0], units, kw), p['title'] + ' · 对比图'
    if kind == 'process':
        return G.process_svg(p['title'], units, kw), p['title'] + ' · 流程图'
    if kind == 'list':
        return G.list_svg(p['title'], units, kw), p['title'] + ' · 清单图'
    return G.concept_svg(p['title'], units, kw), p['title'] + ' · 知识结构图'


def main(sids):
    for sid in sids:
        doc = json.loads((META / sid / f'{sid}.json').read_text(encoding='utf-8'))
        mp = META / sid / f'{sid}-media.json'
        media = json.loads(mp.read_text(encoding='utf-8')) if mp.exists() else {}
        n = 0
        for p in doc['points']:
            items = media.get(p['id']) or []
            tpl = bool(items) and items[0].get('caption', '').endswith(G.TPL_SUFFIX)
            if items and not tpl:
                continue
            svg, cap = build_one(p)
            media[p['id']] = [{
                'kind': 'diagram', 'caption': cap,
                'alt': p['title'] + '；关键要点：' + '；'.join((p.get('units') or [])[:2]),
                'svg': svg,
            }]
            n += 1
        mp.write_text(json.dumps(media, ensure_ascii=False, indent=1), encoding='utf-8')
        print(sid, 'diagrams', n, 'total points with media', len(media))


if __name__ == '__main__':
    main(sys.argv[1:] or ['315', '101', '204'])
