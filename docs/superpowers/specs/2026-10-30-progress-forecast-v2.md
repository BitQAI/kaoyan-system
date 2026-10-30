# 进度预测 v2：负载感知与不确定性

日期：2026-10-30
状态：待确认，确认后进入实施

## 1. 背景

现有「进度预测」是记 / 听双维度线性外推：完成 = 卡片至少复习过一次；速度 = 最近 7 天新增 / 7，近 7 天无新增时回落到累计均值；预计完成日 = 今天 + 剩余 ÷ 速度；只给点估计。

调研（exa，2026-10-30）确认四个会系统性高估进度的点：

1. 队列是「到期卡优先、新卡垫底」（`service.card_queue`）。已学卡转成复习负载后会挤占新卡，而线性外推假设新卡速度恒定，越到后期越乐观。Anki / FSRS 的成熟做法是逐日推演复习负载与遗忘。
2. 近 7 天无新增时，速度回落到「累计完成 ÷ 总天数」，会把停滞误判成正常推进，状态仍可能给 `ok`。
3. 完成口径包含评「忘了」的卡（`grade_card` 无论评分都写 `card_progress`），覆盖率不等于掌握度。
4. 只给一个完成日，没有区间；项目管理领域用 P50 / P80 或乐观 / 悲观双线表达不确定性。

本 Spec 解决 1、2、4，并把 3 作为非目标留到下一版。

## 2. 目标与非目标

目标：

1. **停滞可见**：近 7 天无新增时速度归零，状态为 `stalled`，不再外推假完成日。
2. **速度稳健**：用指数平滑替代硬窗口，并输出趋势（加速 / 放缓 / 平稳）。
3. **完成日区间**：给出最早 / 最可能 / 最晚三个完成日；状态用最晚完成日做保守判断。
4. **负载感知**：记维度按「每日容量 = 复习 + 新卡」逐日推演，复习挤占新卡时预测曲线自动放缓。
5. **UI 可决策**：预测区间带、所需速度线、缺口文案、tooltip / 键盘 / 移动端交互。
6. **兼容**：保留现有字段，新增字段可空；旧前端不崩。

非目标：

- 不迁移 FSRS，不改 `scheduler.py` 的三档调度。
- 不改「完成」语义（仍为至少复习过一次）；掌握度 / ΣR 放到 v3。
- 不改听页播放、音频生成、AI 助手。
- 不做逐题掌握度列表，不做新的里程碑体系。
- 不做机器学习模型（单用户、短历史，必然过拟合）。

## 3. 统计口径

### 3.1 维度

| 维度 | 总量 | 完成 | 调度数据 |
|------|------|------|----------|
| 记 | 全部卡片 | `card_progress` 有记录 | `interval` / `due_at` / `stage` / `difficulty` / `lapses` / `reviews` |
| 听 | 全部卡片 | `card_listen` 有记录 | 无，保持线性稳健外推 |

听维度没有 due 概念，无法做负载推演，标记 `mode="linear"`，界面注明。

### 3.2 稳健速度

- 取每日**首次**完成数 `n_i`（重复复习不计入速度，但仍计入复习负载）。
- 简单指数平滑：`L_0 = 0`；对最近 28 天逐日 `L = α·n + (1-α)·L`，`α = 0.3`；`pace = L`。
- **停滞覆盖**：最近 7 天 `n` 全为 0 → `pace = 0`，`status = stalled`。
- **冷启动**：统计跨度 < 3 天 → `insufficient`，不做预测。
- **趋势**：`L` 与最近 14 天简单均值比较，差值超过 10% 记 `up` / `down`，否则 `flat`。
- 保留 `pace_window = 28`；前端文案从「近 N 天日均」改为「近期日均」。

### 3.3 完成日区间

- 近 14 天日新增的标准误 `SE = std / √14`。
- `half = max(1, 1.28 · SE, 0.2 · pace)`，即 80% 区间，且至少 ±20%，避免数据平稳时出现假精确。
- `pace_low = max(0, pace - half)`，`pace_high = pace + half`。
- 线性模式：`finish_earliest = 今天 + 剩余 / pace_high`，`finish_latest = 今天 + 剩余 / pace_low`。
- 负载模式：用 `capacity_low` / `capacity` / `capacity_high` 各跑一次模拟（容量区间同样至少 ±20%），取三个完成日。
- 无预测时三个日期均为 `null`。

