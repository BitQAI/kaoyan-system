# 进度预测 v2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「进度预测」从线性点估计升级为负载感知、带完成日区间的预测，并补齐可决策的 UI。

**Architecture:** 新建纯函数模块 `backend/app/forecast.py`，负责稳健速度、区间、负载逐日推演、状态判定；`progress.py` 只做数据读取与编排。前端拆出共享类型、示例数据、维度卡、科目行，图表加区间带、所需速度线、tooltip、键盘与数据表。

**Tech Stack:** Python 3.10+ / FastAPI / sqlite3；Next.js 14 / React 18 / TypeScript；零新增依赖。

**Spec:** `docs/superpowers/specs/2026-10-30-progress-forecast-v2.md`

## Global Constraints

- 不新增任何依赖，不改数据库模型，不写 Alembic 迁移。
- `.py` 硬上限 500 行、`.tsx` 硬上限 500 行；接近软上限 300 行时按计划拆分。
- API 只增字段，不删不改；旧前端必须继续可用。
- 所有 git commit 前必须得到用户明确确认；本计划先保持工作区改动，确认后统一提交。
- UI 文案用中文；commit message 用英文 `type(scope): description`。
- 预测段不得画过 `finish_latest` 或初试日后的 180 天上限，且不超过 100%。

## Review Focus

1. **零/一天历史**：`done=0`、`span<3` 时不得崩、不得给出假完成日。→ Task 4 集成测试 + Task 3 状态测试。
2. **全部学完**：`remaining=0` 时完成日必须是今天，不跑模拟。→ Task 2 `project_load` 测试。
3. **复习积压大于容量**：`due > capacity` 时新卡必须为 0、完成日可为 `None`。→ Task 2 测试。
4. **听维度无调度**：永远 `mode="linear"`、`capacity=null`，不进入负载模拟。→ Task 4 集成测试。
5. **区间/曲线越界**：预测不得越过初试与 100%，停滞时不得继续外推。→ Task 3 状态测试、Task 4 序列测试。

---

### Task 1: 纯预测模块 —— 稳健速度与区间

**Files:**
- Create: `backend/app/forecast.py`
- Create: `backend/tests/test_forecast.py`

**Interfaces:**
- Produces:
  - `smoothed_pace(per_day: dict[str, int], today: date) -> tuple[float, str]`，返回 `(pace, trend)`，`trend ∈ {"up","down","flat"}`。
  - `pace_band(per_day: dict[str, int], today: date, pace: float) -> tuple[float, float]`，返回 `(pace_low, pace_high)`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_forecast.py
from datetime import date, timedelta

import pytest

from app import forecast

TODAY = date(2026, 10, 30)


def per_day(values: list[int]) -> dict[str, int]:
    """values[0] 是今天，values[1] 是昨天，以此类推。"""
    return {(TODAY - timedelta(days=i)).isoformat(): n for i, n in enumerate(values)}


def test_smoothed_pace_steady():
    pace, trend = forecast.smoothed_pace(per_day([10] * 28), TODAY)
    assert pace == pytest.approx(10, abs=0.01)
    assert trend == "flat"


def test_smoothed_pace_stops_after_seven_empty_days():
    pace, trend = forecast.smoothed_pace(per_day([0] * 7 + [20] * 21), TODAY)
    assert pace == 0
    assert trend == "flat"


def test_smoothed_pace_detects_acceleration():
    pace, trend = forecast.smoothed_pace(per_day([20] * 7 + [0] * 21), TODAY)
    assert pace > 10
    assert trend == "up"


