# 实施计划：进度预测 记 / 听 双维度

依据：[spec](../specs/2026-10-30-progress-dual-dimension.md)

## Task 1 数据层：listen_event

文件：
- `backend/app/models.py`
- `backend/migrations/versions/0006_add_listen_event.py`

- [x] 新增 `listen_event` Table（id / card_id / ts）与两个索引
- [x] 迁移 0006，`down_revision = '0005'`，upgrade / downgrade 对称

## Task 2 业务层：抽出进度模块并实现双维度

文件：
- `backend/app/progress.py`（新建）
- `backend/app/service.py`（删除迁出的函数）
- `backend/app/routers/progress.py`

- [x] 从 `service.py` 迁出 `_scope_total` `_completion_first_ts` `_status` `_active_days` `streak` `daily_progress` `weekly` `milestones` `timeline`
- [x] 新增 `_listen_total` `_listen_first_ts` `_build_series` `_dimension`
- [x] `timeline()` 返回 `dimensions.memo` / `dimensions.listen` 与双维度 subjects
- [x] router 改为调用 `progress.timeline`
- [x] `mark_card_listened()` 同步写 `listen_event`
- [x] `progress_stats()` 的 `listen` 改用卡片口径

## Task 3 测试

文件：`backend/tests/test_progress.py`

- [x] 更新 timeline 形状断言（`dimensions.memo/listen`）
- [x] 新增：听维度 done 与 `card_listen` 计数一致
- [x] 新增：`mark_card_listened` 写入 `listen_event`
- [x] 新增：`progress_stats.listen` 口径
- [x] `pytest` 全绿；`alembic check` 无漂移；`alembic upgrade head` 成功

## Task 4 图表：双线 + 日期横轴

文件：`frontend/src/components/ProgressChart.tsx`

- [x] 入参改为 `lines: ChartLine[]`（key / label / tone / series）
- [x] 横轴按日期线性映射，支持两条线不同起点与终点
- [x] 每条线实际实线 + 预测虚线；今天圆点；初试竖线
- [x] 去掉斜纹面积与 100% 上的文字标签（完成日移到摘要卡）

## Task 5 页面：精简层级

文件：
- `frontend/src/components/ProgressDashboard.tsx`
- `frontend/src/app/globals.css`

- [x] `Timeline` 类型改为 `dimensions` 结构
- [x] 维度摘要双卡 + 元信息行
- [x] 双线图表 + 新图例 + 双维度 pace 脚注
- [x] 科目列表改为记 / 听双细条
- [x] 周对比 / 里程碑 / 数据质量移入 `<details>`
- [x] 示例数据同步新结构
- [x] 新增样式（dim-* / habit-line / sl-metric / more-block）

## Task 6 验证

- [x] `pytest backend/tests`
- [x] `alembic check` / `upgrade head`
- [x] 启动 backend + frontend，浏览器实测 `/me` 进度预测
- [x] 移动端宽度检查

## Task 7 提交

- [x] 单次提交：模型 + 迁移 + 后端 + 前端 + 文档
- [x] push 到 origin main
