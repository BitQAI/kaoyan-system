"""原子记忆单元的确定性切分（无需 LLM）。

背景
----
旧管线用 LLM 把 explain 拆成「原子知识单元」，代价是每个知识点一次调用（524 次），
且输出不稳定、无法回归。本模块改为**确定性切分**：

  explain 本身就是按「一件事一句」写的（3–6 句），所以**句界切分即等价于「一单元一件事」**；
  过长的句子优先按**逗号**二次拆分（顿号会割裂并列短语，尽量避开）；
  过短的句子与相邻句合并到 30–70 字窗口。

产出与 LLM 版同构：list[str]，每条 30–70 字，可独立记忆。
"""

import re

MIN_LEN = 30
MAX_LEN = 70

_SENT = re.compile(r'[^。！？!?；;]+[。！？!?；;]?')
_CLAUSE_COMMA = re.compile(r'[^，,]+[，,]?')
_CLAUSE_DUN = re.compile(r'[^、]+[、]?')


def _sentences(text):
    out = []
    for s in _SENT.findall(text or ''):
        s = s.strip()
        if s:
            out.append(s)
    return out


def _chunk_by(pattern, s):
    """按给定标点切分并贪心装入 MAX_LEN 窗口。"""
    parts, buf = [], ''
    for c in pattern.findall(s):
        c = c.strip()
        if not c:
            continue
        if len(buf) + len(c) <= MAX_LEN:
            buf += c
        else:
            if buf:
                parts.append(buf)
            while len(c) > MAX_LEN:
                parts.append(c[:MAX_LEN])
                c = c[MAX_LEN:]
            buf = c
    if buf:
        parts.append(buf)
    return parts


def _split_long(s):
    """超长句：先按逗号切；逗号粒度不够再按顿号切；仍超长硬切。"""
    parts = _chunk_by(_CLAUSE_COMMA, s)
    if len(parts) <= 1:
        parts = _chunk_by(_CLAUSE_DUN, s)
    if len(parts) <= 1:
        parts = [s[i:i + MAX_LEN] for i in range(0, len(s), MAX_LEN)]
    return parts


def _merge_short(units):
    """过短单元优先与**后一个**合并（语义更连贯），放不下再与前一个合并。"""
    out = []
    for u in units:
        if out and len(out[-1]) < MIN_LEN:
            merged = out[-1] + u
            if len(merged) <= MAX_LEN:
                out[-1] = merged
                continue
        out.append(u)
    # 尾部过短 → 并入前一个
    while len(out) > 1 and len(out[-1]) < MIN_LEN:
        tail = out.pop()
        if len(out[-1] + tail) <= MAX_LEN:
            out[-1] += tail
        else:
            out.append(tail)
            break
    return out


def split_units(explain, fallback=None):
    """从 explain 切出原子单元。

    explain: 理解解析文本（LLM 写的 3–6 句）
    fallback: explain 为空时使用的兜底文本（通常是考点原文）
    """
    text = (explain or '').strip()
    if not text:
        text = (fallback or '').strip()
    if not text:
        return []
    units = []
    for s in _sentences(text):
        units.extend(_split_long(s) if len(s) > MAX_LEN else [s])
    units = [u for u in units if u]
    if not units:
        return []
    units = _merge_short(units)
    if len(units) == 1 and len(units[0]) < MIN_LEN and len(text) > MIN_LEN:
        units = _split_long(text)
    return units
