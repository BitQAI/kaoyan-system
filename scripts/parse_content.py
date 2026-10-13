#!/usr/bin/env python3
"""四科全景 HTML → content.json 骨架（考点句切分 + 口语化 + 权重挂载）。

用法：python scripts/parse_content.py [--merged PATH] [--out PATH] [--subject 812 ...]
"""
import argparse
import datetime
import hashlib
import html as html_mod
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts.normalize import to_speech  # noqa: E402

DEFAULT_MERGED = "../master_eaxm/2027考研_四科知识全景与章节权重.html"
DEFAULT_OUT = "content/content.json"

TIER_NUM = {"第一梯队": 1, "第二梯队": 2, "第三梯队": 3}


def text_of(frag: str) -> str:
    frag = re.sub(r"<br\s*/?>", " ", frag)
    frag = re.sub(r"<[^>]+>", "", frag)
    return re.sub(r"\s+", " ", html_mod.unescape(frag)).strip()


def section(html: str, anchor: str) -> str:
    i = html.find(f'<section class="section" id="{anchor}"')
    if i < 0:
        raise SystemExit(f"缺少 section {anchor}")
    j = html.find('<section class="section" id="', i + 10)
    return html[i:j]


def split_points(text: str, chap_id: str, subject: str) -> list[dict]:
    merged: list[str] = []
    for raw in [p.strip() for p in re.split(r"[；;]", text) if p.strip()]:
        if merged and len(raw) < 5:          # 碎片（如"总任务"）并入前一点
            merged[-1] = merged[-1] + "；" + raw
        else:
            merged.append(raw)
    pts = []
    for i, raw in enumerate(merged, 1):
        pts.append({
            "id": f"{chap_id}-{i:02d}",
            "text": raw,
            "spoken": to_speech(raw, subject=subject),
            "tags": [], "listen_ok": True, "media": [], "audio": [],
        })
    return pts


def parse_812(html: str) -> dict:
    sec = section(html, "p4-2")
    cards = [c for c in re.split(r'(?=<div class="chapter">)', sec) if c.lstrip().startswith('<div class="chapter">')]
    chapters = []
    for idx, card in enumerate(cards):
        title = text_of(re.search(r"<h3>(.*?)</h3>", card, re.S).group(1))
        m_w = re.search(r'class="w">\s*(\d+)\s*分', card)
        small = re.search(r'<p class="small">(.*?)</p>', card, re.S)
        small_txt = text_of(small.group(1)) if small else ""
        m_rng = re.search(r"区间\s*([\d.]+)[–\-—~至]+([\d.]+)", small_txt)
        m_tier = re.search(r"(第[一二三]梯队)", small_txt)
        main = re.search(r'<p>(.*?)</p>', card, re.S)
        mech = re.search(r'<p class="mech">(.*?)</p>', card, re.S)
        tags = [text_of(t) for t in re.findall(r'class="tag[^"]*">(.*?)</span>', card)]
        chap_id = f"812-{idx:02d}"
        body = text_of(main.group(1)) if main else ""
        points = split_points(body, chap_id, "812")
        if mech:
            points.append({"id": f"{chap_id}-m1", "text": text_of(mech.group(1)),
                           "spoken": to_speech(text_of(mech.group(1)), subject="812"),
                           "tags": ["机制"], "listen_ok": True, "media": [], "audio": []})
        chapters.append({
            "id": chap_id, "name": title,
            "tier": TIER_NUM.get(m_tier.group(1) if m_tier else "", 3),
            "weight_center": int(m_w.group(1)) if m_w else 0,
            "weight_range": [float(m_rng.group(1)), float(m_rng.group(2))] if m_rng else None,
            "tags": tags, "points": points, "quiz": [], "cards": [],
        })
    return {"id": "812", "name": "植物生理学", "score": 150, "has_content": True, "chapters": chapters}


