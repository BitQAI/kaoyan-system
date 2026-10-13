"""媒体配置：结构式 SMILES / 数据图表 / 人工挑选的静态图。

点 ID 依据 content/content.json 的实际编号；新增媒体在此登记。
"""

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


CHARTS = {
    "812-04-05": {"title": "光响应曲线", "xlabel": "光照强度", "ylabel": "光合速率",
                  "caption": "光补偿点与光饱和点示意（自绘）", "draw": _light_curve},
    "315-06-07": {"title": "NaOH 滴定 HAc 的滴定曲线", "xlabel": "NaOH 体积 / mL",
                  "ylabel": "pH", "caption": "一元弱酸滴定曲线与突跃（Ka≈1.8×10⁻⁵ 示意）",
                  "draw": _titration_curve},
}

# 人工挑选的静态图（Commons CC / 教材裁图 local）：
# 格式 {point_id: {"src": "media/xxx.png", "caption": ..., "source": "commons|textbook",
#                 "license": "CC BY-SA 4.0", "attribution": "..."}}
STATIC: dict = {}
