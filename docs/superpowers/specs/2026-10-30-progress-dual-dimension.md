# 进度预测：记 / 听 双维度

日期：2026-10-30
状态：已确认口径，进入实施

## 1. 背景

「我的 → 进度预测」当前只统计**记**维度：总量 = 全部卡片数，完成 = 复习过至少一次的卡（`card_progress`），每日曲线来自 `card_event` 事件流水，速度按最近 7 天摊平后线性外推到初试日。

用户的需求：进度预测要同时呈现**记**和**听**两个维度。

现状约束：

- 听的实际写入是 `card_listen`（每次听完一张卡 +1），只有 `updated_at`（最近一次），**没有事件流水**，因此历史每日曲线无法精确还原。
- `listen_progress`（按知识点）与 `point_progress.listen_at` 是旧接口 `mark_listened` 的产物，前端从不调用，实际为空。
- 「听」页使用 `/api/queue/custom?mode=listen`，粒度是**全部卡片**，没有 `listen_script` 过滤。

## 2. 目标与非目标

目标：

1. 「进度预测」页同时呈现「记」「听」两个维度，同一张图双线叠加。
2. 「听」维度支持完成率、最近 7 天日均、预计完成日、状态判定。
3. 新增 `listen_event` 事件表，从今往后「听」的每日曲线精确。
4. 精简页面信息层级：首屏只留维度摘要、双线曲线、科目进度；周对比 / 里程碑 / 数据质量下沉到折叠区。

非目标：

- 不改「听」页播放逻辑、不改音频生成。
- 不回填历史听记录（无数据源，只能推算并标注）。
- 不做新的里程碑体系（沿用现有记维度里程碑）。

## 3. 统计口径

| 维度 | 总量 | 完成 | 事件源 |
|------|------|------|--------|
| 记 | 全部卡片（3171） | `card_progress` 有记录的卡 | `card_event`，历史回落 `card_progress.updated_at` |
| 听 | 全部卡片（3171） | `card_listen` 有记录的卡 | `listen_event`，历史回落 `card_listen.updated_at` |

两个维度**同分母**，进度百分比可直接横向对比。听不是「有听稿的 538 个知识点」，因为听页实际服务全部卡片（无音频时前端用 TTS 兜底）。

速度口径与记一致：最近 7 天新增完成数 / 7；最近 7 天无新增时用 `done / 统计跨度`。

## 4. 数据模型

新增表：

```sql
listen_event(
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  card_id TEXT NOT NULL,
  ts      TEXT NOT NULL
)
CREATE INDEX idx_listen_event_card ON listen_event(card_id);
CREATE INDEX idx_listen_event_ts   ON listen_event(ts);
```

`mark_card_listened()` 在更新 `card_listen` 的同时写入一条 `listen_event`，同一事务提交。模型与 Alembic 迁移 `0006_add_listen_event` 同一次提交。

历史回落：`card_listen` 有记录但 `listen_event` 无记录的卡，用 `card_listen.updated_at` 作为首次完成日，并在 `data_quality.derived_cards` 计数（与记维度的 derived 口径一致）。

## 5. API

`GET /api/stats/timeline?days=21&sid=`

响应改为按维度嵌套（无其他消费方，直接替换）：

```json
{
  "today": "2026-10-30",
  "exam_date": "2026-12-20",
  "days_left": 51,
  "scope": "all",
  "dimensions": {
    "memo":   { "label": "记", "unit": "张", "total": 3171, "done": 24, "percent": 0.76,
                "status": "risk", "status_text": "...",
                "pace": 0, "pace_window": 7, "required_pace": 61.7,
                "finish_date": null,
                "series": [{ "date": "2026-10-29", "done": 24, "percent": 0.76, "actual": true }],
                "data_quality": { "derived_cards": 0, "recorded_cards": 24 } },
    "listen": { "... 同结构 ..." }
  },
  "subjects": [
    { "id": "812", "name": "812 植物生理学",
      "memo":   { "total": 0, "done": 0, "percent": 0, "pace": 0, "finish_date": null, "status": "empty" },
      "listen": { "... 同结构 ..." } }
  ],
  "streak": 6,
  "daily": { "goal": 30, "cards": 18, "listened": 12, "read": 5 },
  "weekly": { "this_week": 86, "last_week": 62, "delta_pct": 39, "week_start": "2026-10-26" },
  "milestones": { "count": 3, "items": [], "next": null }
}
```

`/api/stats/progress` 的 `listen` 口径同步修正：`total` = 全部卡片数，`heard` = `card_listen` 行数（原来用 `point.listen_script != ''` + 为空的 `listen_progress`，导致「已听 0/538」）。

## 6. UI

页面结构（自上而下）：

1. **维度摘要**：左右两张半卡片，记 / 听各显示百分比、`done/total 张`、状态 pill、预计完成日、一行状态说明。
2. **一行元信息**：距初试 N 天 · 连续 N 天 · 今日 记 N / 听 N。
3. **双线曲线卡片**：记（绿）与听（蓝）各画实际实线 + 预测虚线，共享 0–100% 纵轴与日期横轴；标注今天与初试竖线。不再画斜纹预测区，虚线本身表达预测。
4. **范围切换**：整体 / 四个科目 / 示例。
5. **科目列表**：每个科目两行细进度条（记 / 听），显示百分比与 done/total。
6. **折叠区「更多数据」**：本周记 N 张及环比、里程碑、数据质量说明。

图表横轴改为**按日期线性映射**（不再是数组下标），因为两个维度的实际段起点与预测终点可能不同。

颜色：记 = `--chart-ac`（绿），听 = `--accent`（蓝），初试 = `--chart-goal`。

## 7. 验证

- 后端：`pytest backend/tests`，新增用例覆盖 listen_event 写入、听维度 series 形状、口径一致性。
- 迁移：`alembic check` 无漂移、`alembic upgrade head` 成功。
- 前端：启动前后端，浏览器打开 `/me` → 进度预测，检查双线渲染、范围切换、折叠区、移动端宽度。
- 数据核对：页面「听」的 done 与 `SELECT COUNT(*) FROM card_listen` 一致。

## 8. 风险

- 历史听记录只能推算：重复听过的卡会被算晚，界面已标注 derived。
- `listen_event` 从本次上线开始积累，首周「听」的日均偏低（只有新事件），状态可能显示「有风险」，属预期。
- API 结构变更：仅 `ProgressDashboard` 一个消费方，无外部依赖。