def test_pace_band_has_a_minimum_width():
    low, high = forecast.pace_band(per_day([10] * 14), TODAY, 10)
    assert low == pytest.approx(8)
    assert high == pytest.approx(12)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_forecast.py -q`
Expected: FAIL，`ModuleNotFoundError: app.forecast` 或 `AttributeError`。

- [ ] **Step 3: 实现**

`backend/app/forecast.py` 顶部常量：`ALPHA=0.3`、`PACE_DAYS=28`、`TREND_DAYS=14`、`BAND_DAYS=14`、`Z80=1.28`、`MIN_HALF_RATIO=0.2`。

`smoothed_pace`：先取最近 7 天，若全 0 直接返回 `(0.0, "flat")`；否则从 28 天前向今天迭代 `level = ALPHA*n + (1-ALPHA)*level`（初值 0），趋势用 `level` 与最近 14 天均值比较，差值超过 10% 为 `up`/`down`。

`pace_band`：取最近 14 天计数，均值与总体方差，`se=sqrt(var/14)`，`half=max(1.0, Z80*se, MIN_HALF_RATIO*pace)`，返回 `(max(0, pace-half), pace+half)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_forecast.py -q`
Expected: 4 passed。

- [ ] **Step 5: 提交（需用户确认）**

```bash
git add backend/app/forecast.py backend/tests/test_forecast.py
git commit -m "feat(progress): add robust pace and forecast band"
```

---

### Task 2: 纯预测模块 —— 负载推演与容量

**Files:**
- Modify: `backend/app/forecast.py`
- Modify: `backend/tests/test_forecast.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) CardState(interval: int, due: date, stage: int, difficulty: int, lapses: int, reviews: int)`
  - `@dataclass(frozen=True) Projection(finish: date | None, series: list[tuple[date, int]], review_load: float)`
  - `project_load(cards: list[CardState], done0: int, remaining: int, capacity: int, new_pace: float, today: date, horizon: date) -> Projection`
  - `steady_review_load(cards: list[CardState]) -> float`
  - `capacity_from_actions(actions: list[int], pace: float, steady: float) -> int`

- [ ] **Step 1: 写失败测试**

```python
def card(interval: int, due_in: int, stage: int = 2, difficulty: int = 2,
         lapses: int = 0, reviews: int = 1) -> forecast.CardState:
    return forecast.CardState(interval, TODAY + timedelta(days=due_in),
                              stage, difficulty, lapses, reviews)


def test_project_load_complete_immediately():
    p = forecast.project_load([], done0=100, remaining=0, capacity=30, new_pace=10,
                              today=TODAY, horizon=TODAY + timedelta(days=30))
    assert p.finish == TODAY
    assert p.series == []


def test_project_load_backlog_blocks_new_cards():
    cards = [card(1, 0) for _ in range(50)]
    p = forecast.project_load(cards, done0=50, remaining=100, capacity=30,
                              new_pace=20, today=TODAY,
                              horizon=TODAY + timedelta(days=10))
    assert p.series[0] == (TODAY + timedelta(days=1), 50)
    assert p.finish is None


def test_project_load_never_exceeds_observed_new_pace():
    p = forecast.project_load([], done0=0, remaining=100, capacity=100,
                              new_pace=5, today=TODAY,
                              horizon=TODAY + timedelta(days=30))
    assert p.series[0] == (TODAY + timedelta(days=1), 5)


def test_project_load_handles_fractional_pace():
    p = forecast.project_load([], done0=0, remaining=100, capacity=100,
                              new_pace=0.5, today=TODAY,
                              horizon=TODAY + timedelta(days=4))
    assert p.series[-1] == (TODAY + timedelta(days=4), 2)


def test_project_load_finishes_earlier_with_more_capacity():
    cards = [card(10, 5) for _ in range(20)]
    low = forecast.project_load(cards, 20, 100, capacity=10, new_pace=10,
                                today=TODAY, horizon=TODAY + timedelta(days=365))
    high = forecast.project_load(cards, 20, 100, capacity=40, new_pace=10,
                                 today=TODAY, horizon=TODAY + timedelta(days=365))
    assert low.finish and high.finish and high.finish < low.finish


def test_steady_review_load_uses_interval_reciprocal():
    cards = [card(10, 0), card(50, 0), card(0, 0)]
    assert forecast.steady_review_load(cards) == pytest.approx(1 / 10 + 1 / 50 + 1)


def test_capacity_uses_median_of_active_days():
    assert forecast.capacity_from_actions([0, 10, 20, 30, 0], pace=5, steady=2) == 20


def test_capacity_falls_back_when_no_activity():
    assert forecast.capacity_from_actions([0] * 14, pace=5, steady=2) == 7
