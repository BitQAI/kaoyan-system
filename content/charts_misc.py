"""204 英语（二）章节示意图 + 812-00 绪论内容体系图。

复用 charts_101 的声明式渲染器（结构图/流程）。
"""
from content.charts_101 import render_flow


def _flow(**kw):
    return lambda ax, spec=kw: render_flow(ax, spec)


def draw_score_structure(ax):
    """试卷结构分值分布（横条图，按 100 分制）。"""
    items = [("阅读理解 A（4 篇 20 题）", 40, "#2457d6"),
             ("翻译（150 词英译汉）", 15, "#11845b"),
             ("写作 B（约 150 词短文）", 15, "#b96a00"),
             ("完形填空（20 题）", 10, "#6d4ec7"),
             ("阅读理解 B（新题型）", 10, "#0e7490"),
             ("写作 A（约 100 词应用文）", 10, "#b33a3a")]
    for i, (label, v, color) in enumerate(items):
        y = 0.84 - i * 0.145
        ax.barh(y, v / 45, height=0.09, color=color, alpha=0.85, left=0.36)
        ax.text(0.35, y, label, fontsize=7.2, ha="right", va="center", color="#333b45")
        ax.text(0.37 + v / 45, y, f"{v}分", fontsize=7.2, va="center", color=color)
    ax.text(0.36, 0.02, "阅读 + 写作合计 75 分 → 训练重点", fontsize=7.4,
            color="#b33a3a")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


FIGURES = {}

# 204-01 试卷结构（分值图）
FIGURES["204-01-01"] = draw_score_structure

# 204-02 长难句主干识别
FIGURES["204-02-05"] = _flow(
    boxes=[{"x": 0.10, "y": 0.74, "w": 0.80, "h": 0.14,
            "text": "The researcher who conducted the survey found that…", "color": "grey", "size": 6.6},
           {"x": 0.03, "y": 0.36, "w": 0.29, "h": 0.20, "text": "① 找谓语动词\n（确定分句数）", "color": "blue"},
           {"x": 0.355, "y": 0.36, "w": 0.29, "h": 0.20, "text": "② 定主语\n（谓语前中心词）", "color": "green"},
           {"x": 0.68, "y": 0.36, "w": 0.29, "h": 0.20, "text": "③ 理修饰\n（从句/非谓语/介词短语）", "color": "orange"}],
    arrows=[{"x1": 0.32, "y1": 0.46, "x2": 0.355, "y2": 0.46},
            {"x1": 0.645, "y1": 0.46, "x2": 0.68, "y2": 0.46}],
    texts=[{"x": 0.5, "y": 0.62, "text": "主干：The researcher found that…", "size": 7.2, "color": "#2457d6"},
           {"x": 0.5, "y": 0.18, "text": "先翻主干，再把修饰成分挂回原位", "size": 7.0}])

# 204-03 完形填空做题步骤
FIGURES["204-03-02"] = _flow(
    boxes=[{"x": 0.03, "y": 0.44, "w": 0.27, "h": 0.22, "text": "① 通读首句\n抓文章主线", "color": "blue"},
           {"x": 0.365, "y": 0.44, "w": 0.27, "h": 0.22, "text": "② 逐空定位\n（上下文语境）", "color": "green"},
           {"x": 0.70, "y": 0.44, "w": 0.27, "h": 0.22, "text": "③ 复读复核\n（逻辑是否通顺）", "color": "orange"}],
    arrows=[{"x1": 0.30, "y1": 0.55, "x2": 0.365, "y2": 0.55},
            {"x1": 0.635, "y1": 0.55, "x2": 0.70, "y2": 0.55}],
    texts=[{"x": 0.5, "y": 0.26, "text": "高频：动词辨析、介词搭配、逻辑关系词", "size": 7.2, "color": "#b33a3a"},
           {"x": 0.5, "y": 0.88, "text": "完形填空（10 分 / 15-18 分钟）", "size": 7.8}])

