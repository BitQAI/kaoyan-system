"""315 无机/分析/有机的示意图与曲线（matplotlib 自绘，media_config.CHARTS 挂载）。

命名约定：draw 函数接收 ax，自行完成全部绘制（示意图类调用 ax.set_axis_off()）。
"""
import math


def _arrow(ax, x1, y1, x2, y2, color="#2457d6", lw=1.6):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw))


def draw_vapor_pressure(ax):
    """蒸气压-温度曲线：溶液蒸气压下降 → 沸点升高、凝固点降低。"""
    temps = [x * 0.5 for x in range(60, 261)]          # 30~130 ℃示意
    def pv(t):                                          # 简化蒸气压曲线
        return max(0.2, 0.9 ** (100 - t) * 101)
    ax.plot(temps, [pv(t) for t in temps], color="#2457d6", lw=2, label="纯水")
    ax.plot(temps, [pv(t) * 0.92 for t in temps], color="#b96a00", lw=2, label="溶液")
    ax.axhline(101.325, color="#9aa3b2", lw=0.9, ls=":")
    ax.annotate("p°", xy=(60, 101), xytext=(36, 104), fontsize=7.5, color="#6b7280")
    ax.plot([100], [101], "o", ms=4, color="#2457d6")
    ax.plot([102.4], [101], "o", ms=4, color="#b96a00")
    ax.annotate("沸点升高\nΔTb", xy=(101.2, 101), xytext=(106, 74), fontsize=7.5,
                color="#b96a00", arrowprops=dict(arrowstyle="->", color="#b96a00", lw=1))
    ax.plot([0], [0.92], "o", ms=4, color="#b96a00")
    ax.annotate("凝固点降低\nΔTf", xy=(0.5, 1), xytext=(10, 18), fontsize=7.5,
                color="#11845b", arrowprops=dict(arrowstyle="->", color="#11845b", lw=1))
    ax.legend(fontsize=7, loc="upper left")
    ax.set_xlim(0, 130)
    ax.set_ylim(0, 118)


def draw_reaction_enthalpy(ax):
    """反应焓变能级图：ΔH = H(产物) − H(反应物)（放热示意）。"""
    ax.plot([0.1, 0.35], [0.72, 0.72], color="#2457d6", lw=2.4)
    ax.plot([0.65, 0.9], [0.32, 0.32], color="#11845b", lw=2.4)
    ax.text(0.05, 0.76, "反应物 H1", fontsize=8, color="#2457d6")
    ax.text(0.68, 0.24, "产物 H2", fontsize=8, color="#11845b")
    _arrow(ax, 0.5, 0.72, 0.5, 0.36, color="#b33a3a")
    ax.text(0.52, 0.5, "ΔH<0\n（放热）", fontsize=8, color="#b33a3a")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def draw_activation_energy(ax):
    """活化能与有效碰撞：能量-反应进程图（含活化配合物）。"""
    xs = [x / 100 for x in range(0, 101)]
    ys = []
    for x in xs:
        peak = math.exp(-((x - 0.45) ** 2) / 0.012)
        ys.append(0.30 - 0.16 * x + 0.45 * peak)
    ax.plot(xs, ys, color="#2457d6", lw=2)
    ax.axhline(0.30, color="#c3cbd8", lw=0.8, ls="--")
    ax.axhline(0.14, color="#c3cbd8", lw=0.8, ls="--")
    _arrow(ax, 0.12, 0.30, 0.12, 0.685, color="#b33a3a")
    ax.text(0.02, 0.44, "Ea（正）", fontsize=8, color="#b33a3a")
    _arrow(ax, 0.82, 0.14, 0.82, 0.36, color="#11845b")
    ax.text(0.84, 0.2, "Ea（逆）", fontsize=8, color="#11845b")
    ax.text(0.42, 0.78, "活化配合物", fontsize=7.5, color="#6b7280")
    ax.text(0.01, 0.26, "反应物", fontsize=8, color="#4a5158")
    ax.text(0.86, 0.10, "产物", fontsize=8, color="#4a5158")
    ax.text(0.33, 0.055, "ΔH<0", fontsize=8, color="#6b7280")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 0.95)


