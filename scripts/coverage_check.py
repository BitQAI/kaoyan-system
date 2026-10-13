#!/usr/bin/env python3
"""考点覆盖率检查：大纲条目 ↔ content.json 知识点 的机械化查漏。

方法：对每条大纲条目，取其字符二元组（bigram），计算有多少比例能在
对应章节的「全部考点文本」中找到；低于阈值（默认 0.55）的条目列为疑似缺口，
供人工复核（同义改写会导致低分，属正常，重点看真实遗漏）。

用法：python scripts/coverage_check.py [--subject 812|315|101] [--threshold 0.55]
数据源：
  812 ← 《812植物生理学》考试大纲.pdf（pdftotext）
  315 ← 合并版 HTML 的「十六/十七 章原文清单」（qj 大纲原文）
  101 ← 合并版 HTML 的「B. 101」考点清单（官方模块口径，定性核对）
"""
import argparse
import html as html_mod
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MERGED = pathlib.Path.home() / "Sync/master_eaxm/2027考研_四科知识全景与章节权重.html"
SYLLABUS_812 = pathlib.Path.home() / "Sync/master_eaxm/《812植物生理学》考试大纲.pdf"


def text_of(frag: str) -> str:
    frag = re.sub(r"<[^>]+>", "", frag)
    return re.sub(r"\s+", "", html_mod.unescape(frag))


def bigrams(s: str) -> set:
    return {s[i:i + 2] for i in range(len(s) - 1)}


def coverage(item: str, corpus: str, threshold: float) -> float:
    bg = bigrams(item)
    if not bg:
        return 1.0
    hit = sum(1 for g in bg if g in corpus)
    return hit / len(bg)


def chapter_corpus(content: dict, subject: str) -> dict:
    s = next(x for x in content["subjects"] if x["id"] == subject)
    out = {}
    for ch in s["chapters"]:
        parts = []
        for p in ch["points"]:
            parts.append(p["text"])
        out[ch["id"]] = {"name": ch["name"], "corpus": "".join(parts)}
    return out


# ---------- 812：考纲 PDF ----------

def items_812() -> dict:
    txt = subprocess.run(["pdftotext", "-layout", str(SYLLABUS_812), "-"],
                         capture_output=True, text=True).stdout
    # 取「考试内容和考试要求」到「参考书目」之间
    m = re.search(r"考试内容和考试要求(.*?)参考书目", txt, re.S)
    body = m.group(1) if m else txt
    chapters = {}
    cur = None
    for line in body.splitlines():
        line = line.strip()
        if re.match(r"^(绪论|第[一二三四五六七八九十]+章)", line):
            cur = line[:16]
            chapters[cur] = []
        elif cur and line:
            chapters[cur].append(line.replace(" ", ""))
    return {k: "".join(v) for k, v in chapters.items()}


# ---------- 315：合并版 HTML 大纲原文清单 ----------

def _section_by_id(merged: str, anchor: str) -> str:
    i = merged.find(f'id="{anchor}"')
    if i < 0:
        return ""
    j = merged.find('<section class="section" id="', i + 10)
    return merged[i:j] if j > i else merged[i:]


CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8,
          "九": 9, "十": 10, "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15}


def cn2num(s: str) -> int | None:
    return CN_NUM.get(s)


def extract_mod_blocks(seg: str) -> list[str]:
    """深度计数提取 <details class="mod ..."> 块（兼容变体类名与内部嵌套 details）。"""
    blocks, pos = [], 0
    marker_re = re.compile(r'<details class="mod[^"]*">')
    while True:
        m = marker_re.search(seg, pos)
        if not m:
            break
        i, j, depth = m.start(), m.end(), 1
        while j < len(seg) and depth > 0:
            nd = seg.find("<details", j)
            nc = seg.find("</details>", j)
            if nc < 0:
                break
            if nd != -1 and nd < nc:
                depth += 1
                j = nd + 8
            else:
                depth -= 1
                j = nc + 10
        blocks.append(seg[i:j])
        pos = j
    return blocks


