"""媒体配置：结构式 SMILES / 数据图表 / 人工挑选的静态图。

点 ID 依据 content/content.json 的实际编号；新增媒体在此登记。
"""
from content import charts_101, charts_basic, charts_misc  # noqa: E402

# 101 政治：结构图/时间线标题（draw 来自 charts_101.FIGURES）
TITLES_101 = {
    "101-01-01": "马克思主义的三个组成部分与理论来源",
    "101-02-12": "唯物辩证法三大规律",
    "101-03-04": "认识运动的总公式（两次飞跃）",
    "101-04-04": "社会基本矛盾运动",
    "101-05-01": "商品二因素与劳动二重性",
    "101-06-01": "垄断资本主义的五大经济特征",
    "101-07-01": "社会主义从空想到科学",
    "101-08-01": "共产主义社会的基本特征",
    "101-09-01": "马克思主义中国化的理论成果演进",
    "101-10-02": "毛泽东思想活的灵魂",
    "101-11-02": "新民主主义革命总路线",
    "101-12-02": "社会主义改造的基本路径",
    "101-13-02": "两类不同性质的矛盾与处理方法",
    "101-14-01": "中国特色社会主义理论体系的形成",
    "101-15-02": "习近平新时代中国特色社会主义思想的核心内容",
    "101-16-02": "“五位一体”总体布局与“四个全面”战略布局",
    "101-17-02": "中国式现代化的中国特色",
    "101-18-01": "党的领导、人民中心与改革开放的内在联系",
    "101-19-01": "新发展理念及其内在联系",
    "101-20-01": "全过程人民民主的五个环节",
    "101-21-01": "总体国家安全观的要素结构",
    "101-23-01": "新民主主义革命时期关键节点",
    "101-24-03": "新中国与新时代关键节点",
    "101-25-01": "人生观的三要素",
    "101-26-09": "依法治国与以德治国的关系",
    "101-27-02": "中国特色大国外交与三大全球倡议",
}

