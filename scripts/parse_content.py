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


# 204 英语（二）：复习型科目，无音频。章节/考点依据两份调研 HTML：
# ① 《…204英语二…大纲深度调研_V2.html》§2.1-2.5（题型结构/能力要求/得分点/阅读考点/写作评分点）
# ② 《四科知识全景》p2-1..p2-7（语法句法清单/词汇清单/写作清单/阅读翻译长难句/大纲变化）
# 结构为人工整理（源为表格，非考点句列表），后续如需调整直接改本表并由 sync_204 应用。
CHAPTERS_204 = [
    ("204-01", "考试结构与得分策略", 3, 4, [
        "试卷结构与分值分布（完形 10 + 阅读 A 40 + 阅读 B 10 + 翻译 15 + 写作 25）",
        "考试时间分配与做题顺序（180 分钟：阅读 → 写作 → 翻译 → 完形）",
        "基础阶段的投入重点（高频词汇循环 + 真题长难句拆解 + 阅读证据定位 + 小作文框架）",
        "大纲阅读能力八项要求（主旨/细节/词义/推理/态度/结构/修辞/比较）",
        "得分底线策略：阅读与写作合计 75 分，先保住优势题型",
    ]),
    ("204-02", "词汇与语法基础", 1, 12, [
        "5500 词的分层记忆法（核心词 → 熟词僻义 → 高频搭配）",
        "熟词僻义与一词多义（如 address 处理、subject 使遭受）",
        "固定搭配与介词搭配（动词 + 介词、形容词 + 介词）",
        "构词法：前缀、后缀与词根（否定前缀、-tion/-ment 名词化）",
        "长难句主干识别：主谓宾 + 从句 + 非谓语",
        "动词时态高频考点（一般过去时、过去完成时、现在完成时）",
        "非谓语动词三大形式（to do / doing / done 的句法功能）",
        "被动语态与含情态动词的被动（翻译与写作均高频）",
        "虚拟语气与从句时态呼应",
        "从句与连接词：定语从句、状语从句、名词性从句",
    ]),
    ("204-03", "完形填空", 2, 10, [
        "完形题型与考查逻辑（语境词汇、固定搭配、逻辑衔接）",
        "上下文语境定位法：先通读抓主线再逐空",
        "逻辑关系词：转折、因果、让步、并列、递进",
        "动词辨析与介词搭配高频考法",
        "完形做题步骤与时间控制（15-18 分钟）",
    ]),
    ("204-04", "阅读 A · 题型与解法", 1, 20, [
        "阅读六大题型：主旨、细节、推理、词义、态度、例证",
        "主旨题解法：首末段 + 高频复现词 + 段落功能",
        "细节题：题干定位词 + 原文同义替换",
        "推理判断题：基于原文一步推理，不过度引申",
        "词义猜测题：上下文线索（定义、举例、对比）",
        "作者态度题：评价性形容词与转折后的立场",
        "例证题与段落功能题：例子服务于什么观点",
        "干扰项特征：偷换概念、无中生有、绝对化、张冠李戴",
    ]),
    ("204-05", "阅读 A · 真题精读实战", 1, 20, [
        "精读流程：限时做题 → 逐句翻译 → 错因归类 → 生词入卡",
        "题干—原文定位句对应表的建立",
        "错误选项逐一还原：命题人如何设置干扰",
        "长难句在真题语境中的拆解训练",
        "阅读速度与证据意识：不靠常识靠原文",
    ]),
    ("204-06", "阅读理解 B（新题型）", 2, 10, [
        "新题型形式：小标题匹配、段落匹配（备选择一）",
        "小标题匹配解题步骤：找段落主题句与关键词复现",
        "段落匹配与过渡句：首末句、代词指代、逻辑词",
        "篇章结构信号词与选项排除法",
    ]),
    ("204-07", "翻译（英译汉）", 2, 15, [
        "翻译评分标准：准确、完整、通顺",
        "拆句三步法：找主干 → 理修饰 → 重组中文语序",
        "定语从句翻译（前置合译与后置分译）",
        "被动句翻译：意译为主、变主动",
        "代词指代还原与逻辑词显化",
    ]),
    ("204-08", "写作 A（应用文）", 2, 10, [
        "应用文五要素：格式、称谓、目的、主体内容、结尾",
        "书信类模板与常用句式（建议信、感谢信、邀请信）",
        "通知与告示的格式与语气",
        "应用文常见失分点：任务未完成、格式错误、语气不当",
    ]),
    ("204-09", "写作 B（短文）", 2, 15, [
        "图表/图画作文三段式结构：描述 → 解释 → 总结",
        "描述段：数据趋势与图表常用表达",
        "原因分析段：因果链与例证句型",
        "结论段与观点表达（提出建议、展望）",
        "写作评分点与提分优先级：先正确再丰富",
    ]),
]


def parse_204() -> dict:
    chapters = []
    for chap_id, name, tier, weight, texts in CHAPTERS_204:
        points = [{
            "id": f"{chap_id}-{i:02d}", "text": t, "spoken": t,
            "tags": [], "listen_ok": False, "media": [], "audio": [],
        } for i, t in enumerate(texts, 1)]
        chapters.append({
            "id": chap_id, "name": name, "tier": tier,
            "weight_center": weight, "weight_range": None, "tags": ["英语二"],
            "points": points, "quiz": [], "cards": [], "listen": [],
        })
    return {"id": "204", "name": "英语（二）", "score": 100, "has_content": True,
            "chapters": chapters}


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
    subjects.append(parse_204())

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