def draw_accuracy_precision(ax):
    """准确度与精密度：四种打靶结果（中心=真值）。"""
    import matplotlib.patches as mpatches
    import numpy as np

    groups = [
        ("准确且精密", (0.0, 0.0), 0.055, (0.26, 0.70)),
        ("精密不准确", (0.0, 0.0), 0.05, (0.74, 0.70)),
        ("准确不精密", (0.0, 0.0), 0.20, (0.26, 0.22)),
        ("都不合格", (0.0, 0.0), 0.20, (0.74, 0.22)),
    ]
    rng = np.random.default_rng(7)
    r = 0.10
    for i, (label, _c, spread, (cx, cy)) in enumerate(groups):
        if i == 1:
            mean = (0.05, 0.05)                      # 偏移真值 → 不准确
        else:
            mean = (0.0, 0.0)
        ax.add_patch(mpatches.Circle((cx, cy), r, fill=False, ec="#9aa3b2", lw=1))
        for rr in (r * 0.62, r * 0.28):
            ax.add_patch(mpatches.Circle((cx, cy), rr, fill=False, ec="#dfe4ec", lw=0.8))
        ax.plot([cx], [cy], marker="+", ms=8, color="#b33a3a", mew=1.5)
        pts = rng.normal(mean, spread, size=(6, 2))
        ax.plot(cx + pts[:, 0], cy + pts[:, 1], "o", ms=3.4, mfc="none", mec="#2457d6")
        ax.text(cx, cy - r - 0.09, label, fontsize=7, ha="center", color="#4a5158")
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def draw_fractional_precipitation(ax):
    """分步沉淀：Ksp 小者先沉淀（AgI 先于 AgCl）。"""
    for i, (title, sub, color) in enumerate([
            ("滴入 AgNO₃", "I-、Cl- 共存", "#9aa3b2"),
            ("继续滴加", "黄色沉淀 AgI 先析出", "#b96a00"),
            ("沉淀完全后", "白色沉淀 AgCl 析出", "#2457d6")]):
        cx = 0.18 + i * 0.32
        ax.add_patch(__import__("matplotlib").patches.Rectangle(
            (cx - 0.075, 0.32), 0.15, 0.34, fill=False, ec="#6b7280", lw=1.2))
        ax.plot([cx - 0.075, cx + 0.075], [0.32, 0.24], color="#6b7280", lw=1)
        ax.add_patch(__import__("matplotlib").patches.Rectangle(
            (cx - 0.07, 0.32), 0.14, 0.075, fc=color, ec="none", alpha=0.75))
        ax.text(cx, 0.72, title, fontsize=7.5, ha="center", color="#4a5158")
        ax.text(cx, 0.17, sub, fontsize=7, ha="center", color=color)
    ax.text(0.5, 0.05, "沉淀顺序由开始沉淀所需 Ag+ 浓度（Ksp）决定", fontsize=7.5,
            ha="center", color="#6b7280")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def draw_galvanic_cell(ax):
    """Zn-Cu 原电池：电极、盐桥、电子与离子流向。"""
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.06, 0.2), 0.32, 0.5,
                 fill=False, ec="#6b7280", lw=1.2))
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.62, 0.2), 0.32, 0.5,
                 fill=False, ec="#6b7280", lw=1.2))
    ax.plot([0.11, 0.11], [0.22, 0.62], color="#4a5158", lw=2.4)      # Zn 电极
    ax.plot([0.89, 0.89], [0.22, 0.62], color="#b96a00", lw=2.4)      # Cu 电极
    ax.text(0.10, 0.66, "Zn", fontsize=9, ha="center", color="#4a5158")
    ax.text(0.90, 0.66, "Cu", fontsize=9, ha="center", color="#b96a00")
    ax.plot([0.11, 0.11, 0.89, 0.89], [0.62, 0.86, 0.86, 0.62], color="#2457d6", lw=1.6)
    _arrow(ax, 0.42, 0.86, 0.58, 0.86, color="#2457d6")
    ax.text(0.5, 0.90, "e- 电子流向", fontsize=7.5, ha="center", color="#2457d6")
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.47, 0.60), 0.06, 0.16,
                 fc="#dbe6ff", ec="#2457d6", lw=1))
    ax.text(0.5, 0.55, "盐桥", fontsize=7.5, ha="center", color="#2457d6")
    ax.text(0.22, 0.40, "Zn2+", fontsize=8, color="#4a5158")
    ax.text(0.76, 0.40, "Cu2+ → Cu", fontsize=8, color="#b96a00", ha="center")
    ax.text(0.22, 0.12, "负极（氧化）", fontsize=7.5, ha="center", color="#4a5158")
    ax.text(0.78, 0.12, "正极（还原）", fontsize=7.5, ha="center", color="#b96a00")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def draw_absorption_curve(ax):
    """吸收曲线与最大吸收波长（λmax）。"""
    xs = [x / 10 for x in range(3500, 6501)]
    lam0, sigma, amp = 520, 55, 0.85
    ys = [amp * math.exp(-((x - lam0) ** 2) / (2 * sigma ** 2)) + 0.05 for x in xs]
    ax.plot(xs, ys, color="#2457d6", lw=2)
    ax.axvline(lam0, color="#b96a00", lw=1, ls="--")
    ax.annotate("λmax=520 nm", xy=(lam0, amp), xytext=(560, 0.72), fontsize=8,
                color="#b96a00", arrowprops=dict(arrowstyle="->", color="#b96a00", lw=1))
    ax.set_xlabel("波长 λ / nm")
    ax.set_ylabel("吸光度 A")
    ax.set_ylim(0, 1.0)


