#!/usr/bin/env python3
"""把含公式/符号的卡片改写成适合朗读的口语文本（LLM，结果落盘缓存）。

规则层 tts_text.py 先清能直接替换的记号；清完仍有数学/化学记号的卡片走本脚本，
结果写到 data/tts_text/{card_id}.txt，并记 source_sha1 用于失效判断。

用法：
  python3 scripts/gen_tts_text.py --limit 3 --dry-run
  python3 scripts/gen_tts_text.py --subjects 812 315
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
OUT = ROOT / 'data' / 'tts_text'
MANIFEST = OUT / 'manifest.json'
_lock = threading.Lock()

SYSTEM = """你把考研复习卡片改写成适合中文语音朗读的口语文本，供通勤时听。

硬性要求：
1. 不增删知识点，不改数值、单位、结论和因果关系。
2. 所有公式、符号、化学式、上下标、数学记号都改写成能直接念出的中文。例如：
   H⁺ → 氢离子；CO₂ → 二氧化碳；NaCl → 氯化钠；
   ΔfH°m → 标准摩尔生成焓；S°m → 标准摩尔熵；ΔᵣG°m → 反应的标准摩尔吉布斯自由能变；
   kJ·mol⁻¹ → 千焦每摩尔；J·mol⁻¹·K⁻¹ → 焦每摩尔每开尔文；
   N₂(g) + 3H₂(g) ⇌ 2NH₃(g) → 氮气加三分子氢气可逆生成两分子氨气；
   10⁵ → 10 的 5 次方；a_B → 溶液中溶质 B 的活度；① → 第一，。
   化学方程式里的系数一律念成「三分子氢气」这种形式，不要念成「三倍氢气」。
   符号后面不要再跟原字母（不要出现「标准平衡常数 K 标准」「S°m 标准摩尔熵」这类重复念法）。
   下划线一律不念，直接念字母：b_B → b B，x_B → x B，K° → 标准平衡常数。
3. 答案原本是选项字母（如 A）时，改写成"正确答案是 A，……"并把该选项内容念出来。
4. 保留原文顺序；并列分点用"第一、第二"或"首先、其次"。
5. 只输出改写后的正文，不要开场白、总结、解释，不要 markdown。

示例输入：下列关于热力学基本概念的说法中，正确的是（ ）。正确答案是D。在等温等压且只做体积功的封闭体系中，ΔG<0 可作为过程自发进行的判据
示例输出：下列关于热力学基本概念的说法中，正确的是。正确答案是 D。在等温等压且只做体积功的封闭体系中，反应的标准摩尔吉布斯自由能变小于零，可作为过程自发进行的判据。"""


def env(name, default=''):
    for path in (ROOT / '.env', ROOT / '.build' / 'pkg' / '.env'):
        if not path.exists():
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith(f'{name}='):
                return line.split('=', 1)[1].strip()
    return os.environ.get(name, default)


def rewrite(text, key, base_url, model, retries=3):
    payload = {
        'model': model,
        'temperature': 0.1,
        'messages': [{'role': 'system', 'content': SYSTEM},
                     {'role': 'user', 'content': text}],
    }
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    last = ''
    for attempt in range(retries + 1):
        try:
            r = requests.post(f'{base_url}/chat/completions', headers=headers,
                              json=payload, timeout=180)
            if r.status_code == 200:
                body = r.json()['choices'][0]['message']['content'].strip()
                if body:
                    return body, None
                last = '空响应'
            else:
                last = f'HTTP {r.status_code} {r.text[:120]}'
                if r.status_code not in (429, 500, 502, 503):
                    return None, last
        except Exception as e:  # noqa: BLE001
            last = f'{type(e).__name__}: {e}'[:160]
        time.sleep(3 * (attempt + 1))
    return None, last


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else {}


def save_manifest(m):
    tmp = MANIFEST.with_suffix('.tmp')
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(MANIFEST)


def collect(subjects, cards=None):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    marks = ','.join('?' * len(subjects))
    rows = conn.execute(
        f'SELECT c.* FROM card c JOIN point p ON p.id = c.point_id '
        f'WHERE p.subject_id IN ({marks}) ORDER BY p.subject_id, c.card_id',
        subjects).fetchall()
    out = []
    for r in rows:
        c = dict(r)
        if cards and c['card_id'] not in cards:
            continue
        c['options'] = json.loads(c['options'] or '[]')
        base = tts_text.spoken_text(c)
        if tts_text.needs_rewrite(base):
            out.append((c['card_id'], base))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--subjects', nargs='+', default=['812', '315', '101'])
    ap.add_argument('--cards', nargs='+', default=[])
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--concurrency', type=int, default=4)
    ap.add_argument('--api', choices=['deepseek', 'opencode'], default='deepseek')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if args.api == 'deepseek':
        key, base = env('DEEPSEEK_API_KEY'), env('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        model = env('DEEPSEEK_MODEL', 'deepseek-chat')
    else:
        key, base = env('OPENCODE_API_KEY'), env('OPENCODE_BASE_URL', 'https://opencode.ai/zen/go/v1')
        model = env('OPENCODE_MODEL', 'deepseek-v4.1-flash')
    if not key:
        raise SystemExit(f'缺少 {args.api.upper()} key')
    if args.api == 'opencode':
        base = base.rstrip('/')

    tasks = collect(args.subjects, set(args.cards) if args.cards else None)
    manifest = load_manifest()
    todo = []
    for cid, base_text in tasks:
        sha = hashlib.sha1(base_text.encode('utf-8')).hexdigest()
        old = manifest.get(cid)
        cached = (OUT / f'{cid}.txt')
        fresh = (old and old.get('sha1') == sha and cached.exists())
        if fresh and not args.force:
            continue
        todo.append((cid, base_text, sha))
    if args.limit:
        todo = todo[:args.limit]

    print(f'需改写 {len(tasks)} 张，待处理 {len(todo)} 张，模型 {model}', flush=True)
    if args.dry_run:
        for cid, t, _ in todo[:3]:
            print(f'\n### {cid}\n{t[:300]}')
        return
    if not todo:
        print('全部已改写，无需处理')
        return

    OUT.mkdir(parents=True, exist_ok=True)
    done = fail = 0
    errs = []
    t0 = time.time()

    def one(t):
        return t, *rewrite(t[1], key, base, model)

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [ex.submit(one, t) for t in todo]
        for fut in as_completed(futs):
            (cid, base_text, sha), body, err = fut.result()
            if body:
                (OUT / f'{cid}.txt').write_text(body, encoding='utf-8')
                with _lock:
                    manifest[cid] = {'sha1': sha, 'model': model,
                                     'created_at': int(time.time())}
                done += 1
            else:
                fail += 1
                errs.append([cid, err])
            n = done + fail
            if n % 20 == 0:
                save_manifest(manifest)
                print(f'  {n}/{len(todo)}  成功 {done} 失败 {fail}  '
                      f'{n / max(time.time() - t0, 1) * 60:.0f} 张/分', flush=True)

    save_manifest(manifest)
    print(f'完成：成功 {done} · 失败 {fail} · 用时 {(time.time() - t0) / 60:.1f} 分')
    if errs:
        (OUT / 'failed.json').write_text(json.dumps(errs, ensure_ascii=False, indent=1),
                                         encoding='utf-8')
        print('失败清单：', OUT / 'failed.json')


if __name__ == '__main__':
    main()
