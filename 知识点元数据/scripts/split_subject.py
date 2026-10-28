#!/usr/bin/env python3
"""把 <sid>.json 按章拆成可单独阅读的分片，并校验可无损重组。

{subjace}.json 仍是唯一入口（应用与脚本都读它），分片只是同一份数据的按章视图：
每片含该章的 chapter 条目 + 落在该章的 points（含 cards / media），
单文件从 2–3 MB 降到 100–300 KB，便于阅读、审阅和逐章处理。

用法：
  python3 scripts/split_subject.py            # 生成分片
  python3 scripts/split_subject.py --check    # 只校验：分片能否无损重组回 <sid>.json
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SUBJ = ROOT / '知识点元数据/subjects'


def split_doc(doc):
    """→ (manifest, {chapter_id: chapter_doc})"""
    chapters = doc['chapters']
    by_ch = {c['id']: [] for c in chapters}
    orphan = []
    for p in doc['points']:
        if p.get('chapter') in by_ch:
            by_ch[p['chapter']].append(p)
        else:
            orphan.append(p)
    out = {}
    for c in chapters:
        out[c['id']] = {
            'schema': doc['schema'],
            'subject': doc['subject'],
            'name': doc['name'],
            'chapter': c,
            'points': by_ch[c['id']],
        }
    manifest = {
        'schema': doc['schema'],
        'subject': doc['subject'],
        'name': doc['name'],
        'score': doc.get('score'),
        'generated_at': doc.get('generated_at'),
        'source_file': doc.get('source_file'),
        'counts': {'chapters': len(chapters), 'points': len(doc['points'])},
        'chapters': [
            {'id': c['id'], 'name': c['name'], 'module': c.get('module'),
             'tier': c.get('tier'), 'points': len(by_ch[c['id']]),
             'file': f'{c["id"]}.json'}
            for c in chapters
        ],
        'orphan_points': orphan,
    }
    return manifest, out


def main(check):
    bad = 0
    for jf in sorted(SUBJ.glob('*/[0-9][0-9][0-9].json')):
        sid = jf.stem
        doc = json.loads(jf.read_text(encoding='utf-8'))
        manifest, parts = split_doc(doc)
        outdir = jf.parent / 'chapters'
        if check:
            if not (outdir / '_manifest.json').exists():
                print(f'{sid}: 缺少分片，未拆')
                bad += 1
                continue
            disk = json.loads((outdir / '_manifest.json').read_text(encoding='utf-8'))
            pts = []
            if disk != manifest:
                print(f'{sid}: manifest 与源不一致')
                bad += 1
            for cid in parts:
                pf = outdir / f'{cid}.json'
                if not pf.exists():
                    print(f'{sid}: 缺分片 {cid}')
                    bad += 1
                    continue
                if json.loads(pf.read_text(encoding='utf-8')) != parts[cid]:
                    print(f'{sid}: 分片 {cid} 与源不一致')
                    bad += 1
                pts += json.loads(pf.read_text(encoding='utf-8'))['points']
            pts += disk['orphan_points']
            if pts != doc['points']:
                print(f'{sid}: 重组后的 points 与源不一致')
                bad += 1
            else:
                print(f'OK {sid}: {len(parts)} 章 / {len(pts)} 点 可无损重组')
            continue
        outdir.mkdir(exist_ok=True)
        (outdir / '_manifest.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        for cid, chunk in parts.items():
            (outdir / f'{cid}.json').write_text(
                json.dumps(chunk, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        sizes = [len(json.dumps(c, ensure_ascii=False)) for c in parts.values()]
        print(f'{sid}: {len(parts)} 片，最大 {max(sizes)/1024:.0f} KB，'
              f'源 {jf.stat().st_size/1048576:.2f} MB')
    if check:
        print('不一致项', bad)
        return 1 if bad else 0
    return 0


if __name__ == '__main__':
    sys.exit(main('--check' in sys.argv))
