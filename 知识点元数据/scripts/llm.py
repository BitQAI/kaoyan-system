"""LLM 调用封装（opencode go 网关 / deepseek-v4.1-flash）。

三个生成脚本（enrich / gen_units / gen_cards）共用本模块，保证：
- 统一的 429 限流退避与连接中断重试；
- 统一的容错 JSON 解析（花括号配对扫描，能处理字符串内的花括号与被截断的响应）。
"""
import json
import os
import pathlib
import re
import time

import requests

MODEL = 'deepseek-v4.1-flash'
DEFAULT_BASE = 'https://opencode.ai/zen/go/v1'
ENV_FALLBACKS = [
    pathlib.Path.home() / '.config/kaoyan/bailian.env',
    pathlib.Path('/Users/huajun/Sync/kaoyan-system/.env'),
]


def settings():
    base = os.environ.get('OPENCODE_GO_BASE', DEFAULT_BASE).rstrip('/')
    key = os.environ.get('OPENCODE_GO_KEY', '')
    for env in ENV_FALLBACKS:
        if key or not env.exists():
            continue
        for line in env.read_text(encoding='utf-8').splitlines():
            if line.startswith('OPENCODE_GO_KEY='):
                key = line.split('=', 1)[1].strip()
            elif line.startswith('OPENCODE_GO_BASE='):
                base = line.split('=', 1)[1].strip().rstrip('/')
    return base, key


def parse_reply(t):
    """容错解析：剥围栏 → 花括号配对扫描 → json.loads。"""
    if not t:
        return None
    t = re.sub(r'^```(?:json)?\s*', '', t.strip())
    t = re.sub(r'\s*```$', '', t)
    i = t.find('{')
    if i < 0:
        return None
    depth, in_str, esc = 0, False, False
    for k in range(i, len(t)):
        ch = t[k]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[i:k + 1])
                except json.JSONDecodeError:
                    return None
    return None


def call_llm(messages, max_tokens=6000, retries=5, session=None):
    session = session or os.environ.get('OPENCODE_SESSION', 'ky-meta')
    base, key = settings()
    if not key:
        raise SystemExit('缺少 OPENCODE_GO_KEY')
    url = base + '/chat/completions'
    headers = {'Authorization': f'Bearer {key}', 'x-opencode-session': session}
    last = ''
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, headers={**headers, 'Content-Type': 'application/json'},
                              json={'model': MODEL, 'messages': messages,
                                    'max_tokens': max_tokens}, timeout=300)
            if r.status_code == 429:
                wait = 8 * (attempt + 1)
                print(f'  · 限流(429)，等待 {wait}s', file=__import__('sys').stderr)
                time.sleep(wait)
                last = '429'
                continue
            r.raise_for_status()
            j = r.json()
            choice = (j.get('choices') or [{}])[0]
            content = (choice.get('message') or {}).get('content') or ''
            got = parse_reply(content)
            if got:
                return got
            last = (f"finish={choice.get('finish_reason')} "
                    f"content_len={len(content)}")
        except Exception as e:  # noqa: BLE001
            last = str(e)[:150]
        time.sleep(2.5 * (attempt + 1))
    print(f'  ! 生成失败：{last}', file=__import__('sys').stderr)
    return None