命名约定：`finish_earliest` = 乐观（快），`finish_date` = 最可能（P50），`finish_latest` = 悲观（慢）。

### 3.4 状态

| 状态 | 条件 |
|------|------|
| `empty` | `done = 0` |
| `insufficient` | 统计跨度 < 3 天 |
| `stalled` | 近 7 天无新增且还有剩余 |
| `late` | `finish_date > exam` |
| `risk` | `finish_date <= exam` 但 `finish_latest > exam`，或 `exam - finish_date < 7` 天，或 `required > pace × 1.2` |
| `ok` | `finish_date <= exam` 且 `finish_latest <= exam` 且缓冲 ≥ 7 天 |

文案必须可行动，按分支给出：

- 「按当前速度能赶上，但最晚可能晚 N 天」
- 「每天还差 X 张（当前 Y / 需要 Z）」
- 「复习已占满，新卡推不动」
- 「近 7 天没有新增，先恢复学习节奏」

## 4. 负载感知模型

### 4.1 输入

- `learned`：每张已学卡的 `interval`、`due_at`、`stage`、`difficulty`、`lapses`、`reviews`。
- `remaining`：未学卡数。
- `C`：每日总动作容量。
- `horizon`：`min(exam + 30 天, today + 365 天)`，至少覆盖初试日。
- `p_lapse = clamp(Σlapses / Σreviews, 0.05, 0.30)`，无复习数据时取 `0.12`。
- `growth(difficulty) = 1.6 + 0.3 × difficulty`，与 `scheduler.next_state` 保持一致，上限 `MAX_INTERVAL = 120`。
- 新卡首次：`interval = 1`、`stage = 1`、`difficulty = 已学卡均值`（无数据时 2）。

### 4.2 逐日推演

1. `due` = 所有 `due_at <= day` 的卡（含积压）。
2. `reviews = min(due, C)`；超出部分留到明天，与 `service.card_queue` 的「到期优先 + limit」一致。
3. `new = min(max(0, C - reviews), remaining)`。
4. 每张被复习的卡，按 `p_lapse` 拆分计数（不逐卡随机，保证确定性）：
   - 遗忘部分：`interval = 1`、`stage = 0`、`due = day + 1`；
   - 成功部分：`stage += 1`；`interval = 1`（`stage <= 1`），否则 `min(120, round(max(interval,1) × growth))`；`due = day + interval`。
5. 新卡计入完成数；`remaining -= new`。
6. `remaining = 0` 的当天即完成日。

实现按 `due` 日分桶 + 按 `(interval, stage, difficulty)` 分组计数，避免逐卡逐日扫描；上界为 `O(天数 × 分组数)`。

### 4.3 容量估计

- `actions_i` = 近 14 天每天 `card_event` 总数（复习 + 新卡）。
- `C` = 有记录日的中位数；无记录时 `C = max(pace + steady_load, 1)`。
- `steady_load = Σ 1 / max(1, interval)`（Anki daily load 口径），用于文案与 fallback。
- 若 `C < steady_load`，说明复习已占满容量：新卡速度接近 0，状态文案提示。
- **置信度**：跨度 ≥ 14 天且事件 ≥ 100 → `high`；跨度 ≥ 7 天且事件 ≥ 30 → `medium`；否则 `low`。`low` 时回退线性模型并标 `mode="linear"`。

### 4.4 科目级

主维度跑 3 次模拟（低 / 中 / 高容量）。科目行保持**线性稳健预测**，避免 4 × 3 次模拟和容量分摊假设；科目行只补 `finish_date`、`finish_earliest`、`finish_latest`、`status`、`mode`。

## 5. API

`GET /api/stats/timeline?days=21&sid=`

新增字段（只增不改，向后兼容）：

