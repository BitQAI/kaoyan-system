# V4「记」模块实施计划

- 日期：2026-10-15
- 关联 Spec：`docs/superpowers/specs/2026-10-15-kaoyan-v4-memo-module.md`
- 基线：V3 已上线，114 测试全绿
- 实施约定：沿用 V3——后端测试先行（RED→GREEN）；UI 以浏览器金路径自验为准；独立预览库（`data/preview.db`，8011）；每任务 commit + push + 汇报。

进度总览：

- [x] T1（M1）卡级调度：`card_reviews` + 引擎扩展 + `/api/card_review`
- [ ] T2（M2）memo 队列引擎 + `/api/memo/queue` + 今日页计数
- [ ] T3（M3+M4）「记」前端：翻转卡会话 + 范围面板 + 第 6 个 Tab
- [ ] T4（M6）迁移：测页去卡、今日页入口、`#s-review` 并屏
- [ ] T5（M5）看页瘦身 + 死代码清理
- [ ] T6（M7）删旧端点/测试 + 全量回归 + README + 收尾

---

## T1（M1）卡级调度

**文件清单**
- `app/schema.sql` — 新增 `card_reviews`（幂等）
- `app/services/unit_review_engine.py` — 抽出内部通用评分函数，新增 `rate_card`
- `app/routers/review_router.py` — 新增 `POST /api/card_review`
- `tests/test_unit_review_engine.py` — 或新建 `tests/test_card_review.py`（就近追加）

**接口**
```
unit_review_engine.rate_card(con, card_id, rating, today=None, days_left=None) -> {stage, due_date, graduates}
POST /api/card_review {card_id, rating} -> {ok, next:{again,hard,good,graduates}}
```
- 规则与单元完全一致（again/hard/good、毕业保留行、考前缩放）；评分只写 `card_reviews` + `daily_log.cards`，**不改考点状态**；卡不存在 404、rating 枚举校验。

**步骤**
- [x] 1. 测试先行：卡级规则矩阵（复用缩放边界因子）+ 解耦断言（评分后 progress 无变化）+ API 测试
- [x] 2. schema + 引擎 `rate_card`（内部复用 `_schedule(table,…)`）至新测试绿
- [x] 3. 路由 + 全量 `make test`；commit

**验证**：新测试绿、V3 存量绿（`unit_review_engine` 行为不变）。

---

## T2（M2）memo 队列引擎

**文件清单**
- `app/services/unit_review_engine.py` — `memo_queue(...)` 全量实现；`queue(...)` 改为其 `quick=due` 薄封装
- `app/routers/review_router.py` — `GET /api/memo/queue`；`/api/review/queue` 改薄封装
- `app/routers/plan_router.py` — `/api/plan/today` 增 `review_cards_due`；`review_session_est_min` 含卡
- `tests/test_unit_review_engine.py` — 队列合并/范围/筛选/新卡测试

**接口**
```
memo_queue(con, content, review_n, quick, subjects, chapters, points, filter, look_points, today, days_left)
  -> {items:[{kind, point_id, idx?, card_id?, stage, due_date, next}], total, shown, est_min, days_left, frozen_graduation}
GET /api/memo/queue?quick=due|today_look|fav|hot&subjects=&chapters=&points=&filter=
```
- 来源合并：到期单元 ∪ 到期考点展开 ∪ 到期卡 ∪ 范围新卡（集合为 today_look/fav/hot/显式范围时含 `stage<3` 或无记录项）
- 排序 `(stage,due)` + 科目轮转（卡归其考点科目）；默认队列 `review_n` 截断、显式范围不截断
- `queue(...)` 旧签名行为不变（V3 测试全绿是硬约束）

**步骤**
- [ ] 1. 测试先行：合并交错（单元+卡）、范围含新卡、`filter=weak/due/fav/hot`、截断/不截断、est_min、total
- [ ] 2. 实现 `memo_queue` + `queue` 薄封装；API 路由
- [ ] 3. plan_router 计数扩展 + 测试
- [ ] 4. 全量 `make test`；curl 冒烟（真实内容）；commit