# 204-04 阅读解题流程
FIGURES["204-04-03"] = _flow(
    boxes=[{"x": 0.03, "y": 0.46, "w": 0.21, "h": 0.20, "text": "读题干\n划关键词", "color": "blue"},
           {"x": 0.27, "y": 0.46, "w": 0.21, "h": 0.20, "text": "回原文\n定位对应句", "color": "green"},
           {"x": 0.51, "y": 0.46, "w": 0.21, "h": 0.20, "text": "比对选项\n（同义替换）", "color": "orange"},
           {"x": 0.75, "y": 0.46, "w": 0.21, "h": 0.20, "text": "排除干扰\n（无据/绝对化）", "color": "red"}],
    arrows=[{"x1": 0.24, "y1": 0.56, "x2": 0.27, "y2": 0.56},
            {"x1": 0.48, "y1": 0.56, "x2": 0.51, "y2": 0.56},
            {"x1": 0.72, "y1": 0.56, "x2": 0.75, "y2": 0.56}],
    texts=[{"x": 0.5, "y": 0.30, "text": "六大题型：主旨 / 细节 / 推理 / 词义 / 态度 / 例证", "size": 7.0},
           {"x": 0.5, "y": 0.80, "text": "阅读原则：答案必有原文依据，不凭常识", "size": 7.6, "color": "#b33a3a"}])

# 204-05 真题精读四步
FIGURES["204-05-01"] = _flow(
    boxes=[{"x": 0.02, "y": 0.44, "w": 0.22, "h": 0.22, "text": "① 限时做题\n（18 分钟/篇）", "color": "blue"},
           {"x": 0.26, "y": 0.44, "w": 0.22, "h": 0.22, "text": "② 逐句翻译\n标生词句型", "color": "green"},
           {"x": 0.50, "y": 0.44, "w": 0.22, "h": 0.22, "text": "③ 错因归类\n（定位/替换/推理）", "color": "orange"},
           {"x": 0.74, "y": 0.44, "w": 0.22, "h": 0.22, "text": "④ 生词入卡\n次日复习", "color": "purple"}],
    arrows=[{"x1": 0.24, "y1": 0.55, "x2": 0.26, "y2": 0.55},
            {"x1": 0.48, "y1": 0.55, "x2": 0.50, "y2": 0.55},
            {"x1": 0.72, "y1": 0.55, "x2": 0.74, "y2": 0.55}],
    texts=[{"x": 0.5, "y": 0.24, "text": "目标：把每篇真题榨干——定位句与干扰项设置都能复述", "size": 7.2}])

# 204-06 新题型步骤
FIGURES["204-06-02"] = _flow(
    boxes=[{"x": 0.03, "y": 0.42, "w": 0.29, "h": 0.24, "text": "① 先读选项\n圈核心名词/动词", "color": "blue"},
           {"x": 0.355, "y": 0.42, "w": 0.29, "h": 0.24, "text": "② 逐段找主题句\n（首末句、转折后）", "color": "green"},
           {"x": 0.68, "y": 0.42, "w": 0.29, "h": 0.24, "text": "③ 关键词复现匹配\n④ 检查唯一性", "color": "orange"}],
    arrows=[{"x1": 0.32, "y1": 0.54, "x2": 0.355, "y2": 0.54},
            {"x1": 0.645, "y1": 0.54, "x2": 0.68, "y2": 0.54}],
    texts=[{"x": 0.5, "y": 0.80, "text": "阅读理解 B：小标题匹配 / 段落匹配（10 分）", "size": 7.4}])

