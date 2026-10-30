#!/usr/bin/env python3
"""给缺中文的例句补译文（只翻译，不改英文，不参与朗读）。"""
import json
import pathlib
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import vocab_enrich as ve  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
VOCAB = ROOT / '知识点元数据' / 'subjects' / '204' / '204-vocab.jsonl'

PROMPT = ('把下面这句考研英语真题句子翻译成自然、准确的中文，只输出 JSON：'
          '{{"cn": "译文"}}，不要解释。\n\n句子：{en}')


def missing(entry: dict) -> list[int]:
    return [i for i, ex in enumerate(entry.get('examples') or []) if not ex.get('cn')]


def translate(text: str, call=ve.call_llm) -> str:
    raw = call([{'role': 'user', 'content': PROMPT.format(en=text)}], max_tokens=600)
    if not isinstance(raw, dict):
        return ''
    cn = (raw.get('cn') or '').strip()
    return cn if cn and not re.search(r'[A-Za-z]{4,}', cn) else cn


def main():
    limit = None
    for arg in sys.argv[1:]:
        if arg.startswith('--limit='):
            limit = int(arg.split('=', 1)[1])
    rows = [json.loads(l) for l in VOCAB.read_text(encoding='utf-8').splitlines() if l.strip()]
    lock = threading.Lock()
    todo = [(i, j) for i, r in enumerate(rows) for j in missing(r)]
    if limit:
        todo = todo[:limit]
    print(f'待翻译 {len(todo)} 条', flush=True)

    def one(pair):
        i, j = pair
        ex = rows[i]['examples'][j]
        cn = translate(ex['quote'])
        if not cn:
            print(f'  ! 失败 {rows[i]["word"]}', flush=True)
            return
        with lock:
            ex['cn'] = cn
            done = sum(1 for r in rows for e in (r.get('examples') or []) if e.get('cn'))
            if done % 50 == 0:
                flush(rows)
                print(f'  已补 {done}', flush=True)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(one, todo))
    flush(rows)
    left = sum(1 for r in rows for e in (r.get('examples') or []) if not e.get('cn'))
    print(f'完成，仍缺 {left} 条')


def flush(rows):
    VOCAB.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                     encoding='utf-8')


if __name__ == '__main__':
    main()
