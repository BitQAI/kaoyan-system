"""口语化：把考点文本转成 TTS 友好的朗读文本（符号/公式/缩写 → 中文读法）。"""
import re

# —— 规则表：按顺序应用，(pattern, repl) 为正则替换 ——
# 1) 化学式/物质（先长后短，避免拆坏）
CHEM = [
    (r"K?MnO₄|KMnO4", "高锰酸钾"),
    (r"K2Cr2O7|K₂Cr₂O₇", "重铬酸钾"),
    (r"CH3COOH|CH₃COOH|HAc", "醋酸"),
    (r"C2H5OH|C₂H₅OH", "乙醇"),
    (r"NaHCO3|NaHCO₃", "碳酸氢钠"),
    (r"Na2CO3|Na₂CO₃", "碳酸钠"),
    (r"H2SO4|H₂SO₄", "硫酸"),
    (r"HNO3|HNO₃", "硝酸"),
    (r"CaCO3|CaCO₃", "碳酸钙"),
    (r"NaOH", "氢氧化钠"),
    (r"NaCl", "氯化钠"),
    (r"NH3|NH₃", "氨"),
    (r"CH4|CH₄", "甲烷"),
    (r"CO2|CO₂", "二氧化碳"),
    (r"H2O2|H₂O₂", "过氧化氢"),
    (r"H2O|H₂O", "水"),
    (r"O2|O₂", "氧气"),
    (r"N2|N₂", "氮气"),
    (r"H2|H₂", "氢气"),
]
# 2) 离子
IONS = [
    (r"H⁺", "氢离子"), (r"OH⁻", "氢氧根"),
    (r"NH4⁺|NH₄⁺", "铵根"), (r"NO3⁻|NO₃⁻", "硝酸根"),
    (r"HCO3⁻|HCO₃⁻", "碳酸氢根"), (r"HSO4⁻|HSO₄⁻", "硫酸氢根"),
    (r"SO4²⁻|SO₄²⁻", "硫酸根"), (r"CO3²⁻|CO₃²⁻", "碳酸根"),
    (r"PO4³⁻|PO₄³⁻", "磷酸根"), (r"MnO4⁻|MnO₄⁻", "高锰酸根"),
    (r"Cr2O7²⁻|Cr₂O₇²⁻", "重铬酸根"),
    (r"Fe³⁺", "铁离子"), (r"Fe²⁺", "亚铁离子"),
    (r"Ca²⁺", "钙离子"), (r"Mg²⁺", "镁离子"), (r"Cu²⁺", "铜离子"), (r"Zn²⁺", "锌离子"),
    (r"K⁺", "钾离子"), (r"Na⁺", "钠离子"), (r"Al³⁺", "铝离子"), (r"Cl⁻", "氯离子"),
    (r"⁻", "负"), (r"⁺", "正"),
]
# 3) 缩写与专有名词
TERMS = [
    (r"Ψ[_ ]?w|Ψw", "水势"), (r"Ψ[_ ]?s|Ψs", "渗透势"),
    (r"Ψ[_ ]?p|Ψp", "压力势"), (r"Ψ[_ ]?m|Ψm", "衬质势"), (r"Ψ", "普西"),
    (r"H⁺-ATP\s*酶|H\+-ATP酶", "氢离子ATP酶"),
    (r"Rubisco|RuBP羧化酶|核酮糖二磷酸羧化酶", "核酮糖二磷酸羧化酶"),
    (r"RuBP", "核酮糖二磷酸"), (r"PEPC", "磷酸烯醇式丙酮酸羧化酶"),
    (r"ATP", "A-T-P"), (r"NADPH", "N-A-D-P-H"), (r"NADP", "N-A-D-P"),
    (r"DNA", "D-N-A"), (r"RNA", "R-N-A"), (r"EDTA", "E-D-T-A"),
    (r"CAM", "景天酸代谢"), (r"C3|C₃", "碳三"), (r"C4|C₄", "碳四"),
    (r"PSⅡ|PSII|光系统Ⅱ", "光系统二"), (r"PSⅠ|PSI|光系统Ⅰ", "光系统一"),
    (r"IAA", "吲哚乙酸"), (r"CTK", "细胞分裂素"), (r"ABA", "脱落酸"),
    (r"GA3|GA₃", "赤霉素"), (r"GA", "赤霉素"), (r"PPP", "磷酸戊糖途径"),
    (r"RQ", "呼吸商"), (r"pH", "P-H"),
]
# 4) 符号
SYMBOLS = [
    (r"℃|°C", "摄氏度"), (r"°", "度"),
    (r"≈", "约等于"), (r"≥", "大于等于"), (r"≤", "小于等于"),
    (r"×", "乘"), (r"±", "正负"),
    (r"²", "平方"), (r"³", "立方"),
    (r"₀", "零"), (r"₁", "一"), (r"₂", "二"), (r"₃", "三"), (r"₄", "四"),
    (r"₅", "五"), (r"₆", "六"), (r"₇", "七"), (r"₈", "八"), (r"₉", "九"),
]
GREEK = [
    (r"Δ", "德尔塔"), (r"α", "阿尔法"), (r"β", "贝塔"), (r"γ", "伽马"),
    (r"λ", "拉姆达"), (r"μ", "缪"), (r"π", "派"), (r"θ", "西塔"),
    (r"ω", "欧米伽"), (r"σ", "西格玛"), (r"ρ", "柔"), (r"η", "伊塔"),
]
ARROW = {
    "315": [(r"→|⟶|->", "生成")],
    "812": [(r"→|⟶|->", "到")],
    "_default": [(r"→|⟶|->", "到")],
}
DASH_BETWEEN_DIGITS = [(r"(\d)\s*[–—-]\s*(\d)", r"\1 到 \2")]


