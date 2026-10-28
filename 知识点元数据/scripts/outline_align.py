"""315 大纲条目 ↔ 考点的保序最优分段对齐。

背景
----
315 的官方大纲条目（126 条，带「掌握/理解/了解」层级）是**粗粒度要求**；
考点清单（196 条）是这些要求的**细粒度展开**。二者不是 1:1：
平均每条大纲要求覆盖约 1.6 个考点。

因此不能用「逐条模糊匹配」（旧 enrich_tags.py 的做法，会跨序误配，
把「难溶电解质沉淀—溶解平衡与Ksp」配到「由溶度积原理判断沉淀的生成与溶解」）。

本模块采用 **保序分段**：
  1. 章内按出现顺序把 N 个考点切成 M 个连续段；
  2. 一段对应一条大纲要求；
  3. 用动态规划求总分最优的切分（保证不跨序、不重复）；
  4. 输出每点的 `outline_ref` + `outline_conf`（置信度），
     仅当置信度达阈值时才允许派生「大纲掌握层级」标签，否则留空并登记问题。
"""

import re

LV_MAP = {'lv-m': '掌握', 'lv-u': '理解', 'lv-k': '了解'}
LV_TO_TAG = {'掌握': '必掌握', '理解': '理解', '了解': '了解'}

# 匹配置信度阈值：低于此值不派生层级标签
CONF_THRESHOLD = 0.34
# 低于此值视为未匹配
CONF_MIN = 0.12


def norm_chapter_name(n: str) -> str:
    """章名归一化：去掉「第X章 / X、 / 有机化学第X章 / 独立成章 / 新增章」等前缀。"""
    n = n.strip()
    n = re.sub(r'独立成章|2024\s*新增章', '', n)
    n = re.sub(r'^有机化学第[一二三四五六七八九十]+章', '', n)
    n = re.sub(r'^第[一二三四五六七八九十]+章', '', n)
    n = re.sub(r'^[一二三四五六七八九十]+、', '', n)
    return n.strip()


def _bigrams(s: str) -> set:
    s = re.sub(r'[\s，,。、；;（）()「」“”\'"]', '', s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _cover(needle: set, hay: str) -> float:
    if not needle:
        return 0.0
    bg = _bigrams(hay)
    return sum(1 for g in needle if g in bg) / len(needle)


def pair_score(point: str, item: str) -> float:
    """单个考点与单条大纲要求的匹配分（0~1）。

    双向覆盖取较大值；反向（大纲→考点）打 0.85 折，
    因为大纲措辞更抽象、无字面重合不代表不对应。
    """
    pb = _bigrams(point)
    ib = _bigrams(item)
    fwd = _cover(pb, item)
    bwd = _cover(ib, point)
    return max(fwd, bwd * 0.85)


def segment(points, items):
    """把 points 按序切分成 len(items) 个连续段，每段对应一条 items。

    返回 [(segment_index, item_index, confidence)]，与 points 等长。
    DP 目标：最大化 Σ 段内最大匹配分。
    """
    n, m = len(points), len(items)
    if n == 0 or m == 0:
        return []
    if m > n:                       # 大纲条目多于考点：退化为前 m-n 条不参与
        return [(min(i, m - 1), min(i, m - 1), pair_score(p, items[min(i, m - 1)]))
                for i, p in enumerate(points)]

    # score_of[j][k] = items[j] 与 points[k] 的匹配分
    sc = [[pair_score(p, it[1]) for p in points] for it in items]

    # dp[j][i] = items[0..j] 恰好覆盖 points[0..i) 的最优总分
    NEG = float('-inf')
    dp = [[NEG] * (n + 1) for _ in range(m + 1)]
    back = [[None] * (n + 1) for _ in range(m + 1)]
    dp[0][0] = 0.0
    for j in range(m):
        for i in range(n):
            if dp[j][i] == NEG:
                continue
            best = NEG
            best_end = None
            for k in range(i + 1, n + 1):        # items[j] 覆盖 points[i..k)
                seg = max(sc[j][i:k])
                val = dp[j][i] + seg
                if val > best:
                    best, best_end = val, k
            if best_end is not None and best > dp[j + 1][best_end]:
                dp[j + 1][best_end] = best
                back[j + 1][best_end] = (i, best_end)

    # 回溯
    if dp[m][n] == NEG:                          # 不可行（m>n 已处理），退化为贪心
        return _greedy(points, items)
    cuts = []
    i = n
    for j in range(m, 0, -1):
        prev = back[j][i]
        if prev is None:
            return _greedy(points, items)
        cuts.append((prev[0], prev[1], j - 1))
        i = prev[0]
    cuts.reverse()
    out = []
    for start, end, j in cuts:
        conf = max(sc[j][start:end])
        for k in range(start, end):
            out.append((j, conf))
    return out


def _greedy(points, items):
    """DP 不可行时的贪心退化：顺序扫描，命中即推进游标。"""
    out, cur = [], 0
    for p in points:
        best, bi = 0.0, cur
        for j in range(cur, len(items)):
            s = pair_score(p, items[j][1])
            if s > best:
                best, bi = s, j
        if best > 0:
            cur = bi
        out.append((bi, best))
    return out


def align_chapter(points, items):
    """章内对齐。

    points: [考点文本]
    items:  [(层级, 大纲文本)]
    返回 [(item_index, confidence)]，与 points 等长。
    """
    if not items:
        return [(None, 0.0) for _ in points]
    seg = segment(points, items)
    return seg
