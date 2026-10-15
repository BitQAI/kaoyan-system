# V3 记忆增强实施计划

- 日期：2026-10-15
- 关联 Spec：`docs/superpowers/specs/2026-10-15-kaoyan-v3-memory-enhancement.md`
- 基线：94 测试全绿（2026-10-15 实测）
- 实施约定：
  - 顺序 T1 → T11 → T2 → … → T9 → T10（T10 门控）；T11（液态玻璃重构）先行，后续新组件直接以玻璃令牌实现；每个任务独立可验证
  - 完成定义 = `make test` 全绿 + 浏览器自验（涉及 UI 时）+ commit + push + 汇报
  - 浏览器自验用**独立预览库**（`KY_DB_PATH=data/preview.db`），不污染真实进度数据
  - 后端测试先行（沿用 `test_review_engine.py` 规则矩阵风格）；前端以浏览器金路径验证为准
  - commit message 英文 `type(scope): description`；每个任务完成后勾选本文件对应项

进度总览：

- [x] T1 单元级调度引擎（后端）
- [x] T11 液态玻璃视觉重构（全站）
- [x] T2 复习模式 UI
- [x] T3 看页改造
- [x] T4 背题卡三屏
- [ ] T5 训练库交错 + 测这个考点
- [ ] T6 今日页时间自适应 + streak 迁移
- [ ] T7 听页节间检索提示
- [ ] T8 设置：每日复习条数
- [ ] T9 视觉编码 + 记忆统计
- [ ] T10 cue 线索标题（门控：样例先行，主人确认后全量）

---

## T1 单元级调度引擎（后端）

**文件清单**
- `app/schema.sql` — 新增 `unit_reviews`、`unit_ratings` 两表（幂等）
- `app/db.py` — 新增 `_migrate_daily_log`：`daily_log` 幂等加列 `review_n INTEGER NOT NULL DEFAULT 0`
- `app/services/unit_review_engine.py`（新）— 调度核心
- `app/services/daily_stats.py`（新）— `bump_daily(con, col, n=1)`（自 quiz_router 提取共用）
- `app/services/progress_engine.py` — 迁入 `recompute_point_state(con, point_id)`（自 progress_router）
- `app/routers/progress_router.py` — 改用迁入函数（行为不变）
- `app/routers/review_router.py`（新）— `GET /api/review/queue`、`POST /api/unit_review`
- `app/routers/quiz_router.py` — `_bump_daily` 换用 `daily_stats`
- `app/routers/plan_router.py` — streak 计入 `review_n`；`/api/plan/today` 新增 `review_units_due`、`review_session_est_min`
- `app/main.py` — 注册 `review_router`
- `tests/test_unit_review_engine.py`（新）

**接口定义**
```
unit_review_engine.next_intervals(stage, days_left) -> {again, hard, good, graduates}
unit_review_engine.rate(con, point_id, idx, rating, today=None, days_left=None) -> {stage, due_date, graduates}
unit_review_engine.queue(con, content, review_n, today=None, days_left=None, point_id=None) -> {items, due_total, shown, days_left, frozen_graduation}
progress_engine.recompute_point_state(con, point_id) -> None   # 行为与现 progress_router._recompute_point_state 一致
daily_stats.bump_daily(con, col, n=1) -> None
```
- 间隔规则：again→stage0,+1 天；hard→stage 不变,+3 天；good→stage+1（0→+3、1→+7、≥2 毕业 stage=3 保留行）
- 缩放：`days_left≤7 → 全部压缩为 1 天`；`≤21 → 上限 3 天且冻结毕业`；否则正常
- 队列：到期单元（stage<3）∪ 到期考点展开（该点无到期单元时，出未毕业单元；全毕业则跳过）；排序 (stage,due) 后按科目轮转交错；`review_n` 截断、`due_total` 为未截断数；`point` 参数单考点模式不受截断

**步骤**
- [x] 1. schema.sql 两表 + db.py daily_log 迁移
- [x] 2. daily_stats.bump_daily + quiz_router 换用（测试保持绿）
- [x] 3. progress_engine.recompute_point_state 迁入 + progress_router 改用（测试保持绿）
- [x] 4. 测试先行：`test_unit_review_engine.py` 规则矩阵 / 缩放边界(22·21·7·0) / 毕业 / 队列生成(去重·全毕业跳过·排序·交错·截断) / point 模式
- [x] 5. 实现 `unit_review_engine` 至新测试绿
- [x] 6. `review_router` 实现（rate 联动 unit_progress 状态 + recompute + bump_daily；all 批量）+ main.py 注册 + API 测试
- [x] 7. plan_router：streak 计入 review_n；plan/today 增 `review_units_due`、`review_session_est_min`（≈条数×0.2 分钟）
- [x] 8. `make test` 全绿 → commit