def to_speech(text: str, subject: str | None = None) -> str:
    out = text
    for pat, repl in CHEM:
        out = re.sub(pat, repl, out)
    for pat, repl in IONS:
        out = re.sub(pat, repl, out)
    for pat, repl in TERMS:
        out = re.sub(pat, repl, out)
    for pat, repl in GREEK + SYMBOLS:
        out = re.sub(pat, repl, out)
    for pat, repl in ARROW.get(subject or "", ARROW["_default"]):
        out = re.sub(pat, repl, out)
    for pat, repl in DASH_BETWEEN_DIGITS:
        out = re.sub(pat, repl, out)
    out = re.sub(r"[*#`_]", "", out)
    out = re.sub(r"[；;]", "。", out)
    out = re.sub(r"\s+", " ", out)
    return out.strip()


SENT_SPLIT = re.compile(r"[^。！？!?]+[。！？!?]?")
SOFT_SPLIT = re.compile(r"[^，,、]+[，,、]?")


def split_clips(text: str, max_chars: int = 220) -> list[str]:
    """按句界切成 ≤max_chars 的朗读段；单句过长时按逗号软切再硬切。"""
    clips: list[str] = []
    buf = ""
    for sent in SENT_SPLIT.findall(text):
        if not sent.strip():
            continue
        if len(sent) > max_chars:
            if buf:
                clips.append(buf)
                buf = ""
            sub = ""
            for part in SOFT_SPLIT.findall(sent):
                if len(sub) + len(part) > max_chars:
                    if sub:
                        clips.append(sub)
                    while len(part) > max_chars:
                        clips.append(part[:max_chars])
                        part = part[max_chars:]
                    sub = part
                else:
                    sub += part
            if sub:
                clips.append(sub)
            continue
        if len(buf) + len(sent) > max_chars:
            clips.append(buf)
            buf = sent
        else:
            buf += sent
    if buf:
        clips.append(buf)
    return [c.strip() for c in clips if c.strip()]