# 204-07 翻译三步法
FIGURES["204-07-02"] = _flow(
    boxes=[{"x": 0.06, "y": 0.44, "w": 0.26, "h": 0.22, "text": "① 找主干\n（主谓宾）", "color": "blue"},
           {"x": 0.37, "y": 0.44, "w": 0.26, "h": 0.22, "text": "② 理修饰\n（定从/状语/非谓语）", "color": "green"},
           {"x": 0.68, "y": 0.44, "w": 0.26, "h": 0.22, "text": "③ 重组中文\n（定语前置、被动变主动）", "color": "orange"}],
    arrows=[{"x1": 0.32, "y1": 0.55, "x2": 0.37, "y2": 0.55},
            {"x1": 0.63, "y1": 0.55, "x2": 0.68, "y2": 0.55}],
    texts=[{"x": 0.5, "y": 0.24, "text": "评分标准：准确、完整、通顺（先准确完整，再润色）", "size": 7.2, "color": "#b33a3a"}])

# 204-08 应用文三段框架
FIGURES["204-08-01"] = _flow(
    boxes=[{"x": 0.03, "y": 0.62, "w": 0.29, "h": 0.22, "text": "开头\n表明目的+身份\n（I am writing to…）", "color": "blue"},
           {"x": 0.355, "y": 0.62, "w": 0.29, "h": 0.22, "text": "主体\n2-3 条要点\n（First…/Moreover…）", "color": "green"},
           {"x": 0.68, "y": 0.62, "w": 0.29, "h": 0.22, "text": "结尾\n希望采纳/期待回复\n+ 落款", "color": "orange"}],
    arrows=[{"x1": 0.32, "y1": 0.73, "x2": 0.355, "y2": 0.73},
            {"x1": 0.645, "y1": 0.73, "x2": 0.68, "y2": 0.73}],
    texts=[{"x": 0.5, "y": 0.40, "text": "五要素：格式 · 称谓 · 目的 · 主体 · 结尾", "size": 7.4},
           {"x": 0.5, "y": 0.90, "text": "写作 A：约 100 词应用文（10 分）", "size": 7.8}])

# 204-09 短文三段结构
FIGURES["204-09-01"] = _flow(
    boxes=[{"x": 0.03, "y": 0.58, "w": 0.29, "h": 0.24, "text": "第一段\n描述图表/图画\n（总体趋势+数据）", "color": "blue"},
           {"x": 0.355, "y": 0.58, "w": 0.29, "h": 0.24, "text": "第二段\n解释原因/意义\n（因果链+例证）", "color": "green"},
           {"x": 0.68, "y": 0.58, "w": 0.29, "h": 0.24, "text": "第三段\n总结/建议\n（观点+展望）", "color": "orange"}],
    arrows=[{"x1": 0.32, "y1": 0.70, "x2": 0.355, "y2": 0.70},
            {"x1": 0.645, "y1": 0.70, "x2": 0.68, "y2": 0.70}],
    texts=[{"x": 0.5, "y": 0.36, "text": "连接词清楚、先正确后丰富", "size": 7.2},
           {"x": 0.5, "y": 0.90, "text": "写作 B：约 150 词短文（15 分）", "size": 7.8}])

# 812-00 植物生理学内容体系
FIGURES["812-00-02"] = _flow(
    boxes=[{"x": 0.02, "y": 0.52, "w": 0.20, "h": 0.20, "text": "基础代谢\n水分代谢\n矿质营养", "color": "blue"},
           {"x": 0.245, "y": 0.52, "w": 0.20, "h": 0.20, "text": "能量与物质转化\n光合作用\n呼吸作用", "color": "green"},
           {"x": 0.47, "y": 0.52, "w": 0.20, "h": 0.20, "text": "运输分配\n同化物运输\n源-库关系", "color": "orange"},
           {"x": 0.695, "y": 0.52, "w": 0.20, "h": 0.20, "text": "生长发育调控\n生长物质\n成花/生殖/衰老", "color": "purple"},
           {"x": 0.30, "y": 0.16, "w": 0.40, "h": 0.16, "text": "逆境生理：抗逆性与适应", "color": "red"}],
    arrows=[{"x1": 0.22, "y1": 0.62, "x2": 0.245, "y2": 0.62},
            {"x1": 0.445, "y1": 0.62, "x2": 0.47, "y2": 0.62},
            {"x1": 0.67, "y1": 0.62, "x2": 0.695, "y2": 0.62},
            {"x1": 0.50, "y1": 0.52, "x2": 0.50, "y2": 0.34, "label": "贯穿全程"}],
    texts=[{"x": 0.5, "y": 0.86, "text": "植物生理学内容体系（按生命活动过程）", "size": 7.8, "color": "#b33a3a"}])


