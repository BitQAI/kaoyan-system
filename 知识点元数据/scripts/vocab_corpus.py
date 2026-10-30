#!/usr/bin/env python3
"""真题 raw/ → sentences.jsonl + questions.jsonl（纯本地解析，不联网）。

raw/ 下每个文件由抓取阶段写入，格式见 research/204-sources.md：
头部 `# key: value`，空行后是正文，可选的 `## Questions` 之后是题目。
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
RAW = ROOT / '知识点元数据' / 'research' / '204-corpus' / 'raw'
OUT = RAW.parent

ABBR = ('Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.', 'St.', 'vs.', 'etc.', 'e.g.',
        'i.e.', 'U.S.', 'Jr.', 'Inc.', 'Co.', 'No.')
_SPLIT = re.compile(r'(?<=[.!?])\s+')
_OPTION = re.compile(r'^([A-D])[.、．]\s*(.+)$')


def parse_file(text: str):
    meta, body_lines, q_lines = {}, [], []
    target = body_lines
    for line in text.splitlines():
        if target is body_lines and line.startswith('# ') and ':' in line and not meta.get('_body'):
            k, v = line[2:].split(':', 1)
            meta[k.strip()] = v.strip()
            continue
        if line.strip() == '## Questions':
            target = q_lines
            meta['_body'] = True
            continue
        target.append(line)
    meta.pop('_body', None)
    for key in ('year',):
        if key in meta:
            meta[key] = int(meta[key])
    return meta, '\n'.join(body_lines).strip(), parse_questions(q_lines)


def parse_questions(lines: list[str]) -> list[dict]:
    out, cur = [], None
    for line in lines:
        s = line.strip()
        if not s:
            continue
        m = re.match(r'^(\d+)[.、]\s*(.+)$', s)
        if m:
            if cur:
                out.append(cur)
            cur = {'qno': int(m.group(1)), 'stem': m.group(2).strip(),
                   'options': [], 'answer': '', 'explain': ''}
            continue
        if cur is None:
            continue
        mo = _OPTION.match(s)
        if mo:
            cur['options'].append(mo.group(2).strip())
        elif s.lower().startswith('answer:'):
            cur['answer'] = s.split(':', 1)[1].strip()
        elif s.lower().startswith('explain:'):
            cur['explain'] = s.split(':', 1)[1].strip()
        else:
            cur['stem'] += ' ' + s
    if cur:
        out.append(cur)
    return out


def split_sentences(text: str) -> list[str]:
    flat = ' '.join(text.split())
    for a in ABBR:
        flat = flat.replace(a, a.replace('.', '\u0000'))
    parts = _SPLIT.split(flat)
    return [p.replace('\u0000', '.').strip() for p in parts if p.strip()]


def _text_no(part: str) -> str:
    m = re.match(r'^readingA-(\d)$', part or '')
    return f'Text {m.group(1)}' if m else ''


def build_rows(meta: dict, body: str, questions: list[dict]) -> dict:
    sentences = []
    para_no = 0
    for para in re.split(r'\n\s*\n', body):
        para = para.strip()
        if not para:
            continue
        para_no += 1
        for i, sent in enumerate(split_sentences(para), start=1):
            sentences.append({
                'year': meta.get('year'), 'part': meta.get('part'),
                'text': _text_no(meta.get('part')), 'para': para_no,
                'sent': i, 'en': sent, 'source': meta.get('source', ''),
            })
    qs = [{**q, 'year': meta.get('year'), 'part': meta.get('part'),
           'text': _text_no(meta.get('part'))} for q in questions]
    return {'sentences': sentences, 'questions': qs}


def merge(raw_dir: pathlib.Path = RAW, out_dir: pathlib.Path = OUT) -> dict:
    rows = {'sentences': [], 'questions': []}
    files = sorted(raw_dir.glob('*.txt'))
    for path in files:
        meta, body, questions = parse_file(path.read_text(encoding='utf-8'))
        if not meta.get('year') or not meta.get('part'):
            print(f'  跳过 {path.name}：缺 year/part')
            continue
        got = build_rows(meta, body, questions)
        rows['sentences'].extend(got['sentences'])
        rows['questions'].extend(got['questions'])
    for name, items in rows.items():
        out = out_dir / f'{name}.jsonl'
        with out.open('w', encoding='utf-8') as f:
            for r in items:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
    return {'files': len(files), 'sentences': len(rows['sentences']),
            'questions': len(rows['questions'])}


if __name__ == '__main__':
    raw = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else RAW
    print(merge(raw))
