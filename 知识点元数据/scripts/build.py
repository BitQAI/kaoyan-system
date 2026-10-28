#!/usr/bin/env python3
"""各科 md（人审真源）→ json（机洗真源）。

派生层（units / cards / media）来自 sidecar 文件，由 enrich.py / gen_cards.py 产出；
本脚本负责合并并补齐确定性派生字段（spoken / tts）。
"""
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chem  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'
BUILD = ROOT / '.build'

POINT_COLS = ['id', 'chapter', 'point', 'title', 'explain', 'exam',
              'keywords', 'priority', 'tags', 'source', 'spoken']
CHAP_COLS = ['id', 'name', 'module', 'tier', 'weight_center',
             'weight_range', 'weight_basis', 'entry_count']
META_COLS = ['id', 'prerequisites', 'related', 'confusables', 'evidence']
ALLOWED_SCHEMAS = {'ky-point/2.0', 'ky-point/3.0'}


def front_matter(text):
    """解析 md 开头的 YAML front matter（只支持 key: value 单行）。"""
    if not text.startswith('---'):
        return {}
    out = {}
    for line in text.splitlines()[1:]:
        if line.strip() == '---':
            break
        if ':' in line:
            k, v = line.split(':', 1)
            out[k.strip()] = v.strip()
    return out


def split_row(line):
    """拆 markdown 表格行 → 单元格。禁用 | 于单元格内，故可直接 split。"""
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    return [c.strip() for c in s.split('|')]


def parse_md(text):
    """→ (chapters, points, assoc)；assoc 为知识点关联表，按 id 索引。"""
    chapters, points, assoc = [], [], {}
    mode = None
    for line in text.splitlines():
        if line.startswith('# '):
            if '章节表' in line:
                mode = 'chapter'
            elif '知识点表' in line:
                mode = 'point'
            elif '知识点关联表' in line:
                mode = 'meta'
            else:
                mode = None
            continue
        if not line.startswith('|'):
            continue
        cells = split_row(line)
        if cells and cells[0] in ('id',):
            continue
        if cells and all(set(c) <= set('-: ') for c in cells):
            continue          # 表格分隔行
        if mode == 'chapter' and len(cells) == len(CHAP_COLS):
            c = dict(zip(CHAP_COLS, cells))
            c['tier'] = int(c['tier'])
            c['weight_center'] = float(c['weight_center'])
            c['entry_count'] = int(c['entry_count'])
            c['weight_range'] = _range(c['weight_range'])
            chapters.append(c)
        elif mode == 'point' and len(cells) == len(POINT_COLS):
            p = dict(zip(POINT_COLS, cells))
            p['keywords'] = _arr(p['keywords'])
            p['tags'] = _arr(p['tags'])
            p['source'] = _src(p['source'])
            points.append(p)
        elif mode == 'meta' and len(cells) == len(META_COLS):
            assoc[cells[0]] = {
                'prerequisites': [] if cells[1] == '—' else _arr(cells[1]),
                'related': [] if cells[2] == '—' else _arr(cells[2]),
                'confusables': _json_cell(cells[3]),
                'exam_evidence': _json_cell(cells[4]),
            }
    return chapters, points, assoc


def _json_cell(v):
    if not v or v == '—':
        return None
    return json.loads(v)


def _range(v):
    if not v or v == '—':
        return None
    m = re.match(r'\[([\d.]+),([\d.]+)\]', v)
    return [float(m.group(1)), float(m.group(2))] if m else None


def _arr(v):
    if not v:
        return []
    v = v.strip('[]')
    return [x for x in v.split('/') if x]


def _src(v):
    """'ref;basis;file=…;section=…;outline=…' → dict"""
    if not v:
        return {}
    parts = v.split(';')
    out = {'ref': parts[0].strip()}
    for p in parts[1:]:
        p = p.strip()
        if not p:
            continue
        if p.startswith('outline='):
            out['outline'] = p[len('outline='):]
        elif p.startswith('file='):
            out['file'] = p[len('file='):]
        elif p.startswith('section='):
            out['section'] = p[len('section='):]
        elif 'basis' not in out:
            out['basis'] = p
    return out


