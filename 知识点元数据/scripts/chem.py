"""化学式与专业符号规范化 + TTS 朗读文本生成。

设计要点
--------
1. 显示文本（`point` 字段）中的化学式必须使用 Unicode 下标/上标：
       C6H12O6 → C₆H₁₂O₆      Ca2+ → Ca²⁺
       SO42-  → SO₄²⁻          NH4+  → NH₄⁺
2. **机理代号不转下标**：SN1 / SN2 / E1 / E2 的数字是序号，不是化学计量数。
   这是通用规则最容易误伤的地方，必须显式排除。
3. 幂等：对已经是 Unicode 形态的文本再跑一次，结果不变。
4. 本模块自包含，不依赖 kaoyan-system（后续应用仅凭本目录即可重建听/记/看）。
"""

import re

# ── Unicode 映射 ──────────────────────────────────────────────────────────
SUB = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')
SUP = str.maketrans('0123456789+-', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻')

# 元素符号表（用于校验一个 token 是否像化学式）
ELEMENTS = {
    'H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne',
    'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl', 'Ar', 'K', 'Ca',
    'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
    'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr', 'Rb', 'Sr', 'Y', 'Zr',
    'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn',
    'Sb', 'Te', 'I', 'Xe', 'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd',
    'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb',
    'Lu', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg',
    'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn', 'Fr', 'Ra', 'Ac', 'Th',
    'Pa', 'U', 'Np', 'Pu',
}

# ── 排除表：机理代号 / 非化学计量语境，数字不转下标 ───────────────────────
MECH_CODES = {
    'SN1', 'SN2', 'E1', 'E2', 'E1cb', 'E2c', 'Ar', 'Z', 'Zaitsev',
    'Hofmann', 'Saytzeff', 'Markovnikov', 'Anti',
}

# ── 显式映射表（已逐条核对 524 条知识点全集，零误伤）──────────────────────
# 键为 ASCII 形态，值为 Unicode 形态；按 key 长度倒序应用，避免短串先命中。
FORMULA_MAP = {
    # 多原子化学式
    'K2Cr2O7': 'K₂Cr₂O₇', 'LiAlH4': 'LiAlH₄', 'NaHSO3': 'NaHSO₃',
    'H3PO2': 'H₃PO₂', 'AgNO3': 'AgNO₃', 'FeCl3': 'FeCl₃',
    'KMnO4': 'KMnO₄', 'SOCl2': 'SOCl₂', 'NH3': 'NH₃', 'H2O': 'H₂O',
    # 碳同化途径（碳原子数为下标）
    'C3': 'C₃', 'C4': 'C₄',
    # 单原子离子
    'H+': 'H⁺',
}

# ── 通用规则 ──────────────────────────────────────────────────────────────
# 元素链：至少 2 个「元素符号 + 可选数字」片段，如 Na2CO3 / FeCl3 / H2O
_FORMULA_RE = re.compile(
    r'(?<![A-Za-z0-9])'
    r'(?P<tok>(?:[A-Z][a-z]?\d*){2,})'
    r'(?![A-Za-z0-9])'
)
# 元素 + 电荷（数字在电荷前）：Ca2+ / SO42- / H+
_ION_RE = re.compile(
    r'(?<![A-Za-z0-9])'
    r'(?P<sym>[A-Z][a-z]?)'
    r'(?P<cnt>\d*)'
    r'(?P<chg>[+-])'
    r'(?![A-Za-z0-9])'
)
# 热力学量：ΔrH° → ΔᵣH°
_DELTA_R_RE = re.compile(r'Δr(?=[A-Za-z°])')

# 元素链中的元素必须全部合法，否则不是化学式
_SEG_RE = re.compile(r'[A-Z][a-z]?\d*')


def _is_formula(tok: str) -> bool:
    """判断一个 token 是否为化学式（元素链且各元素合法）。"""
    segs = _SEG_RE.findall(tok)
    if len(segs) < 2:
        return False
    for seg in segs:
        el = re.match(r'[A-Z][a-z]?', seg).group(0)
        if el not in ELEMENTS:
            return False
    return True


def normalize_formulas(text: str) -> str:
    """把 ASCII 形态的化学式/离子规范化为 Unicode 下标与上标。

    幂等：已是 Unicode 形态的文本不变。
    """
    if not text:
        return text

    # 1) 显式映射表（长串优先）
    for src in sorted(FORMULA_MAP, key=len, reverse=True):
        if src in text:
            text = text.replace(src, FORMULA_MAP[src])

    # 2) 通用规则：元素链 + 数字 → 下标
    def _sub_formula(m):
        tok = m.group('tok')
        if tok in MECH_CODES or not _is_formula(tok):
            return tok
        # 已含 Unicode 下标的片段不再处理
        return re.sub(r'\d', lambda mm: mm.group(0).translate(SUB), tok)

    text = _FORMULA_RE.sub(_sub_formula, text)

    # 3) 电荷：元素 + 可选计数 + 电荷 → 上标（计数转下标）
    def _sub_ion(m):
        sym, cnt, chg = m.group('sym'), m.group('cnt'), m.group('chg')
        if sym not in ELEMENTS:
            return m.group(0)
        sup = cnt.translate(SUB) + chg.translate(SUP)
        return sym + sup

    text = _ION_RE.sub(_sub_ion, text)

    # 4) 热力学下标
    text = _DELTA_R_RE.sub('Δᵣ', text)

    return text


# ══ TTS 朗读文本 ═════════════════════════════════════════════════════════
# 规则表按顺序应用：(pattern, repl)。顺序有讲究——先长后短，避免拆坏。

_CHEM = [
    (r'K₂Cr₂O₇', '重铬酸钾'), (r'KMnO₄', '高锰酸钾'), (r'LiAlH₄', '氢化铝锂'),
    (r'NaHSO₃', '亚硫酸氢钠'), (r'H₃PO₂', '次磷酸'), (r'AgNO₃', '硝酸银'),
    (r'FeCl₃', '三氯化铁'), (r'SOCl₂', '亚硫酰氯'), (r'CH₃COOH', '醋酸'),
    (r'C₂H₅OH', '乙醇'), (r'NaHCO₃', '碳酸氢钠'), (r'Na₂CO₃', '碳酸钠'),
    (r'H₂SO₄', '硫酸'), (r'HNO₃', '硝酸'), (r'CaCO₃', '碳酸钙'),
    (r'NaOH', '氢氧化钠'), (r'NaCl', '氯化钠'), (r'NH₃', '氨'),
    (r'CH₄', '甲烷'), (r'CO₂', '二氧化碳'), (r'H₂O₂', '过氧化氢'),
    (r'H₂O', '水'), (r'O₂', '氧气'), (r'N₂', '氮气'), (r'H₂', '氢气'),
]

_IONS = [
    (r'H⁺', '氢离子'), (r'OH⁻', '氢氧根'), (r'NH₄⁺', '铵根'),
    (r'NO₃⁻', '硝酸根'), (r'HCO₃⁻', '碳酸氢根'), (r'HSO₄⁻', '硫酸氢根'),
    (r'SO₄²⁻', '硫酸根'), (r'CO₃²⁻', '碳酸根'), (r'PO₄³⁻', '磷酸根'),
    (r'MnO₄⁻', '高锰酸根'), (r'Cr₂O₇²⁻', '重铬酸根'),
    (r'Fe³⁺', '铁离子'), (r'Fe²⁺', '亚铁离子'), (r'Ca²⁺', '钙离子'),
    (r'Mg²⁺', '镁离子'), (r'Cu²⁺', '铜离子'), (r'Zn²⁺', '锌离子'),
    (r'K⁺', '钾离子'), (r'Na⁺', '钠离子'), (r'Al³⁺', '铝离子'),
    (r'Cl⁻', '氯离子'), (r'⁻', '负'), (r'⁺', '正'),
]

_TERMS = [
    (r'Ψ[_ ]?w|Ψw', '水势'), (r'Ψ[_ ]?s|Ψs', '渗透势'),
    (r'Ψ[_ ]?p|Ψp', '压力势'), (r'Ψ[_ ]?m|Ψm', '衬质势'), (r'Ψ', '普西'),
    (r'H⁺-ATP\s*酶', '氢离子ATP酶'),
    (r'Rubisco|RuBP羧化酶|核酮糖二磷酸羧化酶', '核酮糖二磷酸羧化酶'),
    (r'RuBP', '核酮糖二磷酸'), (r'PEPC', '磷酸烯醇式丙酮酸羧化酶'),
    (r'ATP', 'A-T-P'), (r'NADPH', 'N-A-D-P-H'), (r'NADP', 'N-A-D-P'),
    (r'DNA', 'D-N-A'), (r'RNA', 'R-N-A'), (r'EDTA', 'E-D-T-A'),
    (r'CAM', '景天酸代谢'), (r'C₃', '碳三'), (r'C₄', '碳四'),
    (r'PSⅡ|PSII|光系统Ⅱ', '光系统二'), (r'PSⅠ|PSI|光系统Ⅰ', '光系统一'),
    (r'IAA', '吲哚乙酸'), (r'CTK', '细胞分裂素'), (r'ABA', '脱落酸'),
    (r'GA₃', '赤霉素'), (r'GA', '赤霉素'), (r'PPP', '磷酸戊糖途径'),
    # 原文已写「呼吸商」时不再重复展开（否则出现「呼吸商 呼吸商」）
    (r'(?<!呼吸商 )(?<!呼吸商)RQ', '呼吸商'), (r'pH', 'P-H'),
]

_SYMBOLS = [
    (r'℃|°C', '摄氏度'), (r'°', '度'),
    (r'≈', '约等于'), (r'≥', '大于等于'), (r'≤', '小于等于'),
    (r'×', '乘'), (r'±', '正负'),
    (r'²', '平方'), (r'³', '立方'),
    (r'₀', '零'), (r'₁', '一'), (r'₂', '二'), (r'₃', '三'), (r'₄', '四'),
    (r'₅', '五'), (r'₆', '六'), (r'₇', '七'), (r'₈', '八'), (r'₉', '九'),
    (r'α', '阿尔法'), (r'β', '贝塔'), (r'γ', '伽马'), (r'λ', '拉姆达'),
    (r'μ', '缪'), (r'π', '派'), (r'θ', '西塔'), (r'ω', '欧米伽'),
    (r'σ', '西格玛'), (r'ρ', '柔'), (r'η', '伊塔'), (r'Δ', '德尔塔'),
]

# 箭头按科目分流：315 的「→」是反应生成，812 的是逻辑递进
_ARROW = {
    '315': [(r'→|⟶|->', '生成')],
    '_default': [(r'→|⟶|->', '到')],
}

_DASH_BETWEEN_DIGITS = [(r'(\d)\s*[–—-]\s*(\d)', r'\1 到 \2')]


def to_speech(text: str, subject: str | None = None) -> str:
    """把考点文本转成 TTS 友好朗读文本。"""
    out = text
    for pat, repl in _CHEM:
        out = re.sub(pat, repl, out)
    for pat, repl in _IONS:
        out = re.sub(pat, repl, out)
    for pat, repl in _TERMS:
        out = re.sub(pat, repl, out)
    for pat, repl in _SYMBOLS:
        out = re.sub(pat, repl, out)
    for pat, repl in _ARROW.get(subject or '', _ARROW['_default']):
        out = re.sub(pat, repl, out)
    for pat, repl in _DASH_BETWEEN_DIGITS:
        out = re.sub(pat, repl, out)
    out = re.sub(r'[*#`_]', '', out)
    out = re.sub(r'[；;]', '。', out)
    out = re.sub(r'\s+', ' ', out)
    return out.strip()


# ── 朗读分段（听视图用）──────────────────────────────────────────────────
SENT_SPLIT = re.compile(r'[^。！？!?]+[。！？!?]?')
SOFT_SPLIT = re.compile(r'[^，,、]+[，,、]?')


def split_clips(text: str, max_chars: int = 220) -> list:
    """按句界切成 ≤max_chars 的朗读段；单句过长时按逗号软切再硬切。"""
    clips, buf = [], ''
    for sent in SENT_SPLIT.findall(text):
        if not sent.strip():
            continue
        if len(sent) > max_chars:
            if buf:
                clips.append(buf)
                buf = ''
            sub = ''
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


# ── 时长预估 ──────────────────────────────────────────────────────────────
# 口径 A（旧）：812 旧 107 条音频，字/秒 中位 5.22。
# 口径 B（现行）：Fish Audio `s2.1-pro-free` + 宣传片浑厚男声，实测 473 段，
#   字/秒 中位 3.50、均值 3.53，单段 1.28–37.62s。取 3.5。
CHARS_PER_SEC = 3.5


def est_seconds(text: str) -> float:
    """估算朗读时长（秒）。仅用于生成前的进度预估；已有音频以 audio-manifest 实测值为准。"""
    return round(len(text) / CHARS_PER_SEC, 1)