```json
{
  "dimensions": {
    "memo": {
      "pace": 12.4,
      "pace_window": 28,
      "pace_trend": "flat",
      "finish_date": "2026-12-10",
      "finish_earliest": "2026-12-04",
      "finish_latest": "2026-12-18",
      "status": "risk",
      "status_text": "按当前速度能赶上，但最晚可能晚 2 天",
      "mode": "load_aware",
      "confidence": "high",
      "capacity": { "daily_actions": 30, "review_load": 18.2, "new_pace": 11.8 },
      "series": [
        { "date": "2026-11-01", "done": 240, "percent": 7.6,
          "actual": false, "low_pct": 7.2, "high_pct": 8.1 }
      ],
      "data_quality": { "derived_cards": 0, "recorded_cards": 240 }
    },
    "listen": { "... 同结构，mode=linear，capacity=null ..." }
  },
  "review_load": { "due_today": 42, "steady_load": 18.2 },
  "subjects": [
    { "id": "812", "name": "812 植物生理学",
      "memo": { "...", "finish_earliest": "...", "finish_latest": "...",
                "mode": "linear", "confidence": "medium" } }
  ]
}
```

- `series` 中 `actual=true` 的点不带 `low_pct` / `high_pct`。
- 预测段在 `finish_latest` 处停止；超过初试的预测不画满，保持「曲线停在 100% 以下 = 赶不上」的现有语义。
- `review_load.due_today` 直接查 `card_progress.due_at <= today`，用于 UI 积压提示。

## 6. UI

页面结构保持现有顺序，逐块增强：

1. **维度卡**
   - 主数字百分比。
   - 预计完成：`12/10（最早 12/04 · 最晚 12/18）`；无预测显示「暂无预测」。
   - 状态 pill 增加 `stalled`；文案含缺口，如「每天还差 8 张」。
   - 记维度底部增加负载行：「复习占用 18 张/天 · 可分配新卡 12 张/天」；`capacity=null` 时不显示。
   - `confidence=low` 时增加「数据不足，仅供参考」。
2. **图表**
   - 实际实线 + P50 预测虚线 + 同色低透明度区间带（`finish_earliest` ~ `finish_latest`）。
   - 从今天到初试 100% 的「所需速度」细虚线。
   - 今天圆点、初试竖线、完成日标记。
   - 图例用大白话：「80% 预测区间」，不写「置信区间」。
   - 停滞时预测段不画，图上标注「近 7 天无新增」。
3. **交互**
   - 桌面 hover、移动端 tap / 长按显示 crosshair + tooltip（日期、记 / 听百分比、区间）。
   - 键盘：图容器可聚焦，← / → 移动日期点，Esc 关闭。
   - `aria-label` 一句话总结；图下提供「查看数据表」折叠表格（日期 / 记 / 听 / 区间）。
   - 不只靠颜色区分记 / 听：虚线样式或端点形状至少再给一种编码。
4. **科目行**
   - 每科增加状态 chip 与预计完成日，不再只有进度条。
5. **习惯行**
   - 增加「今日到期 N 张」，把复习积压前置。
6. **保留项**
   - 示例模式、「更多数据」折叠、derived 提示保持不变；示例数据同步新增字段。

## 7. 验证

- **纯函数单测**（`backend/tests/test_progress.py`）：
  - 平稳 10 张/天 → 速度接近 10；加速 → `pace_trend=up`；单日突击后停滞 → `stalled`、`pace=0`。
  - 区间下限：数据完全平稳时 `half >= 0.2 × pace`。
  - 负载模拟：`due > C` 时 `new=0`、完成日晚于线性；`p80 >= p50 >= p20`。
  - 听维度始终 `mode="linear"`。
- **集成**：timeline 新字段存在且类型正确；stalled 场景；旧字段（`pace` / `finish_date` / `series`）保持兼容。
- **前端**：`npm --prefix frontend run typecheck`、`run build`；浏览器打开 `/me` 实测示例、空数据、真实数据、移动端宽度、tooltip、键盘、图例、数据表。
- **性能**：本地 3171 卡下 `/api/stats/timeline` < 300ms；超预算则先简化为单次中位数模拟 + 解析区间。
- **迁移**：无模型改动，不需要 Alembic。

## 8. 风险

- 负载模型参数来自自研三档调度器，样本少时会偏；用 clamp、区间、confidence 三层兜底，不追求精确。
- 容量 `C` 用事件数近似，没有计每题耗时；不同题型耗时差异未建模。
- 听维度无调度，无法负载感知，只能线性，界面注明。
- 区间在数据少时可能很宽；用至少 ±20% 和 confidence 档位避免假精确，也避免过度自信。
- 三次模拟有性能成本；先做基准，必要时降级为一次中位数模拟 + 解析区间。
