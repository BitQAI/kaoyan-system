#!/usr/bin/env python3
"""卡片级 Fish Audio 合成：卡片（考点 question + 作答 answer）→ MP3。

与 gen_audio.py 的区别：那份按知识点 tts.clips（点级脚本）生成，这份按「听」页实际
朗读的卡片粒度生成，文件名 = card_id，并写 manifest 记录文本哈希用于失效判断。

用法：
  python3 scripts/gen_card_audio.py --key-file /path/to/.fishkey
  python3 scripts/gen_card_audio.py --subjects 812 315 --dry-run

断点续跑：已存在的 mp3 跳过；--force 覆盖。
"""
import argparse
import hashlib
import json
import os
import pathlib
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tts_text  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / 'data' / 'ky.db'
OUT = ROOT / 'data' / 'audio'
TTS_TEXT = ROOT / 'data' / 'tts_text'
MANIFEST = OUT / 'manifest.json'
URL = 'https://api.fish.audio/v1/tts'
MODEL = 's2.1-pro-free'
VOICE = '36ef842120654ee6b38ef43c8f08535a'
BYTES_PER_SEC = 16000  # 128kbps mp3
_lock = threading.Lock()


def api_key(key_file):
    k = os.environ.get('FISH_API_KEY', '').strip()
    if not k and key_file:
        k = pathlib.Path(key_file).read_text(encoding='utf-8').strip()
    if not k:
        raise SystemExit('缺少 FISH_API_KEY（环境变量或 --key-file）')
    return k


def synth(text, key, speed=1.0, retries=4):
    payload = {
        'text': text, 'reference_id': VOICE, 'format': 'mp3', 'sample_rate': 44100,
        'mp3_bitrate': 128, 'latency': 'normal', 'chunk_length': 300,
        'min_chunk_length': 50, 'normalize': True, 'language': 'zh',
        'prosody': {'speed': speed, 'volume': 0, 'normalize_loudness': True},
    }
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
               'model': MODEL}
    last = ''
    for attempt in range(retries + 1):
        try:
            r = requests.post(URL, headers=headers, json=payload, timeout=240)
            if r.status_code == 200 and len(r.content) > 1000:
                return r.content, None
            last = f'HTTP {r.status_code} {r.text[:160]}'
            if r.status_code not in (429, 500, 502, 503, 504):
                return None, last
        except Exception as e:  # noqa: BLE001
            last = f'{type(e).__name__}: {e}'[:160]
        time.sleep(min(60, 5 * (attempt + 1) ** 2))
    return None, last


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding='utf-8'))
    return {}


def save_manifest(m):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix('.tmp')
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(MANIFEST)


def load_tts_index():
    path = TTS_TEXT / 'manifest.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def rewrite_of(cid, base, index):
    """命中的 LLM 改写文本（源文本没变才用）。"""
    meta = index.get(cid)
    path = TTS_TEXT / f'{cid}.txt'
    if not meta or not path.exists():
        return ''
    if meta.get('sha1') != hashlib.sha1(base.encode('utf-8')).hexdigest():
        return ''
    return path.read_text(encoding='utf-8').strip()


def collect(subjects):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    marks = ','.join('?' * len(subjects))
    rows = conn.execute(
        f'SELECT c.card_id, p.subject_id, c.question, c.answer, c.kind, c.options '
        f'FROM card c JOIN point p ON p.id = c.point_id '
        f'WHERE p.subject_id IN ({marks}) '
        f'ORDER BY p.subject_id, c.card_id', subjects).fetchall()
    index = load_tts_index()
    tasks = []
    for r in rows:
        card = dict(r)
        card['options'] = json.loads(card.get('options') or '[]')
        base = tts_text.spoken_text(card)
        text = rewrite_of(card['card_id'], base, index) or base
        if text:
            tasks.append((card['subject_id'], card['card_id'], text))
    return tasks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--subjects', nargs='+', default=['812', '315', '101'])
    ap.add_argument('--concurrency', type=int, default=5)
    ap.add_argument('--speed', type=float, default=1.0)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--cards', nargs='+', default=[])
    ap.add_argument('--key-file', default='')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    tasks = collect(args.subjects)
    if args.cards:
        wanted = set(args.cards)
        tasks = [t for t in tasks if t[1] in wanted]
    manifest = load_manifest()
    todo = []
    for sid, cid, text in tasks:
        path = OUT / sid / f'{cid}.mp3'
        sha = hashlib.sha1(text.encode('utf-8')).hexdigest()
        old = manifest.get(cid)
        # 只有 manifest 明确记录过、且文本与速度都一致才算已完成；
        # 有文件但无记录（中断残留）一律重做，避免留下错误语速的音频。
        fresh = (bool(old) and old.get('sha1') == sha
                 and old.get('speed') == args.speed)
        if path.exists() and fresh and not args.force:
            continue
        todo.append((sid, cid, text, sha))
    if args.limit:
        todo = todo[:args.limit]

    chars = sum(len(t[2]) for t in todo)
    est_sec = chars / 3.8 / args.speed  # 实测约 3.8 字/秒
    print(f'卡片 {len(tasks)} 张，待合成 {len(todo)} 张，{chars} 字，'
          f'预估音频 {est_sec / 3600:.1f} 小时', flush=True)
    if args.dry_run:
        for t in todo[:5]:
            print('  ', t[0], t[1], t[2][:40])
        return
    if not todo:
        print('全部已存在，无需生成')
        return

    key = api_key(args.key_file)
    for sid in {t[0] for t in todo}:
        (OUT / sid).mkdir(parents=True, exist_ok=True)

    def one(t):
        return t, *synth(t[2], key, args.speed)

    done = fail = 0
    errs = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [ex.submit(one, t) for t in todo]
        for fut in as_completed(futs):
            (sid, cid, text, sha), data, err = fut.result()
            if data:
                path = OUT / sid / f'{cid}.mp3'
                path.write_bytes(data)
                manifest[cid] = {
                    'subject': sid, 'sha1': sha, 'bytes': len(data),
                    'sec': round(len(data) / BYTES_PER_SEC, 1),
                    'model': MODEL, 'voice': VOICE, 'speed': args.speed,
                    'created_at': int(time.time()),
                }
                done += 1
            else:
                fail += 1
                errs.append([cid, err])
            n = done + fail
            if n % 50 == 0:
                save_manifest(manifest)
                rate = n / max(time.time() - t0, 1) * 60
                eta = (len(todo) - n) / max(n / max(time.time() - t0, 1), 1e-6) / 60
                print(f'  {n}/{len(todo)}  成功 {done} 失败 {fail}  '
                      f'{rate:.0f} 段/分  剩 {eta:.0f} 分', flush=True)

    save_manifest(manifest)
    print(f'完成：成功 {done} · 失败 {fail} · 用时 {(time.time() - t0) / 60:.1f} 分')
    if errs:
        (OUT / 'failed.json').write_text(
            json.dumps(errs, ensure_ascii=False, indent=1), encoding='utf-8')
        print('失败清单：', OUT / 'failed.json')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