```

- [ ] **Step 2: 跑测试确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_forecast.py -q`
Expected: FAIL，`AttributeError: module 'app.forecast' has no attribute 'project_load'`。

- [ ] **Step 3: 实现**

- `remaining == 0` 直接返回 `Projection(TODAY, [], 0.0)`。
- `capacity <= 0` 或 `new_pace <= 0` 返回 `Projection(None, [], 0.0)`。
- 用 `heapq` 存放 `(due_offset, card_index)`；逐日 `d` 从 1 到 `(horizon-today).days`：
  - 弹出 `min(due, capacity)` 张到期卡；
  - 记 `lapse_n = round(reviews * p_lapse)`，前 `lapse_n` 张按遗忘处理（`stage=0`、`interval=1`、due `d+1`），其余成功（`stage+=1`；`stage<=1` 时 `interval=1`，否则 `min(120, round(max(interval,1)*(1.6+0.3*difficulty)))`）；
  - `new = min(max(0, capacity-reviews), remaining, int(new_budget))`，其中 `new_budget` 逐日累加 `new_pace`，用掉后扣减，保证 0.5 张/天也能在两天内推进 1 张；
  - 新卡初始化 `stage=0, interval=0`，due `d+1`；`remaining -= new`；累计 `cum += new`，把 `(today+d, cum)` 加入 `series`；
  - `remaining == 0` 时 `finish = today+d` 并停止。
- `p_lapse = clamp(Σlapses/Σreviews, 0.05, 0.30)`，无数据取 `0.12`。
- `review_load` = 模拟期内 `reviews` 总数 / 模拟天数（至少 1 天）。
- `steady_review_load` 求 `Σ 1/max(1, interval)`。
- `capacity_from_actions` 取正数天数的中位数（`statistics.median`），全 0 时 `ceil(pace+steady)`，最小 1。

- [ ] **Step 4: 跑测试确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_forecast.py -q`
Expected: 12 passed。

- [ ] **Step 5: 提交（需用户确认）**

```bash
git add backend/app/forecast.py backend/tests/test_forecast.py
git commit -m "feat(progress): add load-aware projection"
```

---

### Task 3: 纯预测模块 —— 状态与置信度

**Files:**
- Modify: `backend/app/forecast.py`
- Modify: `backend/tests/test_forecast.py`

**Interfaces:**
- Produces:
  - `status(done: int, total: int, pace: float, finish: date | None, earliest: date | None, latest: date | None, exam: date, required: float | None, stalled: bool, span_days: int) -> tuple[str, str]`
  - `confidence_level(span_days: int, events: int) -> str`，返回 `"high"|"medium"|"low"`。

- [ ] **Step 1: 写失败测试**

```python
EXAM = TODAY + timedelta(days=50)


def test_status_stalled():
    s, text = forecast.status(50, 100, 0, None, None, None, EXAM, 1, True, 10)
    assert s == "stalled" and "近 7 天" in text


def test_status_risk_when_latest_misses_exam():
    s, text = forecast.status(50, 100, 2, TODAY + timedelta(days=40),
                              TODAY + timedelta(days=35),
                              TODAY + timedelta(days=55), EXAM, 1, False, 10)
    assert s == "risk" and "最晚" in text


def test_status_ok_when_latest_has_buffer():
    s, _ = forecast.status(50, 100, 2, TODAY + timedelta(days=40),
                           TODAY + timedelta(days=35),
                           TODAY + timedelta(days=45), EXAM, 1, False, 10)
    assert s == "ok"


def test_status_empty_and_insufficient():
    assert forecast.status(0, 100, 0, None, None, None, EXAM, None, False, 10)[0] == "empty"
    assert forecast.status(5, 100, 2, None, None, None, EXAM, 1, False, 2)[0] == "insufficient"


