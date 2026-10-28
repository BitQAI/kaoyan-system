#!/usr/bin/env python3
"""Fish Audio 批量 TTS：元数据 → 音频（文件名 = clip_id）。

用法：
  python3 scripts/gen_audio.py --voice 36ef842120654ee6b38ef43c8f08535a
  python3 scripts/gen_audio.py --dry-run

断点续跑：已存在的 mp3 跳过。
"""
import argparse
import json
import os
import pathlib
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chem  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'
OUT = META / 'audio'
URL = 'https://api.fish.audio/v1/tts'
MODEL = 's2.1-pro-free'
_lock = threading.Lock()

# 官方授权音色（licensed=true）
VOICE_LIB = {
    '36ef842120654ee6b38ef43c8f08535a': '宣传片浑厚男声',
    '3ebbc3083add43d68aef50815e561316': '沉稳男声',
    '6f1ca7031e964906905e5a46c5b2da4c': '专业本男声',
    'e22f5950a488478ba1283941e5e48c6e': '温柔宁静男声',
    '4cd529b3a2f64774980425633d3e4e02': '温柔沉稳的男声',
    'd9956cb243a34292afc9b42ad3964f73': '温柔沉稳男声',
    '6af29f4378744d93939a8fd7a55dde58': '温暖晨光男声',
    '32c775efe12d461288c67310f4f12ebb': '温暖静谧男声',
}


def api_key():
    k = os.environ.get('FISH_API_KEY', '')
    if not k:
        env = ROOT / '.build' / 'fish' / '.env'
        if env.exists():
            for line in env.read_text(encoding='utf-8').splitlines():
                if line.startswith('FISH_API_KEY='):
                    k = line.split('=', 1)[1].strip()
    if not k:
        raise SystemExit('缺少 FISH_API_KEY')
    return k


def synth(text, ref, key, retries=5):
    payload = {
        'text': text, 'reference_id': ref, 'format': 'mp3', 'sample_rate': 44100,
        'mp3_bitrate': 128, 'latency': 'normal', 'chunk_length': 300,
        'min_chunk_length': 50, 'normalize': True, 'language': 'zh',
        'prosody': {'speed': 1.0, 'volume': 0, 'normalize_loudness': True},
    }
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
               'model': MODEL}
    last = ''
    for attempt in range(retries + 1):
        try:
            r = requests.post(URL, headers=headers, json=payload, timeout=180)
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1))
                last = '429'
                continue
            if r.status_code != 200:
                return None, f'HTTP {r.status_code} {r.text[:120]}'
            return r.content, None
        except Exception as e:  # noqa: BLE001
            last = str(e)[:120]
        time.sleep(3 * (attempt + 1))
    return None, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--voice', default='36ef842120654ee6b38ef43c8f08535a')
    ap.add_argument('--concurrency', type=int, default=4)
    ap.add_argument('--subject', action='append', default=[])
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    key = api_key()
    ref = args.voice
    vname = VOICE_LIB.get(ref, '自定义音色')
    print(f'音色：{vname}  ({ref})   模型：{MODEL}')

    tasks = []
    for sid in ('812', '315', '101', '204'):
        if args.subject and sid not in args.subject:
            continue
        doc = json.loads((META / 'subjects' / sid / f'{sid}.json').read_text(encoding='utf-8'))
        for p in doc['points']:
            if not (p.get('tts') or {}).get('enabled'):
                continue
            for c in p['tts']['clips']:
                tasks.append((sid, c['clip_id'], c['text']))
    todo = [t for t in tasks if not (OUT / t[0] / f'{t[1]}.mp3').exists()]
    total_sec = sum(t[2].__len__() for t in todo) / chem.CHARS_PER_SEC
    print(f'待生成 {len(todo)} / {len(tasks)} 段   预估时长 {total_sec / 60:.0f} 分钟')
    if args.dry_run:
        for t in todo[:10]:
            print('  ', t[1], t[2][:50])
        return
    if not todo:
        print('全部已存在，无需生成')
        return

    for sid in ('812', '315', '101', '204'):
        (OUT / sid).mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    errs = []

    def one(t):
        sid, cid, text = t
        data, err = synth(text, ref, key)
        return t, data, err

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [ex.submit(one, t) for t in todo]
        for i, fut in enumerate(as_completed(futs), 1):
            (sid, cid, text), data, err = fut.result()
            if data:
                (OUT / sid / f'{cid}.mp3').write_bytes(data)
                ok += 1
            else:
                fail += 1
                errs.append((cid, err))
            if i % 25 == 0 or i == len(todo):
                with _lock:
                    print(f'  进度 {i}/{len(todo)}（成功 {ok} · 失败 {fail}）', flush=True)
    print(f'完成：成功 {ok} · 失败 {fail}')
    if errs:
        (OUT / 'failed.json').write_text(
            json.dumps(errs, ensure_ascii=False, indent=1), encoding='utf-8')
        print('失败清单：', OUT / 'failed.json')


if __name__ == '__main__':
    main()
