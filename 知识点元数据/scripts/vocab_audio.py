#!/usr/bin/env python3
"""词卡与范文卡的分片音频。

规则（与前端、接口约定一致）：
- 词卡：word(英文) / meaning(中文) / sentence(英文)；整卡 mp3 由分片字节拼接
- 词组卡：word / meaning
- 辨析卡：说明中文一条
- 回译 / 默写 / 句型 / 整篇卡：para（英文段落或全文）
缺失时前端回退浏览器 TTS，所以失败只记日志、不中断。
"""
import argparse
import hashlib
import json
import pathlib
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_audio  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
META = ROOT / '知识点元数据'
DOC = META / 'subjects' / '204' / '204.json'
OUT = ROOT / 'data' / 'audio'
EN_VOICE = '933563129e564b19a115bedd57b7406a'   # Sarah：Fish 公共英文音色（用户选定）
ZH_VOICE = '59cb5986671546eaa6ca8ae6f29f6d22'   # 央视配音：Fish 公共中文音色


MANIFEST = OUT / '204' / '_manifest.json'
_lock = threading.Lock()


def text_hash(text: str, voice: str) -> str:
    """文本+音色指纹：文本一改，旧音频作废重生成。"""
    return hashlib.sha1(f'{voice}|{text}'.encode()).hexdigest()


def load_manifest() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding='utf-8'))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_manifest(data: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding='utf-8')


def clip_path(subject: str, card_id: str, clip: str | None) -> pathlib.Path:
    name = f'{card_id}-{clip}.mp3' if clip else f'{card_id}.mp3'
    return OUT / subject / name


def scripts_for(card: dict) -> list[dict]:
    p = card.get('payload') or {}
    kind = p.get('type')
    if kind == 'word':
        meaning = '；'.join(m['cn'] for m in p.get('meanings') or [] if m.get('cn'))
        ex = (p.get('examples') or [{}])[0]
        out = [{'clip': 'word', 'text': p.get('word') or '', 'lang': 'en-US'}]
        if meaning:
            out.append({'clip': 'meaning', 'text': meaning, 'lang': 'zh-CN'})
        if ex.get('quote'):
            out.append({'clip': 'sentence', 'text': ex['quote'], 'lang': 'en-US'})
        return [c for c in out if c['text']]
    if kind == 'phrase':
        meaning = '；'.join(m['cn'] for m in p.get('meanings') or [] if m.get('cn'))
        return [{'clip': 'word', 'text': p.get('word') or '', 'lang': 'en-US'}] + (
            [{'clip': 'meaning', 'text': meaning, 'lang': 'zh-CN'}] if meaning else [])
    if kind == 'confusable':
        return [{'clip': 'meaning', 'text': p.get('diff') or '', 'lang': 'zh-CN'}] \
            if p.get('diff') else []
    text = (card.get('answer') or '').strip()
    return [{'clip': 'para', 'text': text, 'lang': 'en-US'}] if text else []


def build(doc: dict) -> list[dict]:
    jobs = []
    for point in doc['points']:
        for card in point['cards']:
            jobs.append({'card_id': card['card_id'], 'clips': scripts_for(card)})
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--sample', action='store_true', help='只做前 5 个词验音色')
    ap.add_argument('--workers', type=int, default=4, help='并发数')
    args = ap.parse_args()

    doc = json.loads(DOC.read_text(encoding='utf-8'))
    jobs = build(doc)
    if args.sample:
        jobs = [j for j in jobs if j['clips'] and j['card_id'].startswith('c2041')][:5]
    if args.limit:
        jobs = jobs[:args.limit]
    total = sum(len(j['clips']) for j in jobs)
    if args.dry_run:
        print(f'{len(jobs)} 张卡 / {total} 段音频')
        return
    key = gen_audio.api_key()
    manifest = load_manifest()
    done = 0
    started = time.time()
    count = [0]
    last = [time.time()]

    def one(job):
        parts = []
        for clip in job['clips']:
            path = clip_path('204', job['card_id'], clip['clip'])
            path.parent.mkdir(parents=True, exist_ok=True)
            voice = EN_VOICE if clip['lang'] == 'en-US' else ZH_VOICE
            h = text_hash(clip['text'], voice)
            fresh = path.exists() and manifest.get(path.name) == h
            if not fresh:
                content, err = gen_audio.synth(
                    clip['text'], voice, key, language='en' if clip['lang'] == 'en-US' else 'zh')
                if not content:
                    print(f'  ! 失败 {path.name}: {err}')
                    continue
                path.write_bytes(content)
                with _lock:
                    manifest[path.name] = h
                    if len(manifest) % 50 == 0:
                        save_manifest(manifest)
            parts.append(path)
        if parts:
            whole = clip_path('204', job['card_id'], None)
            whole.write_bytes(b''.join(p.read_bytes() for p in parts))
            with _lock:
                manifest[whole.name] = text_hash(
                    '|'.join(c['text'] for c in job['clips']), 'joined')
        count[0] += 1
        if count[0] % 50 == 0:
            now = time.time()
            span = max(0.5, now - last[0])
            last[0] = now
            rate = 50 / span * 60
            eta = (len(jobs) - count[0]) / max(rate, 0.01)
            print(f'  {count[0]}/{len(jobs)} 张卡   {rate:.0f} 张/分   剩余约 {eta:.0f} 分钟',
                  flush=True)
        return sum(1 for _ in parts)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for n in pool.map(one, jobs):
            done += n
    save_manifest(manifest)
    print(f'完成 {done}/{total} 段')


if __name__ == '__main__':
    main()