def test_confidence_levels():
    assert forecast.confidence_level(14, 100) == "high"
    assert forecast.confidence_level(7, 30) == "medium"
    assert forecast.confidence_level(6, 29) == "low"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_forecast.py -q`
Expected: FAIL，`AttributeError: ... status`。

- [ ] **Step 3: 实现**

按 Spec 3.4 的顺序判定：`empty → insufficient → stalled → pace<=0 → finish is None → finish>exam → latest>exam → required>pace*1.2 → exam-finish<7 → ok`。文案按 Spec 的四句分支返回，`risk` 且在 `latest>exam` 时用「能赶上，但最晚可能晚 N 天」。

`confidence_level`：`span>=14 且 events>=100` → high；`span>=7 且 events>=30` → medium；否则 low。

- [ ] **Step 4: 跑测试确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_forecast.py -q`
Expected: 17 passed。

- [ ] **Step 5: 提交（需用户确认）**

```bash
git add backend/app/forecast.py backend/tests/test_forecast.py
git commit -m "feat(progress): add forecast status and confidence"
```

---

### Task 4: 接入 progress.py

**Files:**
- Modify: `backend/app/progress.py`
- Modify: `backend/tests/test_progress.py`

**Interfaces:**
- Consumes: Task 1–3 的全部函数与 `CardState` / `Projection`。
- Produces: `/api/stats/timeline` 的新字段（见 Spec 第 5 节）。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_progress.py` 追加：

```python
def test_timeline_forecast_fields(client):
    got = client.get("/api/stats/timeline").json()
    for key in ("memo", "listen"):
        dim = got["dimensions"][key]
        assert {"pace_trend", "finish_earliest", "finish_latest", "mode",
                "confidence", "capacity"} <= set(dim)
        assert dim["mode"] in {"load_aware", "linear"}
        assert dim["confidence"] in {"high", "medium", "low"}
    assert got["dimensions"]["listen"]["mode"] == "linear"
    assert got["dimensions"]["listen"]["capacity"] is None


def test_timeline_series_band_shape(client):
    got = client.get("/api/stats/timeline").json()
    for dim in got["dimensions"].values():
        actual = [p for p in dim["series"] if p["actual"]]
        forecast = [p for p in dim["series"] if not p["actual"]]
        assert all("low_pct" not in p for p in actual)
        assert all(p["low_pct"] <= p["high_pct"] for p in forecast)
        assert all(p["percent"] <= 100 for p in dim["series"])


def test_timeline_review_load_shape(client):
    got = client.get("/api/stats/timeline").json()
    assert {"due_today", "steady_load"} <= set(got["review_load"])
    assert got["review_load"]["due_today"] >= 0
    assert got["review_load"]["steady_load"] >= 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_progress.py::test_timeline_forecast_fields -q`
Expected: FAIL，缺少 `pace_trend`。

- [ ] **Step 3: 实现 progress.py**

新增私有函数：

```python
def _load_cards(conn, sid: str | None, today: date) -> list[forecast.CardState]
def _daily_actions(conn, sid: str | None, today: date, days: int = 14) -> list[int]
def _due_today(conn) -> int
```

- `_load_cards` 查询 `card_progress JOIN card JOIN point`，取 `interval/due_at/stage/ease/lapses/reviews`；`ease` 即难度列；`due_at` 为空用 `today`。
- `_daily_actions` 查询 `card_event` 最近 14 天，按 `substr(ts,1,10)` 分组，补 0；带 `sid` 时 JOIN `card/point`。
- `_due_today` 查 `card_progress.due_at <= today`。

重写 `_metrics`：

- `pace, trend = forecast.smoothed_pace(per_day, today)`。
- `pace_low, pace_high = forecast.pace_band(per_day, today, pace)`。
- `own_span` = 该维度 `firsts` 最早日期到今天的天数，用于 `insufficient` 与 `confidence`；无记录时为 0。
- `events` 由 `timeline` 传入：记 = `card_event` 行数，听 = `listen_event` 行数；科目行用该科 `done`。
- `confidence = forecast.confidence_level(own_span, events)`。
- `stalled = pace == 0 and remaining > 0 and span_days >= 3`。
- 负载模式仅在 `load is not None` 且 `confidence != "low"` 且 `remaining > 0` 时启用：
  - `capacity = forecast.capacity_from_actions(actions, pace, steady)`；`capacity_low = max(1, floor(C*0.8))`、`capacity_high = max(capacity_low+1, ceil(C*1.2))`；
  - 用 `capacity_high / capacity / capacity_low` 三次 `project_load`，分别取 `finish_earliest / finish_date / finish_latest`（容量越高完成越早）；序列用中位数那次；
  - `mode="load_aware"`，`capacity={"daily_actions": C, "review_load": steady, "new_pace": min(pace, max(0, C-steady))}`；
  - 若 `capacity < steady`，状态文案覆盖为「复习已占满，新卡推不动」；
- 否则线性：`earliest/finish/latest` 由 `pace_high/pace/pace_low` 计算，`mode="linear"`，`capacity=None`。
- 状态调 `forecast.status(done, total, pace, finish, earliest, latest, exam, required, stalled, own_span)`，删除旧 `_status`。
- `finish_latest` 或 `exam` 中较早者作为预测终点；停滞时不生成预测点。

序列：

- 线性：保留现有 `_series`，预测点补 `low_pct` / `high_pct`。
- 负载：用 `Projection.series` 生成 `actual=False` 点；`low_pct` 取低容量曲线、`high_pct` 取高容量曲线在同日期的累计值。取值规则：日期早于曲线首点用 `done0`；晚于末点时，该投影已完成则取 `total`，未完则取末点；否则取不晚于该日期的最后一个点。全部 `percent <= 100`，并强制 `low_pct <= high_pct`。

`timeline`：

- 构造 `memo_cards`、`memo_actions`、`steady`，传给 memo 的 `_metrics`；listen 传 `load=None`。
- `subjects` 传 `load=None`，但 `_metrics` 走新的速度/区间/状态，输出 `finish_earliest/finish_latest/mode/confidence`。
- 顶层加 `review_load`。

- [ ] **Step 4: 跑测试**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_progress.py -q`
Expected: 全部通过；若旧断言因新增字段失败，只调整断言，不改旧字段语义。

