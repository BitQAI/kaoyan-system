#!/usr/bin/env python3
"""从已生成的词条里聚合词组卡与辨析卡，写入 204-phrases.jsonl / 204-confusable.jsonl。

口径：
- 词组取词条里出现且能在语料中找到的搭配，按语料命中次数排序；
- 辨析组取互相指认的易混对，一条卡覆盖两个词的区别，不额外编语境句。
"""
import json
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
META = ROOT / '知识点元数据'
VOCAB = META / 'subjects' / '204' / '204-vocab.jsonl'
SENTENCES = META / 'research' / '204-corpus' / 'sentences.jsonl'
OUT_PHRASES = META / 'subjects' / '204' / '204-phrases.jsonl'
OUT_CONFUSE = META / 'subjects' / '204' / '204-confusable.jsonl'


def collect_phrases(entries: list[dict], corpus: list[dict], limit: int = 80) -> list[dict]:
    text = ' '.join((r.get('en') or '').lower() for r in corpus)
    seen: dict[str, dict] = {}
    for e in entries:
        for p in e.get('phrases') or []:
            en = (p.get('en') or '').strip()
            if not en or en.lower() in seen:
                continue
            hits = text.count(en.lower())
            seen[en.lower()] = {'phrase': en, 'cn': p.get('cn', ''), 'hits': hits,
                                'from': e['word']}
    ranked = sorted(seen.values(), key=lambda x: (-x['hits'], x['phrase']))
    return ranked[:limit]


def collect_confusables(entries: list[dict], limit: int = 30) -> list[dict]:
    diffs: dict[str, dict[str, str]] = defaultdict(dict)
    for e in entries:
        for c in e.get('confusables') or []:
            other = (c.get('word') or '').strip().lower()
            if other:
                diffs[e['word']][other] = c.get('diff', '')
    out, used = [], set()
    for word, mates in diffs.items():
        for other, diff in mates.items():
            key = tuple(sorted((word, other)))
            if key in used:
                continue
            used.add(key)
            back = diffs.get(other, {}).get(word, '')
            text = diff if word in diff else f'{word}：{diff}'
            if back and back not in text:
                text += f'；{other}：{back}'
            out.append({
                'group': [word, other],
                'question': f'辨析：{word} 与 {other} 的区别',
                'answer': text,
                'diff': text,
                'from': word,
            })
    return out[:limit]


def main():
    entries = [json.loads(l) for l in VOCAB.read_text(encoding='utf-8').splitlines() if l.strip()]
    corpus = [json.loads(l) for l in SENTENCES.read_text(encoding='utf-8').splitlines() if l.strip()]
    phrases = collect_phrases(entries, corpus, 80)
    conf = collect_confusables(entries, 30)
    with OUT_PHRASES.open('w', encoding='utf-8') as f:
        for p in phrases:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')
    with OUT_CONFUSE.open('w', encoding='utf-8') as f:
        for c in conf:
            f.write(json.dumps(c, ensure_ascii=False) + '\n')
    print(f'{OUT_PHRASES.name}: {len(phrases)} 条；{OUT_CONFUSE.name}: {len(conf)} 条')


if __name__ == '__main__':
    sys.exit(main())