def draw_plant_cell(ax):
    """植物细胞结构示意：细胞壁/大液泡/质体/胞间连丝。"""
    import matplotlib.patches as mpatches
    ax.add_patch(mpatches.FancyBboxPatch((0.08, 0.12), 0.84, 0.74, boxstyle="round,pad=0.01",
                 fc="#f4faf6", ec="#11845b", lw=2.4))            # 细胞壁
    ax.add_patch(mpatches.FancyBboxPatch((0.12, 0.16), 0.76, 0.66, boxstyle="round,pad=0.008",
                 fc="#eef6ff", ec="#2457d6", lw=1.4))            # 原生质体/质膜
    ax.add_patch(mpatches.Circle((0.50, 0.47), 0.17, fc="#dbeafe", ec="#2457d6", lw=1.6))
    ax.text(0.50, 0.47, "大液泡", fontsize=8.5, ha="center", va="center", color="#2457d6")
    for cx, cy, lab in [(0.25, 0.66, "叶绿体"), (0.72, 0.70, "质体"), (0.24, 0.28, "线粒体"),
                        (0.76, 0.28, "高尔基体")]:
        ax.add_patch(mpatches.Ellipse((cx, cy), 0.15, 0.10, fc="#e8f6ef", ec="#11845b", lw=1.2))
        ax.text(cx, cy - 0.085, lab, fontsize=6.6, ha="center", color="#11845b")
    ax.add_patch(mpatches.Circle((0.47, 0.80), 0.045, fc="#fff4e5", ec="#b96a00", lw=1.2))
    ax.text(0.47, 0.875, "细胞核", fontsize=6.6, ha="center", color="#b96a00")
    for y in (0.30, 0.62):
        ax.plot([0.04, 0.14], [y, y + 0.04], color="#8a94a6", lw=1.6, ls="--")
        ax.text(0.015, y + 0.09, "胞间连丝", fontsize=6.4, color="#6b7280")
    ax.text(0.08, 0.90, "细胞壁", fontsize=7.4, color="#11845b")
    ax.text(0.10, 0.055, "质膜", fontsize=6.8, color="#2457d6")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def draw_fluid_mosaic(ax):
    """生物膜流动镶嵌模型：磷脂双分子层 + 膜蛋白。"""
    import matplotlib.patches as mpatches
    ax.add_patch(mpatches.Rectangle((0.06, 0.40), 0.88, 0.06, fc="#eaf1ff", ec="none"))
    ax.add_patch(mpatches.Rectangle((0.06, 0.54), 0.88, 0.06, fc="#eaf1ff", ec="none"))
    for x in [0.075 + i * 0.055 for i in range(16)]:
        ax.add_patch(mpatches.Circle((x, 0.50), 0.018, fc="#2457d6", ec="none"))
        ax.add_patch(mpatches.Circle((x, 0.44), 0.018, fc="#2457d6", ec="none"))
        ax.plot([x, x], [0.44, 0.50], color="#bcd0f5", lw=1)
    ax.add_patch(mpatches.FancyBboxPatch((0.22, 0.32), 0.10, 0.36, boxstyle="round,pad=0.008",
                 fc="#e8f6ef", ec="#11845b", lw=1.6))
    ax.text(0.27, 0.24, "载体蛋白", fontsize=7, ha="center", color="#11845b")
    ax.add_patch(mpatches.FancyBboxPatch((0.48, 0.34), 0.12, 0.32, boxstyle="round,pad=0.008",
                 fc="#fff4e5", ec="#b96a00", lw=1.6))
    ax.text(0.54, 0.24, "通道蛋白", fontsize=7, ha="center", color="#b96a00")
    ax.add_patch(mpatches.FancyBboxPatch((0.74, 0.42), 0.14, 0.16, boxstyle="round,pad=0.008",
                 fc="#fdeeee", ec="#b33a3a", lw=1.6))
    ax.text(0.81, 0.34, "受体蛋白", fontsize=7, ha="center", color="#b33a3a")
    ax.text(0.06, 0.66, "磷脂双分子层（亲水头·疏水尾）", fontsize=7.2, color="#2457d6")
    ax.text(0.50, 0.86, "膜蛋白镶嵌其中 → 流动性 + 不对称性", fontsize=7.6, ha="center", color="#333b45")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def draw_cytoskeleton(ax):
    """细胞骨架三组分：微管 / 微丝 / 中间纤维。"""
    import matplotlib.patches as mpatches
    # 微管：中空管
    ax.add_patch(mpatches.Rectangle((0.08, 0.72), 0.34, 0.09, fc="#eaf1ff", ec="#2457d6", lw=1.4))
    for x in [0.13 + i * 0.05 for i in range(6)]:
        ax.add_patch(mpatches.Circle((x, 0.765), 0.016, fc="#fff", ec="#2457d6", lw=1))
    ax.text(0.25, 0.85, "微管：中空管·13 条原丝", fontsize=7.2, ha="center", color="#2457d6")
    ax.text(0.25, 0.64, "纺锤体 / 成膜体 / 微纤丝方向", fontsize=6.6, ha="center", color="#6b7280")
    # 微丝：双螺旋细丝
    import math
    xs = [0.10 + i * 0.006 for i in range(45)]
    ax.plot(xs, [0.50 + 0.03 * math.sin(i * 0.7) for i in range(45)], color="#11845b", lw=2)
    ax.text(0.25, 0.57, "微丝：肌动蛋白双螺旋", fontsize=7.2, ha="center", color="#11845b")
    ax.text(0.25, 0.40, "胞质环流 / 顶端生长", fontsize=6.6, ha="center", color="#6b7280")
    # 中间纤维：单根细线
    ax.plot([0.10, 0.40], [0.28, 0.28], color="#b96a00", lw=1.8)
    ax.text(0.25, 0.33, "中间纤维：抗拉支持", fontsize=7.2, ha="center", color="#b96a00")
    ax.text(0.25, 0.19, "（植物中是否存在需对照教材核验）", fontsize=6.4, ha="center", color="#6b7280")
    # 右栏说明
    ax.text(0.60, 0.78, "共同特点：", fontsize=7.4, color="#333b45")
    for i, t in enumerate(["动态组装 / 去组装", "维持细胞形态与极性", "参与物质运输与分裂", "受发育与环境信号调控"]):
        ax.text(0.60, 0.68 - i * 0.10, "· " + t, fontsize=6.8, color="#4a5158")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


UNIT_FIGURES = {
    "812-01-01": {"title": "植物细胞的结构特点", "draw": draw_plant_cell,
                  "caption": "植物细胞结构示意：细胞壁、大液泡、质体与胞间连丝（自绘）"},
    "812-01-03": {"title": "生物膜流动镶嵌模型", "draw": draw_fluid_mosaic,
                  "caption": "生物膜流动镶嵌模型：磷脂双分子层与功能膜蛋白（自绘）"},
    "812-01-05": {"title": "细胞骨架三组分", "draw": draw_cytoskeleton,
                  "caption": "细胞骨架：微管、微丝与中间纤维（自绘）"},
}