- [ ] **Step 5: 提交（需用户确认）**

```bash
git add backend/app/progress.py backend/tests/test_progress.py
git commit -m "feat(progress): wire load-aware forecast into timeline"
```

---

### Task 5: 后端边界与兼容测试

**Files:**
- Modify: `backend/tests/test_progress.py`
- Modify: `backend/tests/test_forecast.py`

**Interfaces:**
- Consumes: Task 4 的 `timeline` 输出。

- [ ] **Step 1: 写测试**

```python
def test_timeline_keeps_legacy_fields(client):
    dim = client.get("/api/stats/timeline").json()["dimensions"]["memo"]
    assert {"total", "done", "percent", "pace", "pace_window", "required_pace",
            "finish_date", "status", "status_text", "series"} <= set(dim)


def test_subjects_have_forecast_fields(client):
    got = client.get("/api/stats/timeline").json()
    for s in got["subjects"]:
        for key in ("memo", "listen"):
            assert {"finish_earliest", "finish_latest", "mode", "confidence"} <= set(s[key])
```

另在 `test_forecast.py` 补三个边界：

```python
def test_project_load_zero_capacity_never_finishes():
    p = forecast.project_load([], 0, 10, capacity=0, new_pace=5,
                              today=TODAY, horizon=TODAY + timedelta(days=30))
    assert p.finish is None and p.series == []


def test_project_load_horizon_caps_projection():
    p = forecast.project_load([], 0, 1000, capacity=10, new_pace=10,
                              today=TODAY, horizon=TODAY + timedelta(days=5))
    assert p.finish is None and len(p.series) == 5


def test_status_late_when_finish_after_exam():
    s, _ = forecast.status(50, 100, 2, EXAM + timedelta(days=1), None, None,
                           EXAM, 1, False, 10)
    assert s == "late"
```

- [ ] **Step 2: 跑测试**

Run: `backend/.venv/bin/python -m pytest backend/tests -q`
Expected: 全部通过。

- [ ] **Step 3: 提交（需用户确认）**

```bash
git add backend/tests
git commit -m "test(progress): cover forecast boundaries and compatibility"
```

---

### Task 6: 前端类型与文件拆分（行为不变）

**Files:**
- Create: `frontend/src/lib/progress-types.ts`
- Create: `frontend/src/lib/progress-demo.ts`
- Create: `frontend/src/components/DimCard.tsx`
- Create: `frontend/src/components/SubjectRow.tsx`
- Modify: `frontend/src/components/ProgressDashboard.tsx`
- Modify: `frontend/src/components/ProgressChart.tsx`

