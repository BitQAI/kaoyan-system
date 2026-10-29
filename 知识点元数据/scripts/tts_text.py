"""把卡片文本转成适合 TTS 朗读的口语文本（纯规则，不做语义改写）。

规则只做「读不出来的字符 → 中文念法」的替换，不改动知识内容；
规则清完后若仍有数学/化学记号，交给 LLM 改写（见 gen_tts_text.py）。
"""
import re

UNITS = [
    ('J·mol⁻¹·K⁻¹', '焦每摩尔每开尔文'),
    ('kJ·mol⁻¹', '千焦每摩尔'),
    ('J·mol⁻¹', '焦每摩尔'),
    ('mol·L⁻¹', '摩尔每升'),
    ('mol·kg⁻¹', '摩尔每千克'),
    ('mol·dm⁻³', '摩尔每立方分米'),
    ('g·mol⁻¹', '克每摩尔'),
    ('g·cm⁻³', '克每立方厘米'),
    ('g·L⁻¹', '克每升'),
    ('kJ·kg⁻¹', '千焦每千克'),
    ('cm³', '立方厘米'),
    ('dm³', '立方分米'),
    ('kJ', '千焦'),
    ('nm', '纳米'),
    ('mL', '毫升'),
    ('kg', '千克'),
    ('℃', '摄氏度'),
    ('°C', '摄氏度'),
]

SYMBOLS = [
    ('⇌', '可逆生成'), ('⇄', '可逆生成'), ('→', '生成'),
    ('↑', '逸出'), ('↓', '沉淀'), ('±', '正负'),
    ('×', '乘'), ('÷', '除以'), ('≈', '约等于'),
    ('≠', '不等于'), ('≤', '小于等于'), ('≥', '大于等于'),
    ('～', '到'), ('~', '到'), ('％', '百分之'), ('%', '百分之'),
]

CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩'
ORDINALS = ['第一', '第二', '第三', '第四', '第五', '第六', '第七', '第八', '第九', '第十']

SUB = str.maketrans('₀₁₂₃₄₅₆₇₈₉', '0123456789')
SUP = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹', '0123456789')

# 规则清完后仍出现这些字符，说明需要语义改写
HARD = re.compile(
    r'[Δ⇌⇄→↑↓±√∑∫≈≠≤≥°⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺₀-₉αβγλμσθπφωΨϕ]'
    r'|[A-Za-z]\s*=\s*[-−\d]'
    r'|\d\s*=\s*[-−\d]'
)


def _ordinals(text):
    def rep(m):
        i = CIRCLED.index(m.group(0))
        return f'{ORDINALS[i]}，'
    return re.sub(f'[{CIRCLED}]', rep, text)


def _exponents(text):
    return re.sub(r'10([⁰¹²³⁴⁵⁶⁷⁸⁹]+)',
                  lambda m: '10的' + m.group(1).translate(SUP) + '次方', text)


def clean(text):
    t = (text or '').strip()
    if not t:
        return ''
    t = _exponents(t)
    for a, b in UNITS:
        t = t.replace(a, b)
    for a, b in SYMBOLS:
        t = t.replace(a, b)
    t = re.sub(r'_{2,}', '，', t)
    t = re.sub(r'[（(]\s*[）)]', '，', t)
    t = _ordinals(t)
    t = t.translate(SUB).translate(SUP)
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'。\s*。', '。', t)
    t = re.sub(r'，\s*，', '，', t)
    t = re.sub(r'。\s*，', '。', t)
    t = re.sub(r'^[，。]+', '', t)
    return t.strip()


def needs_rewrite(text):
    return bool(HARD.search(text or ''))


def option_text(letter, options):
    """选择题：把选项里的正确项取出来，去掉字母前缀。"""
    for opt in options or []:
        s = str(opt).strip()
        if s[:1].upper() == letter:
            return re.sub(r'^[A-Da-d][.．、)）:：]\s*', '', s)
    return ''


def spoken_text(card):
    """卡片 → 朗读文本：考点 + 作答（与前端「听」页同一顺序）。"""
    q = clean(card.get('question'))
    a = clean(card.get('answer'))
    if card.get('kind') == '选择':
        letter = (card.get('answer') or '').strip()[:1].upper()
        opt = option_text(letter, card.get('options'))
        if letter and opt:
            a = f'正确答案是{letter}。{opt}'
    if not q:
        return a
    if q[-1] in '。？！；：':
        return f'{q}{a}'
    return f'{q}。{a}'