---

## T3（M3+M4）「记」前端

**文件清单**
- `web/js/review.js` → `web/js/memo.js`（git mv，扩展）
- `web/index.html` — `#s-review` → `#s-memo`；tabbar 加「记」（6 列）
- `web/js/main.js` — 路由 `memo`；移除 review 引用
- `web/app.css` — 翻转卡（3D flip、玻璃）、范围面板、6 列 tabbar
- `web/js/today.js` — 复习入口改 `kyGo('memo')`（与 T4 合并亦可）

**交互（依 Spec §3.2）**
- 落地 = 范围面板：快捷 chips（今日到期/今日看点/收藏/易错·高频）+ 科目多选 + 章节多选（随科目过滤）+ 考点搜索添加 + 筛选 chips + 「开始复习（约 N 张，约 M 分钟）」
- 会话：单元卡（cue+前 12 字 → 翻转 → 完整原文）、背题卡（front → 翻转 → keywords 锚点 + back）；翻转后出现三档评分键（标下次间隔）+ 跳过；面包屑；轻恢复（`ky_review_run`，旧数据按 unit 兼容）；完成页统计
- 全局入口：`window.kyMemo`（`startDue()` 供今日页）

**步骤**
- [ ] 1. git mv + 会话翻转改造（kind 感知双卡面）
- [ ] 2. 范围面板（含 N 张估算的防抖计数）
- [ ] 3. Tab/路由/样式（含翻转 CSS 玻璃化）
- [ ] 4. 浏览器自验：金路径（含背题卡混排、翻转动效、间隔标注）+ 范围面板各模式 + 空态；commit

---

## T4（M6）迁移与导航

**文件清单**
- `web/index.html`、`web/js/quiz.js`、`web/js/today.js`、`web/js/main.js`

**改动**
- 测页移除背题卡区（`#card-box` + `renderCards/verdict/cardStep/resetCards` 及其常量）
- 今日页：复习卡改跳「记」；文案更新（「读完考点来『记』翻卡」）
- 路由与 Tab 收口检查（`kyGo('review')` 全部替换为 `memo`）

**步骤**
- [ ] 1. 测页卡片区删除 + 死引用清理
- [ ] 2. 今日页入口与文案；浏览器自验（测页无卡片、今日跳转正确）；commit

---

## T5（M5）看页瘦身

**文件清单**
- `web/js/look.js`、`web/app.css`（少量）

**改动**
- 单元 chip 去交互（只读 badge）；考点状态 chip 只读
- 删除 `rateAsk/stateAsk/allGood/chooseBox/RATE_CHOICES` 及「一键评分」「复习此点」按钮
- 保留：搜索/导航/展开/星标/问 AI/**测这个考点**/「待复习」徽标
- grep 清理其余死代码（`jumpTo` 等）

**步骤**
- [ ] 1. 只读化 + 按钮移除 + 死代码清理
- [ ] 2. 浏览器自验（阅读交互齐全、测这个考点可用、无评分弹层）；commit

---

## T6（M7）清理与收尾

**文件清单**
- `app/routers/quiz_router.py`（删 `/api/cards/review`、`CardReviewBody`）
- `tests/test_quiz_api.py`（删 `test_card_review_updates_point_state`）
- `README.md`（Tab 说明、模块描述）

**步骤**
- [ ] 1. 端点与测试删除；全量 `make test`
- [ ] 2. 浏览器主流程回归（今日/听/看/记/测/我的，浅/深抽查）
- [ ] 3. README 更新；commit + push；汇报与部署说明

---

## 收尾

- [ ] 全量回归 + push 后提醒主人宝塔拉取部署
- [ ] 上线首日检查：`card_reviews` 建表、背题卡在「记」中出现、范围队列计数合理