def build():
    ext = json.loads((BUILD / 'extract.json').read_text(encoding='utf-8'))
    src_file = ext['source']['file']

    # 音频台账（实测）：clip_id → {path, bytes, dur_sec}
    audio_index, voice = {}, None
    am = META / 'mappings' / 'audio-manifest.json'
    if am.exists():
        man = json.loads(am.read_text(encoding='utf-8'))
        audio_index = man.get('clips', {})
        voice = man.get('voice')

    outs = []
    for sub in ext['subjects']:
        sid = sub['id']
        md_path = META / 'subjects' / sid / f'{sid}.md'
        if not md_path.exists():
            print(f'  跳过 {sid}：md 不存在')
            continue
        text = md_path.read_text(encoding='utf-8')
        fm = front_matter(text)
        schema = fm.get('schema', 'ky-point/2.0')
        if schema not in ALLOWED_SCHEMAS:
            schema = 'ky-point/2.0'
        chapters, points, assoc = parse_md(text)

        # 派生层 sidecar
        units_map = {}
        up = META / 'subjects' / sid / f'{sid}-units.jsonl'
        if up.exists():
            for line in up.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    r = json.loads(line)
                    units_map[r['id']] = r.get('units', [])
        media_map = {}
        mpath = META / 'subjects' / sid / f'{sid}-media.json'
        if mpath.exists():
            media_map = json.loads(mpath.read_text(encoding='utf-8'))
        cards = []
        point_meta = {}
        cp = META / 'subjects' / sid / f'{sid}-cards.jsonl'
        if cp.exists():
            for line in cp.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    r = json.loads(line)
                    pid = r.get('id')
                    point_meta[pid] = {
                        'listen': r.get('listen'),
                        'exam_types': r.get('exam_types'),
                    }
                    for c in r.get('cards', []):
                        c.setdefault('point_id', pid)
                        cards.append(c)

        cards_by_point = {}
        for c in cards:
            pid = c.get('point_id')
            cid = c.get('card_id') or f"c{pid}-{len(cards_by_point.get(pid, [])) + 1}"
            cards_by_point.setdefault(pid, []).append({**c, 'card_id': cid, 'point_id': pid})

        out_points = []
        order_counter = {}
        for p in points:
            order_counter[p['chapter']] = order_counter.get(p['chapter'], 0) + 1
            p['order'] = order_counter[p['chapter']]
            assoc_row = assoc.get(p['id'], {})
            sp = p.get('spoken') or chem.to_speech(p['point'], subject=sid)
            clips = chem.split_clips(sp)
            clip_objs = []
            for i, c in enumerate(clips):
                cid = p['id'] if len(clips) == 1 else f"{p['id']}-p{i + 1}"
                obj = {'clip_id': cid, 'text': c, 'est_sec': chem.est_seconds(c)}
                m = audio_index.get(cid)
                if m:
                    obj['file'] = m['path']
                    obj['bytes'] = m['bytes']
                    obj['dur_sec'] = m['dur_sec']
                clip_objs.append(obj)
            tts = {
                'enabled': True, 'max_chars': 220,
                'est_sec': chem.est_seconds(sp),
                'clips': clip_objs,
            }
            if voice:
                tts['voice'] = voice
            if tts['clips']:
                meas = [c['dur_sec'] for c in tts['clips'] if 'dur_sec' in c]
                if meas:
                    tts['measured_sec'] = round(sum(meas), 1)
            pcards = cards_by_point.get(p['id'], [])
            meta = point_meta.get(p['id']) or {}
            exam_types = meta.get('exam_types') or []
            if not exam_types:
                for c in pcards:
                    if c.get('kind') and c['kind'] not in exam_types:
                        exam_types.append(c['kind'])
            src_obj = {**p['source']}
            src_obj.setdefault('file', src_file)
            src_obj.setdefault('section', src_obj['ref'].split('#')[0])
            o = {
                'id': p['id'],
                'chapter': p['chapter'],
                'point': p['point'],
                'title': p['title'],
                'explain': p['explain'],
                'exam': p['exam'],
                'keywords': p['keywords'],
                'priority': p['priority'],
                'tags': p['tags'],
                'source': src_obj,
                'spoken': sp,
                'tts': tts,
                'units': units_map.get(p['id'], []),
                'exam_types': exam_types,
                'listen': meta.get('listen'),
                'cards': pcards,
            }
            if schema == 'ky-point/3.0':
                ref = src_obj.get('ref') or ''
                src_obj.setdefault(
                    'kind',
                    'syllabus' if ref.startswith('syllabus:')
                    else ('research' if ref.startswith('research:') else 'html'))
                o.update({
                    'order': p['order'],
                    'prerequisites': assoc_row.get('prerequisites', []),
                    'related': assoc_row.get('related', []),
                    'confusables': assoc_row.get('confusables', []) or [],
                    'exam_evidence': assoc_row.get('exam_evidence'),
                })
            if media_map.get(p['id']):
                o['media'] = media_map[p['id']]
            out_points.append(o)

        doc = {
            'schema': schema,
            'subject': sid,
            'name': sub['name'],
            'score': sub['score'],
            'status': 'draft',
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_file': src_file,
            'chapters': chapters,
            'points': out_points,
        }
        op = META / 'subjects' / sid / f'{sid}.json'
        op.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
        n_units = sum(len(p['units']) for p in out_points)
        n_cards = sum(len(p['cards']) for p in out_points)
        print(f"  {op.relative_to(ROOT)}  {op.stat().st_size:,} bytes  "
              f"章 {len(chapters)} · 点 {len(out_points)} · unit {n_units} · card {n_cards}")
        outs.append(op)
    return outs


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只解析 md，不写 json')
    args = ap.parse_args()
    if args.check:
        for sid in ['812', '315', '101', '204']:
            mp = META / 'subjects' / sid / f'{sid}.md'
            if not mp.exists():
                continue
            t = mp.read_text(encoding='utf-8')
            ch, pts, assoc = parse_md(t)
            print(f'{sid}: 章 {len(ch)} · 点 {len(pts)} · 关联行 {len(assoc)} · '
                  f'schema {front_matter(t).get("schema")}')
    else:
        build()