def parse_315_weights(html: str) -> dict:
    """从 p3-5 报告的「各章权重总表」取 {章节名: (中心, 区间, 梯队)}。"""
    sec = section(html, "p3-5")
    tables = re.findall(r"<table[^>]*>(.*?)</table>", sec, re.S)
    target = None
    for t in tables:
        if "权重中心" in t and "梯队" in t and len(re.findall(r"<tr[^>]*>", t)) >= 20:
            target = t
            break
    if target is None:
        raise SystemExit("p3-5 未找到 26 章权重总表")
    out = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", target, re.S):
        cells = [text_of(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 7 or cells[0] == "章节" or cells[0].startswith("合计"):
            continue
        name, _block, _cnt, _pct, center, rng, tier = cells[:7]
        m_rng = re.search(r"([\d.]+)\s*[–\-—~至]\s*([\d.]+)", rng)
        out[re.sub(r"\s+", "", name)] = {
            "center": float(center) if center else 0,
            "range": [float(m_rng.group(1)), float(m_rng.group(2))] if m_rng else None,
            "tier": TIER_NUM.get(tier, 3),
        }
    return out


def parse_315(html: str) -> dict:
    sec = section(html, "p3-4")
    i = sec.find("A. 315")
    j = sec.find("<h2", i + 10)
    block = sec[i:j if j > i else len(sec)]
    weights = parse_315_weights(html)
    chapters = []
    for idx, ch in enumerate([c for c in re.split(r"(?=<h3)", block) if c.lstrip().startswith("<h3")], 1):
        title = text_of(re.search(r"<h3>(.*?)</h3>", ch, re.S).group(1))
        m_p = re.search(r"<p>(.*?)</p>", ch, re.S)
        chap_id = f"315-{idx:02d}"
        name_key = re.sub(r"\s+", "", title)
        w = weights.get(name_key, {})
        if not w:
            # 容错：前缀匹配（总表名可能含"有机化学第X章"前缀差异）
            for k, v in weights.items():
                if k.endswith(name_key) or name_key.endswith(k):
                    w = v
                    break
        chapters.append({
            "id": chap_id, "name": title, "tier": w.get("tier", 3),
            "weight_center": w.get("center", 0), "weight_range": w.get("range"),
            "tags": [], "points": split_points(text_of(m_p.group(1)) if m_p else "", chap_id, "315"),
            "quiz": [], "cards": [],
        })
    return {"id": "315", "name": "315 化学（农）", "score": 150, "has_content": True, "chapters": chapters}


MODULES_101 = [
    ("马原", "马原", 22), ("毛中特", "毛中特", 13),
    ("习近平", "习概", 22), ("新思想", "习概", 22),
    ("史纲", "史纲", 15), ("思修", "思修法治", 15), ("形势与政策", "时政当代", 13),
]


def module_of(title: str):
    for prefix, name, weight in MODULES_101:
        if title.startswith(prefix):
            return name, weight
    return "其他", 0


def parse_101(html: str) -> dict:
    sec = section(html, "p1-4")
    i = sec.find("B. 101")
    j = sec.find("<h2", i + 10)
    block = sec[i:j if j > i else len(sec)]
    groups = [g for g in re.split(r"(?=<h3)", block) if g.lstrip().startswith("<h3")]
    mods: dict[str, list] = {}
    parsed = []
    for g in groups:
        title = text_of(re.search(r"<h3>(.*?)</h3>", g, re.S).group(1))
        m_p = re.search(r"<p>(.*?)</p>", g, re.S)
        mod_name, mod_w = module_of(title)
        mods.setdefault(mod_name, []).append((title, text_of(m_p.group(1)) if m_p else ""))
        parsed.append((mod_name, mod_w, title, text_of(m_p.group(1)) if m_p else ""))
    chapters = []
    for idx, (mod_name, mod_w, title, body) in enumerate(parsed, 1):
        count = len(mods[mod_name]) or 1
        chap_id = f"101-{idx:02d}"
        chapters.append({
            "id": chap_id, "name": title,
            "tier": 1 if mod_w >= 22 else (2 if mod_w >= 15 else 3),
            "weight_center": round(mod_w / count, 2), "weight_range": None,
            "tags": [mod_name],
            "points": split_points(body, chap_id, "101"), "quiz": [], "cards": [],
        })
    return {"id": "101", "name": "思想政治理论", "score": 100, "has_content": True, "chapters": chapters}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", default=DEFAULT_MERGED)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--subject", action="append", default=None)
    args = ap.parse_args()

    merged = pathlib.Path(args.merged).read_text(encoding="utf-8")
    subjects = [parse_812(merged)]
    subjects.append(parse_315(merged))
    subjects.append(parse_101(merged))
    subjects.append({"id": "204", "name": "英语（二）", "score": 100,
                     "has_content": False, "chapters": []})

    if args.subject:
        keep = set(args.subject)
        subjects = [s for s in subjects if s["id"] in keep or s["id"] == "204"]

    version = hashlib.md5((merged + "|v1").encode()).hexdigest()[:10]
    content = {
        "version": version,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "subjects": subjects,
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")

    for s in subjects:
        pts = sum(len(c["points"]) for c in s["chapters"])
        ws = sum(c["weight_center"] for c in s["chapters"])
        print(f"{s['id']:>3}  {s['name'][:12]:14s} 章节 {len(s['chapters']):>2}  考点 {pts:>3}  权重中心合计 {ws}")
    print(f"version={version} → {out}")


if __name__ == "__main__":
    main()