**验证**：新测试覆盖 + 94 存量绿；`GET /api/review/queue` 手工 curl 检查排序与字段。

---

## T11 液态玻璃视觉重构（全站）

**文件清单**
- `web/app.css`（重写为玻璃设计系统）、`web/index.html`（氛围背景层等结构微调）、`web/js/*`（仅类名/图标层面微调，不动逻辑）

**改动**
- 设计令牌 `--glass-*`（半透明底、描边高光、模糊强度、投影）；深色在 `prefers-color-scheme` 下覆盖令牌
- 固定氛围背景层（品牌色渐变光斑）作为玻璃的衬底
- 全组件玻璃化：topbar、卡片、列表行、chip、按钮（主/次/幽灵）、tabbar（悬浮玻璃）、弹层与遮罩、AI 抽屉、播放器、登录屏
- 降级：`@supports not (backdrop-filter)` → 高不透明度纯色
- 性能：控制同时模糊层数，移动端滚动实测顺畅

**步骤**
- [x] 1. 通读 app.css，盘点全部组件类
- [x] 2. 令牌 + 背景层 + 基础组件（card/chip/btn/topbar/tabbar）
- [x] 3. 收编其余组件：列表行/弹层/抽屉/播放器/登录屏
- [x] 4. 深色令牌适配
- [x] 5. 浏览器自验（手机尺寸，浅/深两态截图，对比度与滚动检查）
- [x] 6. commit

**验证**：浅色/深色截图；正文对比度可辨；降级样式存在（代码审查确认）。

---

## T2 复习模式 UI

**文件清单**
- `web/js/review.js`（新）— 复习会话
- `web/index.html` — 新增 `#s-review` 屏；`#s-today` 卡片补 id（供 T6 排序）
- `web/js/main.js` — 注册 `renderReview` / `kyGo('review')`
- `web/app.css` — 复习卡样式

**交互（依据 Spec §3.2）**
- 单条卡：面包屑（科目 > 章 > 考点短标题）→ 遮罩文本（前 12 字 + ……）→「显示原文」→ 三档按钮（忘了 +1 天 / 吃力 +3 天 / 秒答 +n 天，标注取自接口 `next`；秒答毕业时标「毕业 ↗」）+「跳过」
- 一屏一条；完成页：本次 X 条（秒答 a · 吃力 b · 忘了 c）+ 返回
- 轻恢复：`localStorage ky_review_run`（当天、进度、计数），中途退出可续
- 入口 API：`window.kyReview.start(pointId?)`（pointId 空 = 全量队列）

**步骤**
- [x] 1. 读 main.js/api.js/app.css 现有模式，确定接入点
- [x] 2. review.js 会话状态机 + 卡面渲染 + 评分提交 + 完成页 + 轻恢复
- [x] 3. index.html 屏与样式；main.js 接线
- [x] 4. 浏览器自验：进入 → 遮罩 → 揭示 → 三档评分（间隔标注）→ 跳过后继续 → 完成统计；中途退出恢复
- [x] 5. commit

**验证**：金路径截图/快照；确认评分后 `unit_reviews`/`unit_progress` 数据落库正确。

---

## T3 看页改造

**文件清单**
- `web/js/look.js`、`web/app.css`

**改动**
- 一次一考点展开（accordion：开新点自动收起旧点；`jumpTo` 兼容）
- 单元列表 >7 条：「展开剩余 N 条」
- 单元标记：循环轮转 → 显式选择层（忘了/吃力/秒答），POST `/api/unit_review`
- 考点行：状态 chip 循环 → 显式选择层（会了/半会/不会/重置未学，POST `/api/progress`）+「全部秒答」（POST `/api/unit_review` all:true）
- 展开体内新增「复习此点」（`kyReview.start(point_id)`）与「测这个考点」（跳测页 point 模式，T5 接）
- 「待复习」徽标来源改 `/api/review/queue`（点集合），保持徽标逻辑

**步骤**
- [x] 1. accordion + 单元折叠
- [x] 2. 两处显式选择层 + 全部秒答
- [x] 3. 两个直达按钮 + dueSet 切换
- [x] 4. 浏览器自验；commit

**验证**：折叠行为、评分落库、徽标与队列一致。

---

## T4 背题卡三屏

**文件清单**
- `web/js/quiz.js`、`web/app.css`

