#!/usr/bin/env python3
"""点级徽标补全（幂等）：
  812 ← 章级标签下发（基础/重点/易错）
  315 ← 大纲「掌握/理解/了解」层级（二元组匹配到点）+ 真题反查关键词 →「常考」
  101 ← 高频且基础清单关键词 →「高频」
用法：python scripts/enrich_tags.py
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.coverage_check import (MERGED, _section_by_id, bigrams, cn2num,  # noqa: E402
                                    extract_mod_blocks, text_of)

LV = {"lv-m": "必掌握", "lv-u": "理解", "lv-k": "了解"}


def coverage_in(short: str, long: str) -> float:
    """short 的 bigram 有多少出现在 long 中。"""
    bg = bigrams(short)
    if not bg:
        return 0.0
    return sum(1 for g in bg if g in long) / len(bg)


def tag_812(content):
    n = 0
    for subj in content["subjects"]:
        if subj["id"] != "812":
            continue
        for ch in subj["chapters"]:
            ch_tags = ch.get("tags", [])
            point_tags = [t for t in ch_tags if t in ("基础", "重点")]
            if any(t.startswith("易错") for t in ch_tags):
                point_tags.append("易错")
            for p in ch["points"]:
                if "机制" in p.get("tags", []):
                    continue                      # 机制点保持原标签
                for t in point_tags:
                    if t not in p["tags"]:
                        p["tags"].append(t)
                        n += 1
    return n


def _items_with_level(block):
    out = []
    for m in re.finditer(r'<li[^>]*>(.*?)</li>', block, re.S):
        raw = m.group(1)
        lv = "理解"
        for k, v in LV.items():
            if f'class="lv {k}"' in raw:
                lv = v
        out.append((lv, text_of(re.sub(r'<span class="lv[^"]*">[^<]*</span>', "", raw))))
    return [(lv, t) for lv, t in out if len(t) >= 4]


def tag_315(content):
    merged = MERGED.read_text(encoding="utf-8")
    chapters = {}
    for subj in content["subjects"]:
        if subj["id"] == "315":
            chapters = {ch["id"]: ch for ch in subj["chapters"]}
    n = 0
    for anchor, base in (("p3-2", 0), ("p3-3", 11)):
        seg = _section_by_id(merged, anchor)
        for block in extract_mod_blocks(seg):
            tm = re.search(r'class="t">(.*?)</span>', block)
            if not tm:
                continue
            nums = []
            for part in re.split(r"[｜|]", text_of(tm.group(1))):
                mm = re.match(r"^([一二三四五六七八九十]+)、", part.strip())
                if mm and cn2num(mm.group(1)):
                    nums.append(base + cn2num(mm.group(1)))
            if not nums:
                continue
            items = _items_with_level(block)
            # 真题反查关键词
            fz = re.search(r"真题反查：</b>(.*?)</p>", block, re.S)
            frags = []
            if fz:
                for frag in re.split(r"[；;。]", text_of(fz.group(1))):
                    for run in re.split(r"[、，,（）()【】\[\]]", frag):
                        run = run.strip()
                        if len(run) >= 3:
                            frags.append(run)
            grams = {f[i:i + 3] for f in frags for i in range(len(f) - 2)}
            for num in nums:
                ch = chapters.get(f"315-{num:02d}")
                if not ch:
                    continue
                for p in ch["points"]:
                    text = p["text"]
                    # 层级：点文本的 bigram 大部分出现在某条大纲条目里
                    for lv, item in items:
                        if coverage_in(text, item) >= 0.5 or coverage_in(item, text) >= 0.35:
                            if lv not in p["tags"]:
                                p["tags"].append(lv)
                                n += 1
                            break
                    if "常考" not in p["tags"] and any(g in text for g in grams):
                        p["tags"].append("常考")
                        n += 1
    return n


BLACKLIST_101 = {"发展", "关系", "作用", "内容", "体现", "阶段", "基本", "主要", "包括",
                 "如下", "形成", "实现", "要求", "道路", "制度", "理论", "体系"}


def tag_101(content):
    merged = MERGED.read_text(encoding="utf-8")
    sec = _section_by_id(merged, "p1-4")
    m = re.search(r"1\.4[^<]*政治[^<]*高频[^<]*", sec)
    if not m:
        return 0
    end = sec.find("<h2", m.end())
    body = text_of(sec[m.end():end if end > 0 else len(sec)])
    tokens = set()
    for tok in re.split(r"[、，,；;：:（）()【】\[\]/]", body):
        tok = tok.strip()
        if 2 <= len(tok) <= 8 and tok not in BLACKLIST_101:
            tokens.add(tok)
    n = 0
    for subj in content["subjects"]:
        if subj["id"] != "101":
            continue
        for ch in subj["chapters"]:
            for p in ch["points"]:
                if any(len(t) >= 2 and t in p["text"] for t in tokens):
                    if "高频" not in p["tags"]:
                        p["tags"].append("高频")
                        n += 1
    return n


def main():
    path = ROOT / "content" / "content.json"
    content = json.loads(path.read_text(encoding="utf-8"))
    n1 = tag_812(content)
    n2 = tag_315(content)
    n3 = tag_101(content)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    cnt = Counter()
    tot = 0
    for subj in content["subjects"]:
        for ch in subj.get("chapters", []):
            for p in ch["points"]:
                tot += 1
                for t in p.get("tags", []):
                    cnt[t] += 1
    print(f"新增标签: 812 {n1} · 315 {n2} · 101 {n3}")
    print(f"标签分布（共 {tot} 点）: {dict(cnt)}")


if __name__ == "__main__":
    main()