# 315 有机化学结构式（RDKit 渲染）
STRUCTURES = {
    "315-13-01": "CCC(C)C",                                  # 2-甲基丁烷：伯仲叔季碳示例
    "315-14-01": "C=CC=C",                                   # 1,3-丁二烯：共轭二烯烃
    "315-15-01": "c1ccccc1",                                 # 苯：芳香烃母体
    "315-18-01": "CCO",                                      # 乙醇：醇类代表
    "315-19-01": "CC=O",                                     # 乙醛：醛类代表
    "315-20-01": "CC(=O)O",                                  # 乙酸：羧酸代表
    "315-21-01": "CN",                                       # 甲胺：胺类代表
    "315-23-01": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",  # 葡萄糖（吡喃环）
    # —— V2 扩充：官能团代表与考点挂载 ——
    "315-18-06": "Oc1ccccc1",                                # 苯酚：酚酸性
    "315-20-04": "OC(=O)c1ccccc1",                           # 苯甲酸
    "315-20-07": ["CCOC(=O)C", "CC(=O)OC(=O)C"],             # 乙酸乙酯 / 乙酸酐
    "315-21-03": "CCN",                                      # 乙胺
    "315-20-08": "CC(N)=O",                                  # 乙酰胺
    "315-14-04": "CC=C",                                     # 丙烯（加成底物）
    "315-14-08": "CC#C",                                     # 丙炔
    "315-13-04": "C1CCCCC1",                                 # 环己烷（椅式母体）
    "315-20-09": "CC(O)C(=O)O",                              # 乳酸
    "315-20-10": "OC(=O)CC(O)(CC(=O)O)C(=O)O",               # 柠檬酸
    "315-23-04": ["OCC(=O)[C@@H](O)[C@H](O)[C@@H](O)CO",     # 果糖（开链酮糖）
                   "OC(=O)[C@H](O)[C@@H](O)[C@H](O)[C@@H](O)C=O"],  # 葡萄糖醛酸
    "315-23-05": "OC[C@H]1O[C@H](O[C@H]2O[C@H](CO)[C@@H](O)[C@H](O)[C@H]2O)[C@H](O)[C@@H](O)[C@@H]1O",  # 麦芽糖
    "315-24-01": ["NCC(=O)O", "NC(CS)C(=O)O"],               # 甘氨酸 / 半胱氨酸
    "315-22-01": ["c1ccc2[nH]ccc2c1", "c1ccncc1", "c1cncnc1", "c1ccc2ncccc2c1"],  # 吲哚/吡啶/嘧啶/喹啉
    # 脂类（315-25）：甘油三酯代表
    "315-25-01": [
        "CCCCCCCCCCCCCCCCCC(=O)OCC(COC(=O)CCCCCCCCCCCCCCCCC)OC(=O)CCCCCCCCCCCCCCCCC",  # 三硬脂酸甘油酯
        "CCCCCCCCC=CCCCCCCCC(=O)OCC(COC(=O)CCCCCCCC=CCCCCCCCC)OC(=O)CCCCCCCC=CCCCCCCCC",  # 三油酸甘油酯
    ],
}
STRUCTURES_CAPTION = {
    "315-13-01": "2-甲基丁烷（伯、仲、叔、季碳标注示例）",
    "315-14-01": "1,3-丁二烯（共轭双键）",
    "315-15-01": "苯环（凯库勒式对应结构）",
    "315-18-01": "乙醇",
    "315-19-01": "乙醛",
    "315-20-01": "乙酸",
    "315-21-01": "甲胺",
    "315-23-01": "葡萄糖（吡喃环构型）",
    "315-18-06": "苯酚（酚羟基连苯环，酸性强于醇）",
    "315-20-04": "苯甲酸",
    "315-20-07": ["乙酸乙酯", "乙酸酐（两分子乙酸脱水产物）"],
    "315-21-03": "乙胺",
    "315-20-08": "乙酰胺",
    "315-14-04": "丙烯（加成反应底物）",
    "315-14-08": "丙炔（三键加成与金属炔化物）",
    "315-13-04": "环己烷（椅式构象母体）",
    "315-20-09": "乳酸（α-羟基酸）",
    "315-20-10": "柠檬酸（三元羧酸、α-羟基酸脱水代表）",
    "315-23-04": ["果糖（开链式，酮糖）", "葡萄糖醛酸（葡萄糖 C6 氧化产物）"],
    "315-23-05": "麦芽糖（α-1,4-苷键，还原性二糖）",
    "315-24-01": ["甘氨酸（最简单α-氨基酸）", "半胱氨酸（含巯基，可形成二硫键）"],
    "315-22-01": ["吲哚（苯并吡咯）", "吡啶（六元含氮杂环）", "嘧啶（二氮六元环）", "喹啉（苯并吡啶）"],
    "315-25-01": ["三硬脂酸甘油酯（饱和高级脂肪酸甘油酯）",
                  "三油酸甘油酯（含 C=C 的不饱和甘油酯，碘值高）"],
}


def _light_curve(ax):
    xs = list(range(0, 201, 5))
    ys = [0 if x == 0 else 21 * (1 - 2.718 ** (-x / 40)) for x in xs]
    ax.plot(xs, ys, color="#11845b", lw=2)
    ax.axhline(0, color="#c3cbd8", lw=0.8)
    ax.axvline(22, color="#b96a00", lw=1, ls="--")
    ax.annotate("光补偿点", xy=(22, 0), xytext=(40, 3), fontsize=8, color="#b96a00")
    ax.annotate("光饱和点", xy=(120, 20.4), xytext=(118, 14), fontsize=8, color="#2457d6")
    ax.set_ylim(-1, 24)


def _titration_curve(ax):
    ka, ca, va, cb = 1.8e-5, 0.1, 25.0, 0.1
    pka = -__import__("math").log10(ka)
    xs, ys = [], []
    v = 0.0
    while v <= 35.0:
        if v == 0:
            ph = 0.5 * (pka - __import__("math").log10(ca))
        elif v < va:
            nh = cb * v
            ph = pka + __import__("math").log10(nh / max(ca * va - nh, 1e-9))
        elif abs(v - va) < 1e-9:
            c_salt = ca * va / (va + va)
            ph = 0.5 * (14 + pka + __import__("math").log10(c_salt))
        else:
            oh = (cb * v - ca * va) / (v + va)
            ph = 14 + __import__("math").log10(max(oh, 1e-9))
        xs.append(v)
        ys.append(min(ph, 12.5))
        v += 0.5
    ax.plot(xs, ys, color="#2457d6", lw=2)
    ax.axvspan(24.5, 25.5, color="#fff0f0", zorder=0)
    ax.annotate("突跃", xy=(25, 7), xytext=(27, 5), fontsize=8, color="#b33a3a")
    ax.set_ylim(0, 13)