def draw_ph_cell(ax):
    """pH 测量电池：玻璃电极 + 饱和甘汞电极。"""
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.28, 0.16), 0.44, 0.42,
                 fill=False, ec="#6b7280", lw=1.2))
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.30, 0.16), 0.40, 0.24,
                 fc="#dbe6ff", ec="none", alpha=0.8))
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.36, 0.34), 0.05, 0.5,
                 fc="#eef3ff", ec="#2457d6", lw=1.2))
    ax.text(0.385, 0.80, "玻璃电极", fontsize=7.5, ha="center", color="#2457d6")
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.60, 0.36), 0.04, 0.30,
                 fc="#fff4e5", ec="#b96a00", lw=1.2))
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.585, 0.30), 0.07, 0.07,
                 fc="#f2f4f8", ec="#b96a00", lw=1))
    ax.text(0.62, 0.72, "饱和甘汞电极", fontsize=7.5, ha="center", color="#b96a00")
    ax.plot([0.385, 0.385, 0.62, 0.62], [0.84, 0.92, 0.92, 0.66], color="#4a5158", lw=1.4)
    ax.text(0.5, 0.95, "mV / pH 计", fontsize=7.5, ha="center", color="#4a5158")
    ax.text(0.5, 0.27, "待测溶液", fontsize=7.5, ha="center", color="#2457d6")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def draw_hybrid_orbitals(ax):
    """碳的三种杂化：sp（直线形）/ sp²（平面三角形）/ sp³（正四面体）。"""
    labels = [("sp", "180°", 2), ("sp²", "120°", 3), ("sp³", "109.5°", 4)]
    for i, (name, ang, n) in enumerate(labels):
        cx = 0.17 + i * 0.33
        cy = 0.5
        ax.add_patch(__import__("matplotlib").patches.Circle((cx, cy), 0.02, fc="#4a5158"))
        for k in range(n):
            theta = math.pi / 2 + 2 * math.pi * k / n
            x2, y2 = cx + 0.10 * math.cos(theta), cy + 0.10 * math.sin(theta)
            _arrow(ax, cx, cy, x2, y2, color="#2457d6", lw=1.3)
        ax.text(cx, 0.82, name, fontsize=9, ha="center", color="#2457d6")
        ax.text(cx, 0.16, ang, fontsize=7.5, ha="center", color="#6b7280")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def draw_chirality(ax):
    """手性：互为镜像而不重合（左右手模型）+ 手性碳四个不同基团。"""
    ax.text(0.24, 0.90, "物体与其镜像（如左右手）", fontsize=7.5, ha="center",
            color="#4a5158")
    # 左手形：竖线 + 向右的小臂；右手形：竖线 + 向左的小臂（镜像）
    for x, dx in [(0.135, 0.055), (0.345, -0.055)]:
        ax.plot([x, x], [0.74, 0.48], color="#2457d6", lw=2.2)          # 掌心（竖线）
        ax.plot([x, x + dx], [0.74, 0.70], color="#2457d6", lw=2.2)     # 拇指
        ax.plot([x, x + dx * 0.7], [0.60, 0.56], color="#2457d6", lw=1.6)
    ax.plot([0.24, 0.24], [0.42, 0.86], color="#c3cbd8", lw=1, ls="--")
    ax.text(0.24, 0.38, "镜像对称，但无论如何旋转\n都不能与另一个重合", fontsize=7,
            ha="center", color="#6b7280")
    ax.text(0.68, 0.90, "手性碳（C*）：连 4 个不同基团", fontsize=7.5, ha="center",
            color="#4a5158")
    cx, cy = 0.66, 0.56
    ax.add_patch(__import__("matplotlib").patches.Circle((cx, cy), 0.022, fc="#4a5158"))
    ax.text(cx + 0.03, cy + 0.02, "C*", fontsize=8.5, color="#4a5158")
    for label, dx, dy in [("—Cl", 0.13, 0.0), ("—H", -0.13, 0.0),
                          ("—CH3", 0.0, 0.13), ("—COOH", 0.0, -0.14)]:
        _arrow(ax, cx, cy, cx + dx, cy + dy, color="#2457d6", lw=1.2)
        ax.text(cx + dx * 1.35, cy + dy * 1.2 - 0.02, label, fontsize=7.5,
                ha="center", color="#4a5158")
    ax.text(0.68, 0.32, "互为镜像、不能重合 → 一对对映体", fontsize=7.5,
            ha="center", color="#6b7280")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def draw_sn2(ax):
    """SN2 背面进攻与构型翻转（瓦尔登转化）。"""
    # 反应物
    ax.text(0.16, 0.86, "反应物（R 构型）", fontsize=7.5, ha="center", color="#4a5158")
    cx, cy = 0.16, 0.52
    ax.add_patch(__import__("matplotlib").patches.Circle((cx, cy), 0.02, fc="#4a5158"))
    for dx, dy, lab in [(-0.10, 0.06, "R1"), (0.02, -0.12, "R2"), (0.10, 0.08, "R3")]:
        ax.plot([cx, cx + dx], [cy, cy + dy], color="#4a5158", lw=1.4)
        ax.text(cx + dx * 1.35, cy + dy * 1.3, lab, fontsize=7, ha="center", color="#4a5158")
    ax.plot([cx + 0.02, cx + 0.12], [cy + 0.14, cy + 0.2], color="#b33a3a", lw=1.6)
    ax.text(cx + 0.14, cy + 0.22, "Br", fontsize=8, color="#b33a3a")
    _arrow(ax, 0.02, 0.30, 0.19, 0.44, color="#11845b")
    ax.text(0.0, 0.24, "Nu-（背面进攻）", fontsize=7, color="#11845b")
    ax.text(0.5, 0.52, "过渡态\n（Nu—C—Br 共线）", fontsize=7.5, ha="center", color="#6b7280")
    # 产物
    ax.text(0.84, 0.86, "产物（S 构型，构型翻转）", fontsize=7.5, ha="center", color="#4a5158")
    cx = 0.84
    ax.add_patch(__import__("matplotlib").patches.Circle((cx, cy), 0.02, fc="#4a5158"))
    for dx, dy, lab in [(-0.10, -0.06, "R1"), (0.02, 0.12, "R2"), (0.10, -0.08, "R3")]:
        ax.plot([cx, cx + dx], [cy, cy + dy], color="#4a5158", lw=1.4)
        ax.text(cx + dx * 1.35, cy + dy * 1.3, lab, fontsize=7, ha="center", color="#4a5158")
    ax.plot([cx - 0.02, cx - 0.12], [cy + 0.14, cy + 0.2], color="#11845b", lw=1.6)
    ax.text(cx - 0.13, cy + 0.22, "Nu", fontsize=8, color="#11845b")
    ax.text(0.84, 0.24, "Br- 离去，Nu 从背面进入", fontsize=7, ha="center", color="#6b7280")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def draw_distillation_apparatus(ax):
    """常压蒸馏装置示意：圆底烧瓶—蒸馏头—冷凝管—接收瓶。"""
    ax.add_patch(__import__("matplotlib").patches.Circle((0.14, 0.42), 0.09,
                 fill=False, ec="#6b7280", lw=1.2))
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.115, 0.42), 0.05, 0.06,
                 fc="#dbe6ff", ec="none", alpha=0.9))
    ax.text(0.14, 0.24, "圆底烧瓶\n（液体+沸石）", fontsize=7, ha="center", color="#4a5158")
    ax.plot([0.23, 0.42], [0.51, 0.51], color="#6b7280", lw=3)          # 蒸馏头(水平段)
    ax.text(0.32, 0.56, "蒸馏头", fontsize=7, ha="center", color="#4a5158")
    ax.plot([0.42, 0.42], [0.51, 0.40], color="#6b7280", lw=3)          # 竖直段
    ax.plot([0.42, 0.72], [0.40, 0.30], color="#2457d6", lw=3)          # 冷凝管
    ax.plot([0.42, 0.45, 0.72, 0.75], [0.44, 0.44, 0.34, 0.34], color="#9aa3b2", lw=1)
    ax.text(0.57, 0.46, "冷凝管（通冷水）", fontsize=7, ha="center", color="#2457d6")
    ax.plot([0.72, 0.78], [0.30, 0.28], color="#2457d6", lw=2)          # 接引管
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.70, 0.12), 0.16, 0.12,
                 fill=False, ec="#6b7280", lw=1.2))
    ax.add_patch(__import__("matplotlib").patches.Rectangle((0.705, 0.12), 0.15, 0.05,
                 fc="#dbe6ff", ec="none", alpha=0.9))
    ax.text(0.78, 0.05, "接收瓶（馏出液）", fontsize=7, ha="center", color="#4a5158")
    ax.plot([0.14, 0.14], [0.33, 0.10], color="#b96a00", lw=1.6)        # 加热
    _arrow(ax, 0.14, 0.06, 0.14, 0.16, color="#b96a00")
    ax.text(0.03, 0.04, "加热", fontsize=7, color="#b96a00")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