**Interfaces:**
- Produces:
  - `progress-types.ts`：`DimStatus`、`SeriesPoint`、`DimStat`、`SubjectDim`、`SubjectLine`、`Timeline`，字段与 Spec 第 5 节一致。
  - `progress-demo.ts`：`demoData(): Timeline`，包含新增字段。
  - `DimCard({ kind, dim }: { kind: "memo" | "listen"; dim: DimStat })`。
  - `SubjectRow({ s }: { s: SubjectLine })`。

- [ ] **Step 1: 抽出类型与示例数据**

把 `SeriesPoint`/`ChartLine` 从 `ProgressChart.tsx` 移到 `progress-types.ts`；把 `DimStatus`/`DimStat`/`SubjectDim`/`SubjectLine`/`Timeline` 从 `ProgressDashboard.tsx` 移入。把 `demoDim`/`demoSubject`/`demoData` 移到 `progress-demo.ts`。示例数据补 `finish_earliest`、`finish_latest`、`pace_trend`、`mode: "load_aware"`、`confidence: "high"`、`capacity`，`series` 预测点补 `low_pct`/`high_pct`。

- [ ] **Step 2: 抽出子组件**

`DimCard.tsx`：现有维度卡 JSX 原样搬出，`kind` 类型收窄为 `"memo" | "listen"`。
`SubjectRow.tsx`：现有科目行 JSX 原样搬出。
`ProgressDashboard.tsx` 只保留数据加载、范围切换、图表/折叠区组合。

- [ ] **Step 3: 类型检查**

Run: `npm --prefix frontend run typecheck`
Expected: 无错误。

- [ ] **Step 4: 构建**

Run: `npm --prefix frontend run build`
Expected: 成功。

- [ ] **Step 5: 提交（需用户确认）**

```bash
git add frontend/src/lib/progress-types.ts frontend/src/lib/progress-demo.ts \
  frontend/src/components/DimCard.tsx frontend/src/components/SubjectRow.tsx \
  frontend/src/components/ProgressDashboard.tsx frontend/src/components/ProgressChart.tsx
git commit -m "refactor(progress): split dashboard types and components"
```

---

### Task 7: 图表 —— 区间带、所需速度线、tooltip、键盘、数据表

**Files:**
- Modify: `frontend/src/components/ProgressChart.tsx`
- Modify: `frontend/src/app/globals.css`

**Interfaces:**
- Consumes: `ChartLine.series[].low_pct/high_pct`。
- Produces: `ProgressChart({ lines, examDate, today, height?, summary? })`。

- [ ] **Step 1: 加区间带与所需速度线**

对每条线：
- 预测点有 `low_pct`/`high_pct` 时，用 `high` 正向、`low` 反向闭合成 `<path d={area} fill={color} opacity=".12" />`。
- 从 `(today, 该线 todayPct)` 到 `(examDate, 100)` 画 `strokeDasharray="2 5"`、`strokeWidth=1`、`opacity=.45` 的同色细线。
- 记/听预测线使用不同虚线节奏（记 `6 4`、听 `2 3`），今天圆点用不同描边粗细，确保不只靠颜色区分。

- [ ] **Step 2: 加交互**

`hoverDate` 状态；`onPointerMove` 用 `getBoundingClientRect()` 把横坐标映射到最近日期；`onPointerDown` 在触屏上同样选中；`onPointerLeave` 清除。渲染竖向 crosshair 与 tooltip（日期、每条线的百分比与区间）。容器 `tabIndex={0}`，`onKeyDown` 处理 `ArrowLeft/ArrowRight/Escape`。

- [ ] **Step 3: 加 aria 与数据表**

`aria-label` 使用 `summary` 参数（缺省时回退「记与听的学习进度曲线与预测」）。图下渲染：

```tsx
<details className="chart-table">
  <summary>查看数据表</summary>
  <table>…日期 / 记 / 听 / 区间…</table>
</details>
```

表格数据必须与图表使用同一个 `series`，不得另算。

