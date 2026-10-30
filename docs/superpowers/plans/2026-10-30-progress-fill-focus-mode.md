# 实施计划：进度预测聚焦模式填充

依据：[spec](../specs/2026-10-30-progress-fill-focus-mode.md)

## Global Constraints

- 只改前端；不改后端、API、数据模型，不新增依赖。
- `.tsx` 硬上限 500 行；本次改动集中在 `ProgressChart.tsx` 与 `ProgressDashboard.tsx`。
- 提交前需用户确认；commit message 用英文 `type(scope): description`。
- 颜色全部用现有 CSS 变量：`--chart-ac`、`--accent`、`--chart-fc`、`--chart-goal`。

## Task 1 图表：聚焦填充与分界

文件：`frontend/src/components/ProgressChart.tsx`

- [ ] 入参增加 `focus: "memo" | "listen" | "both"`。
- [ ] 从 `lines` 解析 `focusLine` / `otherLine`；`both` 时为 null。
- [ ] 计算：
  - `actualPts = series.filter(actual)`
  - `forecastPts = [actualPts.at(-1), ...series.filter(!actual)]`
  - `actualArea` / `forecastArea`（到 y(0) 闭合）
  - `bandLow` / `bandHigh`（仅预测点有 `low_pct/high_pct` 时）
  - `lastActual`、`finishPoint`
- [ ] `<defs>` 增加：
  - `pc-fill-memo` / `pc-fill-listen` 垂直渐变（18% → 2%）
  - `pc-hatch`：10×10、`userSpaceOnUse`、`rotate(45)`、1px、`--chart-fc` 32%
  - `pc-clip`：绘图区裁剪
- [ ] 渲染顺序改为：网格 → 填充/斜纹 → 目标线/初试线/今日线 → 区间边界/所需速度 → 非聚焦线 → 实际/预测线 → 圆点/标签 → tooltip。
- [ ] 聚焦模式：
  - 实际面积填渐变；预测面积填 7% 底色 + 斜纹；应用 `pc-clip`。
  - 区间改为上下两条虚线边界，不再填色。
  - 所需速度线从今日实际点到初试 100%。
  - 非聚焦维度只画实际线，22% 透明度。
  - 预测终点画琥珀点 + `预计 MM/DD`。
- [ ] 今日分界线 + 顶部「今天」标签；初试线 + 顶部「初试」标签。
- [ ] `both` 模式保持现有行为（区间填色、两条预测虚线、无面积填充）。
- [ ] 无预测点时跳过所有预测装饰。
- [ ] 保留 tooltip、键盘、数据表；tooltip 仍显示两条线。
- [ ] `npm --prefix frontend run typecheck`。

## Task 2 页面：切换控件与图例

文件：
- `frontend/src/components/ProgressDashboard.tsx`
- `frontend/src/app/globals.css`

- [ ] 增加 `focus` 状态，默认 `"memo"`。
- [ ] `.chart-card` 顶部加 `填充 [记] [听] [双线]` 控件，按钮带 `aria-pressed`。
- [ ] `ProgressChart` 传入 `focus`。
- [ ] 图例随模式切换：
  - 聚焦：`记/听 · 实际`、`实际填充`、`预测斜线`、`80% 区间`、`所需速度`、`初试 / 100%`。
  - 双线：沿用现有图例。
- [ ] 图表下方加说明：`当前填充：记；听保留为细线。切到双线可对比。`
- [ ] CSS：
  - `.chart-focus` 分段控件
  - `.lg-fill` 渐变样本、`.lg-hatch` 斜纹样本
  - `.chart-focus-note`
  - 移动端控件换行、图例不溢出
- [ ] `npm --prefix frontend run typecheck && npm --prefix frontend run build`。

## Task 3 浏览器验证

- [ ] 示例模式：记/听/双线切换，填充、斜纹、今日分界、目标线、tooltip、数据表。
- [ ] 真实数据：`insufficient` 时无预测填充、无报错。
- [ ] 375px：无横向溢出，斜纹可辨。
- [ ] 深色模式：斜纹/底色对比正常，目标线与曲线不被遮挡。
- [ ] 控制台无报错。

## Task 4 提交

- [ ] 只暂存 `ProgressChart.tsx`、`ProgressDashboard.tsx`、`globals.css`、Spec、Plan。
- [ ] 用户确认后提交：`feat(progress): add focused forecast area fills`。
