"""source.ref → 源文档原文段落。

配方移植自 知识点元数据/scripts/check_locator.py（该脚本对 524 点逐字验证过）。
差别只有一处：那边只取 split[M] 那一片用于比对，这里取整段——分片本身就是
point 字段，单独取出来与上下文重复，整段才是「这一点在原始资料里的完整语境」。
"""
import html as H
import re
from functools import lru_cache
from pathlib import Path

from app import config

_SECTION_RE = re.compile(r'<section class="section" id="([^"]+)"')


def _text_of(frag: str) -> str:
    frag = re.sub(r"<br\s*/?>", " ", frag)
    frag = re.sub(r"<[^>]+>", "", frag)
    return re.sub(r"\s+", " ", H.unescape(frag)).strip()


@lru_cache(maxsize=4)
def _read_source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _section(text: str, anchor: str) -> str:
    i = text.find(f'<section class="section" id="{anchor}"')
    if i < 0:
        raise ValueError(f"未找到 section {anchor!r}")
    j = text.find('<section class="section" id="', i + 10)
    return text[i:j if j > i else len(text)]


def _find_block(sec: str, chap: str) -> str:
    for pattern in (r'(?=<div class="chapter">)', r"(?=<h3)"):
        for block in re.split(pattern, sec):
            if not block.lstrip().startswith(("<div class=\"chapter\">", "<h3")):
                continue
            m = re.search(r"<h3>(.*?)</h3>", block, re.S)
            if m and _text_of(m.group(1)) == chap:
                return block
    raise ValueError(f"未找到章名 {chap!r}")


def resolve_paragraph(ref: str | None, kind: str | None = "html",
                      source_file: str | None = None,
                      fallback: str = "") -> tuple[str, str]:
    """返回 (原文段落, 说明)。syllabus 或解析失败时回落到 fallback。"""
    if not ref:
        return fallback, "无溯源定位符"
    if kind == "syllabus":
        return fallback, "考纲条款（无 HTML 原文）"
    path = config.ROOT_DIR / (source_file or "2027考研_四科知识全景与章节权重.html")
    if not path.exists():
        return fallback, "源文件不存在"
    try:
        text = _read_source(str(path))
        sec_name, rest = ref.split("#", 1)
        chap, sub = rest.split("/", 1)
        block = _find_block(_section(text, sec_name), chap)
        if sub.startswith("mech["):
            idx = int(re.match(r"mech\[(\d+)\]", sub).group(1))
            mech = re.findall(r'<p class="mech">(.*?)</p>', block, re.S)
            return _text_of(mech[idx]), ""
        m = re.search(r"<p>(.*?)</p>", block, re.S)
        return _text_of(m.group(1)), ""
    except (ValueError, AttributeError, IndexError, re.error) as exc:
        return fallback, f"溯源解析失败：{exc}"