**改动**：翻面卡 → 三步（问题「先自己回忆」→ 关键词锚点（取 `point.keywords`，无则直达）→ 完整答案）+ 自评（会了/模糊/不会/跳过，行为不变）

**步骤**
- [x] 1. 三屏步进渲染 + 样式
- [x] 2. 浏览器自验（含锚点缺省、模糊重出、一轮完成重置）
- [x] 3. commit

---

## T5 训练库交错 + 测这个考点

**文件清单**
- `app/routers/quiz_router.py`、`web/js/quiz.js`、`tests/test_quiz_api.py`

**接口**：`mode += mix | point`；`mix` 按科目内洗牌后轮转交错取前 n；`point` 过滤 `point_id`

**步骤**
- [ ] 1. 后端两模式 + 测试
- [ ] 2. 前端「综合练习（跨科交错）」置顶行 + `startPoint(pointId)`（供 T3 直达）
- [ ] 3. 浏览器自验 + `make test`；commit

---

## T6 今日页时间自适应 + streak 迁移

**文件清单**
- `web/js/today.js`、`web/index.html`、`web/js/me.js`、`web/app.css`

**改动**
- 本地 <18:00：听单 → 今晚任务 → 复习 → 进度；≥18:00：复习 → 今晚任务 → 听单 → 进度（DOM 重排）
- 复习卡：`今日复习 N 条` + 「开始复习」按钮（`kyReview.start()`）；无到期时显示「今日复习已完成 ✓」
- ≥21:00 且今日无测题/评卡 → 今晚任务卡附「睡前把今天的内容过一遍——睡一觉会帮你记得更牢」
- `streak` 从今日页移除；「我的」页新增「坚持与节奏」卡（连续打卡 + 近 7 日评分统计占位，T9 补 charts）

**步骤**
- [ ] 1. 卡片 id + DOM 重排逻辑（阈值常量便于测试覆盖）
- [ ] 2. 复习卡与夜间提示；streak 迁移
- [ ] 3. 浏览器自验（console 覆写 hour 验证两种顺序）；commit

---

## T7 听页节间检索提示

**文件清单**
- `web/js/player.js`、`web/index.html`、`web/app.css`

**改动**：自动续播跨考点（或串讲→考点）时，显示过渡层「🎧 刚听完：〈上段短标题〉。先回忆：这段讲了哪几点？」；8 秒倒计时自动继续；按钮「立即继续」「回听上段」；手动点播不触发

**步骤**
- [ ] 1. 过渡层 UI + 倒计时 + 判断逻辑（用 `kyPlayer._fireEnded()` 钩子模拟验证）
- [ ] 2. 浏览器自验；commit

---

## T8 设置：每日复习条数

**文件清单**
- `app/settings_store.py`（`review_n: 60`）、`app/routers/review_router.py`（clamp 10–200）、`web/js/me.js`

**步骤**
- [ ] 1. 默认值 + clamp + 测试（settings 读写、queue 截断随 review_n 变化）
- [ ] 2. 前端输入 + 后果文案「到期复习按此上限出卡；超额顺延到下次，不会丢失」
- [ ] 3. 浏览器自验；commit

---

## T9 视觉编码 + 记忆统计

**文件清单**
- `web/js/look.js`（chip 图标前缀 ○／✓／~／✗）、`web/app.css`、`app/routers/plan_router.py`（`/api/stats` 增 `ratings_7d` 与 `today.review_n`）、`web/js/me.js`（记忆统计卡：近 7 日 秒答/吃力/忘 + 迷你条）

**步骤**
- [ ] 1. 后端 `ratings_7d` + 测试
- [ ] 2. 前端图标与统计卡；浏览器自验；commit

---

## T10 cue 线索标题（门控）

**文件清单**
- `scripts/gen_cues.py`（新，复用 gen_notes.py 的 opencode 网关模式）、`content/cues.json`、`web/js/state.js`（`displayTitle = cue || shortTitle(text)`）及各调用点

**步骤**
- [ ] 1. 脚本实现（`--limit N` / `--merge`）
- [ ] 2. 生成 20 条样例 → **主人确认**（不通过则跳过本任务）
- [ ] 3. 全量生成 + 合并 + 前端改用 displayTitle
- [ ] 4. 浏览器自验；commit

---

## 收尾

- [ ] 全量 `make test` + 浏览器主流程回归（今日/听/看/测/我的）
- [ ] 更新 README 功能说明（如涉及）
- [ ] push 后提醒主人宝塔拉取部署；上线首日检查复习队列数量与积压截断行为
