#!/usr/bin/env python3
"""词条生成：Llama 写释义/音标/易混/例句，真题出处由本地语料回填。

纪律：卡片上标“真题”的例句必须能在 sentences.jsonl 里精确命中；命不中的
一律降级为自写例句并加 note，避免把仿写句冒充真题。
"""
import json
import pathlib
import re
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import llm  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
META = ROOT / '知识点元数据'
SENTENCES = META / 'research' / '204-corpus' / 'sentences.jsonl'
WORD_LIST = META / 'subjects' / '204' / '204-vocab-list.jsonl'
OUT = META / 'subjects' / '204' / '204-vocab.jsonl'

NOTE = '例句（非真题原句）'
TOKEN = re.compile(r"[A-Za-z][A-Za-z'-]+")

PROMPT = """你在为考研英语（二）词卡准备数据。目标词：{word}

只输出一个 JSON 对象，不要解释。字段：
- word：原词
- phonetic：英式或美式音标，/.../
- meanings：[{{"pos": "n.", "cn": "中文释义"}}]，1-3 个义项，词性带点号
- confusables：[{{"word": "易混或近义词", "diff": "一句话区别"}}]，0-3 组，必须同词性或确实形近
- phrases：[{{"en": "常见搭配", "cn": "中文"}}]，0-3 组，只放该词真实高频搭配
- examples：[{{"kind": "例句", "quote": "英文例句", "cn": "中文翻译"}}]，1-2 条，句子难度与考研真题相当

要求：释义准确；confusables 宁缺毋滥；例句英文地道、不超 25 词。"""


def _norm_sent(s: str) -> str:
    return ' '.join((s or '').split()).strip().lower()


def build_index(rows: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, set] = defaultdict(set)
    for r in rows:
        en = r.get('en') or ''
        if re.search(r'\s\d{1,2}\s', en):
            continue  # 完形设空处的编号，去掉这些句子免得例句带空
        for tok in TOKEN.findall(en):
            w = tok.lower().strip("-'")
            if len(w) < 3:
                continue
            key = _norm_sent(en)
            if key in seen[w]:
                continue
            seen[w].add(key)
            index[w].append(r)
    return dict(index)


def verify_example(quote: str, corpus_rows: list[dict]) -> bool:
    q = _norm_sent(quote)
    return any(q and q == _norm_sent(r.get('en')) for r in corpus_rows)


def normalize(raw: dict) -> dict:
    meanings = []
    for m in raw.get('meanings') or []:
        pos = (m.get('pos') or '').strip()
        cn = (m.get('cn') or '').strip()
        if not cn:
            continue
        if pos and not pos.endswith('.'):
            pos += '.'
        meanings.append({'pos': pos, 'cn': cn})
    confusables = [{'word': c['word'].strip(), 'diff': (c.get('diff') or '').strip()}
                   for c in raw.get('confusables') or []
                   if (c.get('word') or '').strip() and (c.get('diff') or '').strip()]
    phrases = [{'en': p['en'].strip(), 'cn': (p.get('cn') or '').strip()}
               for p in raw.get('phrases') or [] if (p.get('en') or '').strip()]
    examples = []
    for x in raw.get('examples') or []:
        quote = (x.get('quote') or '').strip()
        if not quote:
            continue
        ex = {'kind': '真题' if x.get('kind') == '真题' else '例句', 'quote': quote}
        if x.get('cn'):
            ex['cn'] = x['cn'].strip()
        examples.append(ex)
    return {
        'word': (raw.get('word') or '').strip(),
        'phonetic': (raw.get('phonetic') or '').strip(),
        'meanings': meanings,
        'confusables': confusables,
        'phrases': phrases,
        'examples': examples,
    }


def pick_occurrence(hits: list[dict], word: str) -> dict | None:
    """从语料命中里挑一条最适合展示的：小写、长度适中、不要专有名词里的人名机构名。"""
    best, best_score = None, -1
    for h in hits:
        en = h.get('en') or ''
        i = en.lower().find(word.lower())
        if i < 0:
            continue
        n = len(en.split())
        score = 0
        if i > 0 and en[i].islower():
            score += 2
        if 8 <= n <= 30:
            score += 2
        if n > 45:
            score -= 2
        if score > best_score:
            best, best_score = h, score
    return best


def attach_occurrences(entry: dict, index: dict[str, list[dict]]) -> dict:
    """把例句与语料对上：命中就补年份/题型/原文编号，命不中的降级为自写例句。"""
    hits = index.get(entry['word'].lower(), [])
    by_sent = {_norm_sent(h['en']): h for h in hits}
    out, used = [], set()
    for ex in entry['examples']:
        hit = by_sent.get(_norm_sent(ex['quote'])) if ex['kind'] == '真题' else None
        if hit is None:
            demoted = {'kind': '例句', 'quote': ex['quote'], 'note': NOTE}
            if ex.get('cn'):
                demoted['cn'] = ex['cn']
            out.append(demoted)
            continue
        key = _norm_sent(hit['en'])
        if key in used:
            continue
        used.add(key)
        ex = dict(ex)
        ex.update({'kind': '真题', 'year': hit.get('year'),
                   'part': hit.get('part') or '', 'text': hit.get('text') or ''})
        out.append(ex)

    # 模型没给够真题句时，从语料里补一条最适合展示的真实原句
    if not any(x['kind'] == '真题' for x in out):
        h = pick_occurrence(hits, entry['word'])
        if h is not None:
            out.insert(0, {'kind': '真题', 'quote': h['en'].strip(),
                           'year': h.get('year'), 'part': h.get('part') or '',
                           'text': h.get('text') or ''})
    entry['examples'] = out
    return entry


def enrich(word: str, call=llm.call_llm) -> dict | None:
    raw = call([{'role': 'user', 'content': PROMPT.format(word=word)}], max_tokens=2500)
    if not isinstance(raw, dict):
        return None
    return normalize({**raw, 'word': raw.get('word') or word})


def main(limit: int | None = None, workers: int = 4):
    rows = [json.loads(l) for l in SENTENCES.read_text(encoding='utf-8').splitlines() if l.strip()]
    index = build_index(rows)
    words = [json.loads(l) for l in WORD_LIST.read_text(encoding='utf-8').splitlines() if l.strip()]
    done: dict[str, dict] = {}
    if OUT.exists():
        for line in OUT.read_text(encoding='utf-8').splitlines():
            if line.strip():
                row = json.loads(line)
                done[row['word']] = row
    todo = [w['word'] for w in words if w['word'] not in done]
    if limit:
        todo = todo[:limit]
    lock = threading.Lock()
    order = [w['word'] for w in words]

    def flush():
        with OUT.open('w', encoding='utf-8') as f:
            for w in order:
                if w in done:
                    f.write(json.dumps(done[w], ensure_ascii=False) + '\n')

    def one(word):
        entry = enrich(word)
        if entry is None:
            print(f'  ! 生成失败，跳过 {word}', flush=True)
            return
        with lock:
            done[word] = attach_occurrences(entry, index)
            if len(done) % 25 == 0:
                flush()
                print(f'  {len(done)}/{len(order)}', flush=True)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        list(pool.map(one, todo))
    flush()
    print(f'写出 {OUT.relative_to(ROOT)}：{len(done)} 词')


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=None, help='只生成前 N 个未处理的词')
    ap.add_argument('--workers', type=int, default=4, help='并发数')
    args = ap.parse_args()
    main(args.limit, args.workers)