def _titration_family(ax):
    """不同浓度 NaOH 滴定同浓度 HAc 的曲线族（浓度越低突跃越小）。"""
    import math

    ka, va = 1.8e-5, 25.0
    pka = -math.log10(ka)
    for c, color in zip([0.1, 0.01, 0.001], ["#2457d6", "#b96a00", "#11845b"]):
        xs, ys, v = [], [], 0.0
        while v <= 35.0:
            if v == 0:
                ph = 0.5 * (pka - math.log10(c))
            elif v < va:
                nh = c * v
                ph = pka + math.log10(max(nh, 1e-12) / max(c * va - nh, 1e-12))
            elif abs(v - va) < 1e-9:
                csalt = c * va / (va + va)
                ph = 0.5 * (14 + pka + math.log10(csalt))
            else:
                oh = (c * v - c * va) / (v + va)
                ph = 14 + math.log10(max(oh, 1e-12))
            xs.append(v)
            ys.append(min(max(ph, 0), 12.5))
            v += 0.5
        ax.plot(xs, ys, color=color, lw=1.8, label=f"{c} mol/L")
    ax.legend(fontsize=6.5)
    ax.set_ylim(0, 13)


def _buffer_capacity(ax):
    """HAc-Ac⁻ 缓冲容量 β 随 pH 的变化（pH=pKa 处最大）。"""
    pka, c = 4.74, 0.1
    ka = 10 ** -pka
    xs = [x / 20 for x in range(40, 161)]
    ys = [2.303 * c * ka * (10 ** -ph) / (ka + 10 ** -ph) ** 2 for ph in xs]
    ax.plot(xs, ys, color="#2457d6", lw=2)
    ax.axvline(pka, color="#b96a00", lw=1, ls="--")
    ax.annotate(f"pH=pKa={pka}", xy=(pka, max(ys)), xytext=(5.3, max(ys) * 0.72),
                fontsize=7, color="#b96a00")
    ax.set_ylim(0, max(ys) * 1.15)


def _periodic_trends(ax):
    """第三周期（Na→Ar）原子半径与第一电离能的反向趋势。"""
    z = list(range(11, 19))
    radius = [186, 160, 143, 118, 110, 102, 99, 98]
    ie = [496, 738, 578, 787, 1012, 1000, 1251, 1521]
    labels = ["Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar"]
    ax.plot(z, radius, color="#2457d6", lw=2, marker="o", ms=3)
    ax.set_ylabel("原子半径 / pm", fontsize=8, color="#2457d6")
    ax2 = ax.twinx()
    ax2.plot(z, ie, color="#b33a3a", lw=2, marker="s", ms=3)
    ax2.set_ylabel("第一电离能 / (kJ/mol)", fontsize=8, color="#b33a3a")
    ax.set_xticks(z)
    ax.set_xticklabels(labels, fontsize=7)


def _energy_4s3d(ax):
    """4s 与 3d 能级交错示意（K/Ca 先填 4s，Sc 起 3d 更低）。"""
    ax.plot([0.15, 0.85], [0.72, 0.24], color="#b96a00", lw=2)
    ax.plot([0.15, 0.85], [0.28, 0.76], color="#2457d6", lw=2)
    ax.text(0.10, 0.70, "3d", fontsize=10, color="#b96a00")
    ax.text(0.10, 0.22, "4s", fontsize=10, color="#2457d6")
    ax.text(0.58, 0.52, "能级交错", fontsize=8, color="#6b7280")
    ax.set_axis_off()