def items_315() -> list[tuple[list[int], str, list[str]]]:
    """[(章节号列表, 标题, [大纲要求条目])]。合并块（如"十三｜十四"）返回多个章节号。"""
    merged = MERGED.read_text(encoding="utf-8")
    out = []
    for anchor, base in (("p3-2", 0), ("p3-3", 11)):
        seg = _section_by_id(merged, anchor)
        for block in extract_mod_blocks(seg):
            tm = re.search(r'class="t">(.*?)</span>', block)
            if not tm:
                continue
            title = text_of(tm.group(1))
            nums = []
            for part in re.split(r"[｜|]", title):
                mm = re.match(r"^([一二三四五六七八九十]+)、", part.strip())
                n = cn2num(mm.group(1)) if mm else None
                if n:
                    nums.append(base + n)
            items = [re.sub(r"^(了解|理解|掌握|熟悉)", "", text_of(li))
                     for li in re.findall(r"<li[^>]*>(.*?)</li>", block, re.S)]
            items = [i for i in items if len(i) >= 4]
            if nums and items:
                out.append((nums, title, items))
    return out


def split_items(text: str) -> list[str]:
    parts = re.split(r"[；;。]", re.sub(r"（[^）]*）", "", text))
    return [p for p in (x.strip() for x in parts) if len(p) >= 4]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", choices=["812", "315", "101"])
    ap.add_argument("--threshold", type=float, default=0.55)
    args = ap.parse_args()

    content = json.loads((ROOT / "content/content.json").read_text(encoding="utf-8"))
    report = []

    if not args.subject or args.subject == "812":
        corpus = chapter_corpus(content, "812")
        # 812 考纲章节顺序 = content.json 章节顺序（00 绪论…11 逆境）; 机制点参与语料
        syl = items_812()
        # 顺序映射：绪论→812-00, 第一章→812-01 ...
        order = ["812-00"] + [f"812-{i:02d}" for i in range(1, 12)]
        gaps = 0
        total = 0
        for idx, (title, body) in enumerate(syl.items()):
            cid = order[idx] if idx < len(order) else None
            c = corpus.get(cid)
            if not c:
                continue
            for item in split_items(body):
                total += 1
                cov = coverage(item, c["corpus"], args.threshold)
                if cov < args.threshold:
                    gaps += 1
                    report.append(f"[812 {cid}] 覆盖 {cov:.0%} · {item[:60]}")
        print(f"== 812：大纲条目 {total} · 疑似缺口 {gaps}")

    if not args.subject or args.subject == "315":
        corpus = chapter_corpus(content, "315")
        syl = items_315()
        covered_chapters = {n for nums, _, _ in syl for n in nums}
        missing = [n for n in range(1, 27) if n not in covered_chapters]
        if missing:
            report.append(f"[315 ?] 大纲清单未覆盖章节号: {missing}")
        total = gaps = 0
        for nums, title, items in syl:
            cids = [f"315-{n:02d}" for n in nums]
            joined = "".join(corpus[c]["corpus"] for c in cids)
            names = "＋".join(corpus[c]["name"][:8] for c in cids)
            for item in items:
                total += 1
                cov = coverage(item, joined, args.threshold)
                if cov < args.threshold:
                    gaps += 1
                    report.append(f"[315 {','.join(cids)} {title[:16]}] 覆盖 {cov:.0%} · {item[:70]}")
            print(f"   315 {','.join(cids)} {names:24s} 条目 {len(items):>2}")
        print(f"== 315：大纲条目 {total} · 疑似缺口 {gaps}")

    if not args.subject or args.subject == "101":
        s = next(x for x in content["subjects"] if x["id"] == "101")
        mods = {}
        for ch in s["chapters"]:
            mod = (ch.get("tags") or ["?"])[0]
            mods[mod] = mods.get(mod, 0) + 1
        print(f"== 101：模块分布 {mods}（官方模块级口径，按模块清单定性核对）")

    print("\n---- 疑似缺口明细（低于阈值，需人工复核）----")
    for line in report[:80]:
        print(" ", line)
    if len(report) > 80:
        print(f"  …共 {len(report)} 条")


if __name__ == "__main__":
    sys.exit(main())