- [ ] **Step 4: 样式**

在 `globals.css` 追加 `.pc-band`、`.pc-ideal`、`.pc-cross`、`.pc-tip`、`.chart-table`、`.chart-table table`、`.chart-table th/td`，颜色沿用现有 CSS 变量。

- [ ] **Step 5: 类型检查与构建**

Run: `npm --prefix frontend run typecheck && npm --prefix frontend run build`
Expected: 均成功。

- [ ] **Step 6: 提交（需用户确认）**

```bash
git add frontend/src/components/ProgressChart.tsx frontend/src/app/globals.css
git commit -m "feat(progress): add forecast band, tooltip and chart table"
```

---

### Task 8: 页面 —— 区间文案、缺口、负载行、科目状态

**Files:**
- Modify: `frontend/src/components/DimCard.tsx`
- Modify: `frontend/src/components/SubjectRow.tsx`
- Modify: `frontend/src/components/ProgressDashboard.tsx`
- Modify: `frontend/src/app/globals.css`

**Interfaces:**
- Consumes: Task 4 的 API 字段与 Task 6 的类型。

- [ ] **Step 1: 维度卡**

- `STATUS_LABEL` 增加 `stalled: "停滞"`。
- 预计完成显示 `finish_date（最早 finish_earliest · 最晚 finish_latest）`，缺失时「暂无预测」。
- `capacity` 存在时显示「复习占用 X 张/天 · 可分配新卡 Y 张/天」。
- `confidence === "low"` 时显示「数据不足，仅供参考」。
- `status_text` 直接展示后端文案。

- [ ] **Step 2: 科目行**

每行右侧增加状态 chip 与完成日（`finish_date` 或「暂无」），用现有 `.dh-pill` 样式与 `st-*` 颜色。

- [ ] **Step 3: 习惯行与停滞提示**

- 习惯行增加「今日到期 {review_load.due_today} 张」。
- 两条线都停滞时，图表下方显示 `.chart-stall`：「近 7 天没有新增，先恢复学习节奏」。

- [ ] **Step 4: 样式与示例数据联动**

补 `.dim-load`、`.sl-chip`、`.chart-stall`、`.st-stalled`；确认示例模式新字段齐全。

- [ ] **Step 5: 类型检查与构建**

Run: `npm --prefix frontend run typecheck && npm --prefix frontend run build`
Expected: 均成功。

- [ ] **Step 6: 提交（需用户确认）**

```bash
git add frontend/src/components/DimCard.tsx frontend/src/components/SubjectRow.tsx \
  frontend/src/components/ProgressDashboard.tsx frontend/src/app/globals.css
git commit -m "feat(progress): surface range, gap and review load"
```

---

### Task 9: 全量验证

- [ ] **Step 1: 后端测试**

Run: `backend/.venv/bin/python -m pytest backend/tests -q`
Expected: 全部通过。

- [ ] **Step 2: 前端检查**

Run: `npm --prefix frontend run typecheck`
Expected: 无错误。

Run: `npm --prefix frontend run build`
Expected: 成功。

- [ ] **Step 3: 启动并实测**

启动后端与前端，浏览器打开 `http://localhost:3000/me` → 进度预测：
- 示例模式：区间带、双线、所需速度线、tooltip、数据表正常。
- 真实/空数据：无预测时不画区间、不报错。
- 移动端宽度 375px：维度卡单列、图表不溢出、tap 出 tooltip。
- 键盘：Tab 聚焦图表，←/→ 移动，Esc 关闭。

- [ ] **Step 4: 性能**

Run: `time curl -s -H "Authorization: Bearer <token>" http://localhost:8000/api/stats/timeline > /dev/null`
Expected: < 300ms（本地 3171 卡）。若超预算，按 Spec 风险项降级为单次中位数模拟。

- [ ] **Step 5: 提交（需用户确认）**

```bash
git add -A
git commit -m "feat(progress): load-aware forecast with uncertainty"
```

---

## 执行方式

用户已指定「先写 Spec，再进入实现」，按 Native 方式在当前会话逐 Task 实施；每个 Task 完成后先跑测试，提交前单独向用户确认。