def _distribution_curve(ax):
    """HAc 溶液分布分数 δ 随 pH 的变化（pH=pKa 时两型各 0.5）。"""
    ka = 1.8e-5
    xs = [x / 20 for x in range(20, 141)]
    ha = [(10 ** -ph) / (ka + 10 ** -ph) for ph in xs]
    ac = [ka / (ka + 10 ** -ph) for ph in xs]
    ax.plot(xs, ha, color="#2457d6", lw=2, label="δ(HAc)")
    ax.plot(xs, ac, color="#b96a00", lw=2, label="δ(Ac⁻)")
    ax.axvline(4.74, color="#9aa3b2", lw=1, ls="--")
    ax.legend(fontsize=7)
    ax.set_ylim(0, 1.05)


def _edta_alpha(ax):
    """EDTA 酸效应系数 lgαY(H) 随 pH 变化（pH 越低酸效应越强）。"""
    phs = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    lg = [18.3, 13.5, 10.6, 8.4, 6.5, 4.8, 3.3, 2.3, 1.3, 0.5, 0.1, 0.0]
    ax.plot(phs, lg, color="#2457d6", lw=2, marker="o", ms=3)
    ax.set_ylim(0, 19)


CHARTS = {
    "812-04-05": {"title": "光响应曲线", "xlabel": "光照强度", "ylabel": "光合速率",
                  "caption": "光补偿点与光饱和点示意（自绘）", "draw": _light_curve},
    "315-06-07": {"title": "NaOH 滴定 HAc 的滴定曲线", "xlabel": "NaOH 体积 / mL",
                  "ylabel": "pH", "caption": "一元弱酸滴定曲线与突跃（Ka≈1.8×10⁻⁵ 示意）",
                  "draw": _titration_curve},
    # —— V2 扩充图表 ——
    "315-06-10": {"title": "不同浓度 NaOH 滴定 HAc 曲线族", "xlabel": "NaOH 体积 / mL",
                  "ylabel": "pH", "caption": "浓度越低突跃越小（0.1 / 0.01 / 0.001 mol/L，自绘）",
                  "draw": _titration_family},
    "315-06-05": {"title": "缓冲容量—pH 曲线", "xlabel": "pH", "ylabel": "缓冲容量 β",
                  "caption": "HAc-Ac⁻ 体系缓冲容量在 pH=pKa=4.74 处最大（自绘）",
                  "draw": _buffer_capacity},
    "315-04-06": {"title": "第三周期原子半径与第一电离能", "xlabel": "元素",
                  "ylabel": "原子半径 / pm", "caption": "同周期半径递减、电离能总趋势递增（Al、S 有反常，自绘）",
                  "draw": _periodic_trends},
    "315-04-01": {"title": "4s 与 3d 能级交错示意", "xlabel": "", "ylabel": "能量",
                  "caption": "K/Ca 先填 4s，Sc 起 3d 更低——能级交错（自绘）",
                  "draw": _energy_4s3d},
    "315-06-03": {"title": "HAc 分布分数—pH 曲线", "xlabel": "pH", "ylabel": "分布分数 δ",
                  "caption": "pH=pKa 时 δ(HAc)=δ(Ac⁻)=0.5（自绘）",
                  "draw": _distribution_curve},
    "315-09-08": {"title": "EDTA 酸效应曲线", "xlabel": "pH", "ylabel": "lgαY(H)",
                  "caption": "pH 越低酸效应越强、EDTA 配位能力越弱（自绘）",
                  "draw": _edta_alpha},
    # —— 315 缺图章节补齐（每章 ≥1 图）——
    "315-01-03": {"title": "稀溶液依数性：蒸气压下降", "xlabel": "温度 / ℃", "ylabel": "蒸气压 / kPa",
                  "caption": "溶液蒸气压下降 → 沸点升高、凝固点降低（示意图，自绘）",
                  "draw": charts_basic.draw_vapor_pressure},
    "315-02-05": {"title": "反应焓变与能级变化", "xlabel": "", "ylabel": "",
                  "caption": "ΔrH° = H(产物) − H(反应物)，放热反应示意（自绘）",
                  "draw": charts_basic.draw_reaction_enthalpy},
    "315-03-03": {"title": "活化能与有效碰撞", "xlabel": "", "ylabel": "",
                  "caption": "活化配合物、正/逆活化能与反应热的关系（自绘）",
                  "draw": charts_basic.draw_activation_energy},
    "315-05-02": {"title": "准确度与精密度的四种情形", "xlabel": "", "ylabel": "",
                  "caption": "以打靶类比：+ 为真值，空心点为测定值（自绘）",
                  "draw": charts_basic.draw_accuracy_precision},
    "315-07-05": {"title": "分步沉淀与选择性沉淀", "xlabel": "", "ylabel": "",
                  "caption": "Ksp 小的 AgI 先沉淀，可实现 I⁻ 与 Cl⁻ 的分离（示意，自绘）",
                  "draw": charts_basic.draw_fractional_precipitation},
    "315-08-02": {"title": "Zn-Cu 原电池", "xlabel": "", "ylabel": "",
                  "caption": "电极、盐桥、电子流向与正负极反应（示意，自绘）",
                  "draw": charts_basic.draw_galvanic_cell},
    "315-10-07": {"title": "吸收曲线与最大吸收波长", "xlabel": "波长 λ / nm", "ylabel": "吸光度 A",
                  "caption": "选 λmax 作测量波长，灵敏度最高（示意图，自绘）",
                  "draw": charts_basic.draw_absorption_curve},
    "315-11-03": {"title": "pH 测量电池组成", "xlabel": "", "ylabel": "",
                  "caption": "玻璃电极（指示）与饱和甘汞电极（参比）组成电池（示意，自绘）",
                  "draw": charts_basic.draw_ph_cell},
    "315-12-01": {"title": "碳的三种杂化与键角", "xlabel": "", "ylabel": "",
                  "caption": "sp（180°）、sp²（120°）、sp³（109.5°）（示意，自绘）",
                  "draw": charts_basic.draw_hybrid_orbitals},
    "315-16-01": {"title": "手性与对映体", "xlabel": "", "ylabel": "",
                  "caption": "镜像不重合即手性；手性碳连 4 个不同基团（示意，自绘）",
                  "draw": charts_basic.draw_chirality},
    "315-17-04": {"title": "SN2 背面进攻与构型翻转", "xlabel": "", "ylabel": "",
                  "caption": "亲核试剂从背面进攻，产物构型翻转（瓦尔登转化，示意，自绘）",
                  "draw": charts_basic.draw_sn2},
    "315-26-02": {"title": "常压蒸馏装置", "xlabel": "", "ylabel": "",
                  "caption": "圆底烧瓶—蒸馏头—冷凝管—接收瓶（示意，自绘）",
                  "draw": charts_basic.draw_distillation_apparatus},
}

# 人工挑选的静态图（Commons CC / 教材裁图 local）：
# 格式 {point_id: {"src": "media/xxx.png", "caption": ..., "source": "commons|textbook",
#                 "license": "CC BY-SA 4.0", "attribution": "..."}}
# 101 结构图/时间线并入 CHARTS（与 315 图表同一生成机制）
for _pid, _draw in charts_101.FIGURES.items():
    _title = TITLES_101.get(_pid, "")
    CHARTS[_pid] = {"title": _title, "xlabel": "", "ylabel": "",
                    "caption": f"{_title}（自绘示意图）", "draw": _draw}

# 204 英语（二）与 812 绪论体系图
TITLES_MISC = {
    "204-01-01": "英语（二）试卷结构与分值分布",
    "204-02-05": "长难句主干识别三步法",
    "204-03-02": "完形填空做题步骤",
    "204-04-03": "阅读细节题解题流程",
    "204-05-01": "真题精读四步流程",
    "204-06-02": "新题型（小标题匹配）解题步骤",
    "204-07-02": "翻译拆句三步法",
    "204-08-01": "应用文三段框架",
    "204-09-01": "图表作文三段结构",
    "812-00-02": "植物生理学的内容体系",
}
for _pid, _draw in charts_misc.FIGURES.items():
    _title = TITLES_MISC.get(_pid, "")
    CHARTS[_pid] = {"title": _title, "xlabel": "", "ylabel": "",
                    "caption": f"{_title}（自绘）", "draw": _draw}

# 单元配图示范（第一章）：结构类示意图，展开考点时先于文字展示
for _pid, _spec in charts_misc.UNIT_FIGURES.items():
    CHARTS[_pid] = {"title": _spec["title"], "xlabel": "", "ylabel": "",
                    "caption": _spec["caption"], "draw": _spec["draw"]}

STATIC: dict = {}
