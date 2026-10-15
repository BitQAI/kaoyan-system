# V5 复习调度重设计 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把固定 3 档间隔（1/3/7 天 + 毕业即消失）替换为「考试锚定的分档间隔」，让每条内容的记忆强度在 2026-12-19 达到峰值。

**Architecture:** 间隔不再是常量表，而是按「剩余次数几何铺开剩余天数」计算：`gap = (days_left − jitter) / (2^k_remain − 1)`。曝光次数 K 按 `chapter.tier` 分档（卡 6 / 梯队一 4 / 梯队二 2 / 梯队三 2）。队列排序加入 tier，使末段容量不足时高价值内容优先。不新增表、不新增列、无迁移。

**Tech Stack:** Python 3.11 / FastAPI / SQLite(WAL) / 原生 JS PWA / pytest

**Spec:** `docs/superpowers/specs/2026-10-15-kaoyan-v5-schedule.md`

## Global Constraints

- **不新增表、不新增列、不跑迁移**；K 由 `chapter.tier` 现算（Spec §5）
- **不引入新依赖**，不实现 FSRS（Spec §4.2）
- K 取值：背题卡 **6**、tier=1 **4**、tier=2 **2**、tier=3 **2**、无 tier 缺省 **2**（Spec §4.3）
- `jitter = 1 + int(md5(item_key).hexdigest()[:8], 16) % 21`，值域 **[1, 21]**，必须确定性（Spec §4.1）
- `review_n` 默认 **260**，clamp **100–300**（Spec §3.1 M4）
- **容量分配 = 严格梯队优先，不设配额**；第 3 梯队被饥饿是有意取舍（Spec §6.1）
- 队列排序键：`(tier, stage, due_date, point_id, kind, tail)`（Spec §6.1）
- **删除** `frozen()` / `cap_days()` / `GRADUATE_STAGE` / `GOOD_DAYS` / `GOOD_DAYS_TAIL` / `AGAIN_DAYS` / `HARD_DAYS` / 响应字段 `frozen_graduation`（Spec §9.2）
- **不变更**：跨科轮转交错、队列四来源合并、显式范围不截断、快捷与筛选集合（Spec §9.3）
- `EXAM_DATE = "2026-12-19"`（`app/services/plan_engine.py:7`），`days_left()` 为唯一锚点输入
- 提交信息用英文 `type(scope): description`

## Review Focus

以下五类是 Spec 隐含但任务测试可能覆盖不到的失效模式，**每条都必须有对应测试**（已在 T1/T2/T3 各步内标注）：

1. `days_left ≤ jitter` → `R < 1` → 必须毕业而非崩溃或产生负间隔（T1 Step 1）
2. 遗留 `stage = 3` 行（V3 旧「毕业」语义）在 tier=1（K=4）下会**复活出卡**，在 tier=2/3（K=2）下仍为毕业（T2 Step 1）
3. `jitter` 只有 21 个取值 → 同日 jitter 碰撞导致的**同日堆积**（T3 Step 1 用分布断言而非单点断言）
4. `stage > k` 的异常输入（脏数据）→ 必须判毕业而非 `2 ** 负数`（T1 Step 1）
5. 单元与背题卡的 tier **来源不同**：单元在考点级、卡片挂在章级 `chap["cards"]`（T2 Step 1 分别断言）

---

## 文件结构

| 文件 | 职责 | 变更 |
|---|---|---|
| `app/services/unit_review_engine.py` | 调度引擎：间隔计算、评分推进、队列 | 重写核心 |
| `app/content.py` | 内容索引：新增 tier 映射 | 追加 2 函数 |
| `app/routers/review_router.py` | HTTP 层：注入 tier、返回 next | 改 3 处 |
| `app/settings_store.py` | 设置默认值与 clamp | 改 2 行 |
| `web/js/memo.js` | 翻转卡 UI | 改间隔标注 + tier 徽标 |
| `web/js/me.js` | 设置页 | 改 review_n 输入范围 |
| `tests/test_unit_review_engine.py` | 引擎测试 | 重写矩阵 |
| `tests/test_memo_queue.py` | 队列测试 | 补 tier 排序 |
| `scripts/simulate_schedule.py` | 负载模拟（新交付） | 新建 |

---

## Task 1（T1 / M1）间隔计算式

**文件清单**
- Modify: `app/services/unit_review_engine.py:15-56`（常量区 + `next_intervals`）
- Test: `tests/test_unit_review_engine.py:42-54`（`test_next_intervals_matrix` 重写）

**接口**
```python
target_k(kind: str, tier: int | None) -> int          # kind: "unit" | "card"
unit_key(point_id: str, idx: int) -> str              # f"{point_id}#{idx}"
jitter(key: str) -> int                               # ∈ [1, 21]
next_intervals(stage: int, k: int, days_left: int, key: str) -> dict
    # -> {"again": int, "hard": int, "good": int | None, "graduates": bool}
```

**步骤**

- [ ] **Step 1: 写失败测试**

替换 `tests/test_unit_review_engine.py:42-54` 的 `test_next_intervals_matrix`：

```python
def test_target_k_by_kind_and_tier():
    from app.services import unit_review_engine as e

    assert e.target_k("card", 1) == 6 and e.target_k("card", 3) == 6
    assert e.target_k("unit", 1) == 4
    assert e.target_k("unit", 2) == 2 and e.target_k("unit", 3) == 2
    assert e.target_k("unit", None) == 2


def test_jitter_deterministic_and_bounded():
    from app.services import unit_review_engine as e

    assert e.jitter("A-1-01#0") == e.jitter("A-1-01#0")          # 确定性
    vals = {e.jitter(f"A-1-01#{i}") for i in range(200)}
    assert vals <= set(range(1, 22)) and len(vals) == 21          # 覆盖 [1,21]


def test_next_intervals_follows_exam_anchor():
    from app.services import unit_review_engine as e

    key = "A-1-01#0"
    j = e.jitter(key)                       # 固定值，测试用

    # T1（K=4）：k_remain 3 → 2 → 1，末次落在考前 j 天
    d0 = e.next_intervals(0, 4, 65, key)    # 学习后 stage=0 → good 推 stage=1
    assert d0["graduates"] is False and d0["again"] == 1
    assert d0["good"] == round((65 - j) / (2 ** 3 - 1))
    assert d0["hard"] == max(1, round(d0["good"] / 2))

    # stage=3 时 good 毕业（K=4）
    assert e.next_intervals(3, 4, 65, key)["good"] is None
    assert e.next_intervals(3, 4, 65, key)["graduates"] is True


def test_next_intervals_edges():
    from app.services import unit_review_engine as e

    key = "A-1-01#0"
    j = e.jitter(key)

    # 边界 1（Review Focus #1）：days_left 小于 jitter → 毕业，不崩、不负数
    r = e.next_intervals(1, 4, j - 1, key)
    assert r["good"] is None and r["graduates"] is True

    # 边界 2（Review Focus #4）：stage > k（脏数据）→ 毕业，不产生 2**负数
    assert e.next_intervals(9, 2, 65, key)["graduates"] is True

    # 边界 3：K=2 的单元，学习后 stage=0 → good 只剩 1 次，间隔 = 剩余全额
    assert e.next_intervals(0, 2, 65, key)["good"] == max(1, 65 - j)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/huajun/Sync/kaoyan-system && .venv/bin/pytest tests/test_unit_review_engine.py -k "target_k or jitter or exam_anchor or edges" -v`
Expected: FAIL — `AttributeError: module 'app.services.unit_review_engine' has no attribute 'target_k'`

- [ ] **Step 3: 实现**

替换 `app/services/unit_review_engine.py` 的常量区（第 15–19 行）与 `next_intervals`（第 47–56 行）：

```python
import hashlib

K_CARD = 6
K_BY_TIER = {1: 4, 2: 2, 3: 2}
K_DEFAULT = 2
JITTER_SPAN = 21


def target_k(kind: str, tier: int | None) -> int:
    """目标评分次数（含首次学习评分）。"""
    if kind == "card":
        return K_CARD
    return K_BY_TIER.get(tier if tier is not None else K_DEFAULT, K_DEFAULT)


def unit_key(point_id: str, idx: int) -> str:
    return f"{point_id}#{idx}"


def jitter(key: str) -> int:
    """确定性抖动 ∈ [1, JITTER_SPAN]，把末次复习分散到考前 1–21 天。"""
    return 1 + int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16) % JITTER_SPAN


def _gap(stage: int, k: int, days_left: int, key: str) -> int | None:
    """stage 为「评分后的新 stage」。None 表示应毕业。"""
    kr = k - stage                       # 剩余复习次数（含即将安排的这次）
    if kr <= 0:
        return None
    r = days_left - jitter(key)
    if r < 1:
        return None
    return max(1, round(r / (2 ** kr - 1)))


def next_intervals(stage: int, k: int, days_left: int, key: str) -> dict:
    """各档评分对应的下次间隔天数（good=None 表示毕业）。"""
    good = _gap(stage + 1, k, days_left, key)
    if good is None:
        hard = max(1, round((days_left - jitter(key)) / 2))
    else:
        hard = max(1, round(good / 2))
    return {"again": 1, "hard": hard, "good": good, "graduates": good is None}
```

同时删除 `GRADUATE_STAGE` / `GOOD_DAYS` / `GOOD_DAYS_TAIL` / `AGAIN_DAYS` / `HARD_DAYS` / `frozen()` / `cap_days()`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/huajun/Sync/kaoyan-system && .venv/bin/pytest tests/test_unit_review_engine.py -k "target_k or jitter or exam_anchor or edges" -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd /Users/huajun/Sync/kaoyan-system
git add app/services/unit_review_engine.py tests/test_unit_review_engine.py
git commit -m "feat(schedule): exam-anchored interval formula with tiered K"
```

---

## Task 2（T2 / M2）评分推进接 tier

**文件清单**
- Modify: `app/content.py`（追加 `point_tier_map` / `card_tier_map`）
- Modify: `app/services/unit_review_engine.py:59-101`（`_schedule` / `rate` / `rate_card`）
- Test: `tests/test_unit_review_engine.py`（`test_rate_transitions` 重写 + 新增兼容测试）

**接口**
- Consumes: T1 的 `target_k` / `unit_key` / `jitter` / `_gap`
- Produces:
```python
content.point_tier_map(content: dict) -> dict[str, int]   # point_id -> tier
content.card_tier_map(content: dict) -> dict[str, int]    # card_id  -> tier
unit_review_engine.rate(con, point_id, idx, rating, k, today=None, days_left=None) -> dict
unit_review_engine.rate_card(con, card_id, rating, k, today=None, days_left=None) -> dict
    # -> {"stage": int, "due_date": str, "graduates": bool}
```

**步骤**

- [ ] **Step 1: 写失败测试**

在 `tests/test_unit_review_engine.py` 中重写 `test_rate_transitions` 并新增两条：

```python
def test_rate_transitions(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    key, k = e.unit_key("A-1-01", 0), 4
    j = e.jitter(key)

    r = e.rate(con, "A-1-01", 0, "again", k, today=T, days_left=65)
    assert (r["stage"], r["due_date"], r["graduates"]) == (0, "2026-10-16", False)

    r = e.rate(con, "A-1-01", 0, "good", k, today=T, days_left=65)
    assert r["stage"] == 1 and r["graduates"] is False
    assert r["due_date"] == _plus(T, round((65 - j) / 7))

    # hard：stage 不变，间隔 = 同 stage 下 good 间隔的一半（kr = K - stage = 3）
    r = e.rate(con, "A-1-01", 0, "hard", k, today=T, days_left=65)
    assert r["stage"] == 1
    assert r["due_date"] == _plus(T, max(1, round(round((65 - j) / 7) / 2)))

    # 推进到毕业
    e.rate(con, "A-1-01", 0, "good", k, today=T, days_left=65)   # stage 2
    r = e.rate(con, "A-1-01", 0, "good", k, today=T, days_left=65)  # stage 3
    assert r["graduates"] is False
    r = e.rate(con, "A-1-01", 0, "good", k, today=T, days_left=65)  # stage 4 = K
    assert r["graduates"] is True and r["stage"] == 4
    row = con.execute("SELECT stage FROM unit_reviews WHERE point_id='A-1-01' AND idx=0").fetchone()
    assert row["stage"] == 4                                        # 行保留

    # 忘了可复活
    r = e.rate(con, "A-1-01", 0, "again", k, today=T, days_left=65)
    assert (r["stage"], r["due_date"]) == (0, "2026-10-16")


def _plus(today: str, days: int) -> str:
    import datetime
    return (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()


def test_legacy_stage3_revives_for_tier1(tmp_path, monkeypatch):
    """Review Focus #2：V3 遗留 stage=3 行在 K=4 下复活出卡。"""
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    con.execute(INS_U, ("A-1-01", 0, 3, "2026-11-01", T))
    con.commit()
    assert e.next_intervals(3, 4, 65, e.unit_key("A-1-01", 0))["graduates"] is False  # tier1 复活
    assert e.next_intervals(3, 2, 65, e.unit_key("A-1-01", 0))["graduates"] is True   # tier2/3 仍毕业


def test_tier_maps_unit_vs_card(tmp_path):
    """Review Focus #5：单元 tier 在考点级、卡片 tier 挂章级。"""
    from app import content as c

    data = {"subjects": [{"id": "A", "chapters": [
        {"id": "A-1", "tier": 1, "points": [{"id": "A-1-01", "units": ["u"]}],
         "cards": [{"id": "card1", "point_id": "A-1-01"}]},
        {"id": "A-2", "tier": 3, "points": [{"id": "A-2-01", "units": ["v"]}], "cards": []},
    ]}]}
    assert c.point_tier_map(data) == {"A-1-01": 1, "A-2-01": 3}
    assert c.card_tier_map(data) == {"card1": 1}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/huajun/Sync/kaoyan-system && .venv/bin/pytest tests/test_unit_review_engine.py -k "rate_transitions or legacy_stage3 or tier_maps" -v`
Expected: FAIL — `TypeError: rate() takes ... positional arguments but 6 were given`；`AttributeError: module 'app.content' has no attribute 'point_tier_map'`

- [ ] **Step 3: 实现**

在 `app/content.py` 末尾追加：

```python
def point_tier_map(content: dict) -> dict:
    out = {}
    for _, chap in iter_chapters(content):
        tier = chap.get("tier", 3)
        for p in chap.get("points", []):
            out[p["id"]] = tier
    return out


def card_tier_map(content: dict) -> dict:
    out = {}
    for _, chap in iter_chapters(content):
        tier = chap.get("tier", 3)
        for c in chap.get("cards", []):
            out[c["id"]] = tier
    return out
```

替换 `app/services/unit_review_engine.py` 的 `_schedule` / `rate` / `rate_card`（第 59–101 行）：

```python
def _advance(stage: int, rating: str, k: int, t: str, dl: int, key: str) -> tuple[int, str | None]:
    """返回 (新 stage, 新 due_date)；due_date 为 None 表示毕业。"""
    if rating == "again":
        return 0, _plus(t, 1)
    ns = stage + 1 if rating == "good" else stage
    g = _gap(ns, k, dl, key)
    if g is None:
        return ns, None
    if rating == "hard":
        g = max(1, round(g / 2))
    return ns, _plus(t, g)


def _schedule(con, table: str, key_cols: list[str], key_vals: list,
              stage: int, rating: str, k: int, t: str, dl: int, key: str) -> dict:
    ns, due = _advance(stage, rating, k, t, dl, key)
    graduates = due is None
    if graduates:
        ns = max(ns, k)
        due = t                                  # 毕业行保留，due 置为当天
    cols = ", ".join(key_cols + ["stage", "due_date", "updated_at"])
    ph = ", ".join("?" * (len(key_cols) + 3))
    con.execute(
        f"INSERT INTO {table}({cols}) VALUES({ph}) "
        f"ON CONFLICT({', '.join(key_cols)}) DO UPDATE SET stage=excluded.stage, "
        f"due_date=excluded.due_date, updated_at=excluded.updated_at",
        (*key_vals, ns, due, t))
    con.commit()
    return {"stage": ns, "due_date": due, "graduates": graduates}


def rate(con, point_id: str, idx: int, rating: str, k: int, today: str | None = None,
         days_left: int | None = None) -> dict:
    t = _today(today)
    dl = _days_left(t, days_left)
    row = con.execute("SELECT stage FROM unit_reviews WHERE point_id = ? AND idx = ?",
                      (point_id, idx)).fetchone()
    return _schedule(con, "unit_reviews", ["point_id", "idx"], [point_id, idx],
                     row["stage"] if row else 0, rating, k, t, dl, unit_key(point_id, idx))


def rate_card(con, card_id: str, rating: str, k: int, today: str | None = None,
              days_left: int | None = None) -> dict:
    t = _today(today)
    dl = _days_left(t, days_left)
    row = con.execute("SELECT stage FROM card_reviews WHERE card_id = ?", (card_id,)).fetchone()
    return _schedule(con, "card_reviews", ["card_id"], [card_id],
                     row["stage"] if row else 0, rating, k, t, dl, card_id)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/huajun/Sync/kaoyan-system && .venv/bin/pytest tests/test_unit_review_engine.py -k "rate_transitions or legacy_stage3 or tier_maps" -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
cd /Users/huajun/Sync/kaoyan-system
git add app/content.py app/services/unit_review_engine.py tests/test_unit_review_engine.py
git commit -m "feat(schedule): tier-aware rating with K and exam-anchored gaps"
```

---

## Task 3（T3 / M3）队列 tier 排序与动态 next

**文件清单**
- Modify: `app/services/unit_review_engine.py:106-293`（`_mk_unit_item` / `_mk_card_item` / `_memo_sort_key` / `_assemble` / `memo_queue` / `queue`）
- Test: `tests/test_memo_queue.py`（补 tier 排序 + 同日堆积分布）

**接口**
- Consumes: T1 的 `target_k` / `jitter` / `next_intervals`；T2 的 `rate` 签名
- Produces: `memo_queue(...)` 每个 item 增加 `tier: int`、`k: int`；响应**删除** `frozen_graduation` 字段

**步骤**

- [ ] **Step 1: 写失败测试**

先给 `tests/test_memo_queue.py` 的 `CONTENT` fixture 的三个章节补 `tier`（`A-1` → `1`、`A-2` → `3`、`B-1` → `2`），再追加：

```python
def test_queue_sorts_by_tier_first(tmp_path, monkeypatch):
    """高梯队优先于低梯队，即使低梯队更早到期。"""
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    con.execute(INS_U, ("A-1-01", 0, 1, T, T))     # tier1，当天到期
    con.execute(INS_U, ("A-2-01", 0, 0, Y, Y))     # tier3，更早到期
    con.commit()
    q = e.memo_queue(con, CONTENT, review_n=60, today=T, days_left=65)
    ids = [x["point_id"] for x in q["items"]]
    assert ids.index("A-1-01") < ids.index("A-2-01")


def test_queue_items_expose_tier_and_k(tmp_path, monkeypatch):
    con = _db(tmp_path, monkeypatch)
    from app.services import unit_review_engine as e

    con.execute(INS_U, ("A-1-01", 0, 0, T, T))
    con.commit()
    it = e.memo_queue(con, CONTENT, review_n=60, today=T, days_left=65)["items"][0]
    assert it["tier"] == 1 and it["k"] == 4


def test_jitter_spreads_same_day_items():
    """Review Focus #3：同日条目不应全部撞在同一天到期。"""
    from app.services import unit_review_engine as e

    dues = {e.next_intervals(0, 4, 65, e.unit_key(f"A-1-0{i}", 0))["good"] for i in range(1, 9)}
    assert len(dues) > 1                      # 不是单点，jitter 生效
```

> **注意**：补 `tier` 后 K 由缺省 2 变为 4/2/2，会改变出卡集合（原先 `stage=2` 视为毕业，现在 tier=1 的 `stage=2` 仍出卡）。本文件**既有断言的期望值需逐一复核**，尤其是 `test_due_merges_units_and_cards_interleaved`（第 52 行）与 `test_due_caps_but_scope_does_not`（第 65 行）的计数。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/huajun/Sync/kaoyan-system && .venv/bin/pytest tests/test_memo_queue.py -k "tier_first or tier_and_k or jitter_spreads" -v`
Expected: FAIL — `KeyError: 'tier'`

- [ ] **Step 3: 实现**

`_mk_unit_item` / `_mk_card_item` 增加 `tier` 与 `k` 入参并写入 item；`_memo_sort_key` 改为：

```python
def _memo_sort_key(x: dict):
    tail = x["idx"] if x["kind"] == "unit" else x["card_id"]
    return (x["tier"], x["stage"], x["due_date"], x["point_id"] or "",
            0 if x["kind"] == "unit" else 1, tail)
```

`memo_queue` 内构建 `ptier = content.point_tier_map(content)`、`ctier = content.card_tier_map(content)`，传入两个 `_mk_*`；毕业判定由 `stage >= GRADUATE_STAGE` 改为 `stage >= k`。`_assemble` 返回体删除 `"frozen_graduation"`，保留 `days_left`。`queue(...)` 同步（考点模式用 `target_k("unit", ptier.get(point_id))`）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/huajun/Sync/kaoyan-system && .venv/bin/pytest tests/test_memo_queue.py tests/test_unit_review_engine.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/huajun/Sync/kaoyan-system
git add app/services/unit_review_engine.py tests/test_memo_queue.py
git commit -m "feat(schedule): tier-first queue ordering and dynamic next intervals"
```

---

## Task 4（T4 / M4）路由与设置

**文件清单**
- Modify: `app/routers/review_router.py:65-104`
- Modify: `app/settings_store.py:6-20`
- Modify: `web/js/me.js`（review_n 输入 min/max）
- Test: `tests/test_unit_review_engine.py`（API 测试）、`tests/test_card_review.py`

**接口**
- Consumes: T2 的 `rate` / `rate_card` 新签名；T1 的 `next_intervals` / `target_k`
- Produces: `POST /api/unit_review` / `POST /api/card_review` 响应 `next` 变为动态；`settings_store.review_n()` clamp 100–300

**步骤**

- [ ] **Step 1: 写失败测试**

```python
def test_review_n_default_and_clamp(client):
    from app import db, settings_store
    con = db.connect()
    assert settings_store.review_n(con) == 260                 # 新默认
    settings_store.save(con, {"review_n": 50})
    assert settings_store.review_n(con) == 100                 # 下限
    settings_store.save(con, {"review_n": 999})
    assert settings_store.review_n(con) == 300                 # 上限
    con.close()


def test_unit_review_api_returns_dynamic_next(ac, tmp_path):
    _write_content(tmp_path)
    from app import content as c
    c.reset_cache()
    r = ac.post("/api/unit_review", json={"point_id": "A-1-01", "idx": 0, "rating": "good"})
    assert r.status_code == 200
    n = r.json()["next"]
    assert set(n) == {"again", "hard", "good", "graduates"}
    assert n["again"] == 1 and n["graduates"] is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/huajun/Sync/kaoyan-system && .venv/bin/pytest tests/ -k "review_n_default or dynamic_next" -v`
Expected: FAIL — `assert 60 == 260`

- [ ] **Step 3: 实现**

`app/settings_store.py`：`DEFAULTS` 的 `"review_n": 60` → `260`；`review_n()` 的 `max(10, min(200, ...))` → `max(100, min(300, ...))`，docstring 同步改为 `clamp 100–300`。

`app/routers/review_router.py`：`unit_review` 内由 `content.find_point` 已取得的章节取 tier，计算 `k = unit_review_engine.target_k("unit", chap.get("tier"))`，传入 `rate(con, point_id, i, rating, k)`；`card_review` 同理用 `content.card_tier_map` 取 tier 传 `rate_card(con, card_id, rating, k)`。两处 `next` 改为：

```python
key = unit_review_engine.unit_key(body.point_id, i)      # 卡则为 card_id
"next": unit_review_engine.next_intervals(last["stage"], k, plan_engine.days_left(), key)
```

`web/js/me.js`：`#set-review` 的 `min="10" max="200"` → `min="100" max="300"`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/huajun/Sync/kaoyan-system && .venv/bin/pytest tests/ -v`
Expected: PASS（全量；`test_rate_frozen_never_graduates` 与旧 `test_next_intervals_matrix` 已在 T1/T2 移除）

- [ ] **Step 5: 提交**

```bash
cd /Users/huajun/Sync/kaoyan-system
git add app/routers/review_router.py app/settings_store.py web/js/me.js tests/
git commit -m "feat(schedule): wire tier into review APIs, raise review_n to 260"
```

---

## Task 5（T5 / M6）前端适配

**文件清单**
- Modify: `web/js/memo.js:174-176`（间隔标注）、`:210-214`（单元卡头部）
- Modify: `web/css` 或 `web/app.css`（tier 徽标样式，若需）

**接口**
- Consumes: T3 的 item `tier` / `k` / `next`

**步骤**

- [ ] **Step 1: 改间隔标注与 tier 徽标**

`intervalLabel` 已处理 `null → '毕业'`，无需改。在 `paint()` 的位置行（`pos` 变量）追加 tier 徽标：

```javascript
const TIER_LABEL = { 1: '第1梯队', 2: '第2梯队', 3: '第3梯队' };
// 在 pos 拼接处追加：
const tierChip = it.tier ? `<span class="chip ${it.tier === 1 ? 'r' : 'b'}">${TIER_LABEL[it.tier] || ''}</span>` : '';
```

并在单元卡与背题卡两处 `pos` 中插入 `tierChip`。

- [ ] **Step 2: 浏览器自验（金路径）**

启动预览：`cd /Users/huajun/Sync/kaoyan-system && .venv/bin/python -m uvicorn app.main:app --port 8011`
（或 `kaoyan-preview` 配置）。在 `http://localhost:8011` 依次验证：

1. 今日页 →「记」→ 今日到期队列可出卡
2. 卡片位置行显示梯队徽标
3. 三个评分按钮的间隔数值**随 days_left 变化**（对比 `curl /api/memo/queue` 的 `next`）
4. 连续「秒答」到 K 次后显示「毕业」，且该条目不再出卡
5. 控制台无 JS 报错

- [ ] **Step 3: 提交**

```bash
cd /Users/huajun/Sync/kaoyan-system
git add web/js/memo.js web/app.css
git commit -m "feat(memo): show tier badge on flip cards"
```

---

## Task 6（T6 / M7）模拟验证脚本与回归

**文件清单**
- Create: `scripts/simulate_schedule.py`
- Test: `tests/test_simulate_schedule.py`

**接口**
- Produces: CLI `python scripts/simulate_schedule.py [--cap 260] [--learn-days 45] [--json]`

**步骤**

- [ ] **Step 1: 写失败测试**

```python
def test_simulation_runs_and_reports(tmp_path):
    from scripts.simulate_schedule import simulate

    out = simulate(cap=260, learn_days=45)
    assert out["daily_avg"] <= 180                 # Spec §7.2：均值不得超原批准预算
    assert out["peak"] <= 260
    assert out["tier1_tail_coverage"] >= 0.95
    assert out["tier_tail_coverage"][2] >= 0.90
    assert out["tier_tail_coverage"][3] >= 0.40    # 第 3 梯队有意饥饿，仅设下限
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/huajun/Sync/kaoyan-system && .venv/bin/pytest tests/test_simulate_schedule.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.simulate_schedule'`

- [ ] **Step 3: 实现**

新建 `scripts/simulate_schedule.py`。**必须复用 `unit_review_engine.next_intervals` 与 `target_k`，不得重写公式**，否则脚本与实现会漂移：

```python
"""负载模拟：验证 V5 调度在给定容量下的日负载与考前覆盖率（Spec §7.2）。

公式一律复用 unit_review_engine，不重写。
"""
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.services import unit_review_engine as e   # noqa: E402

EXAM = 64          # 距考试天数（day 0 = 今天；2026-10-15 → 2026-12-19）
TAIL = 21          # 考前窗口
DEFAULT_CONTENT = pathlib.Path(__file__).resolve().parent.parent / "content" / "content.json"


def load_items(content_path):
    """返回 [(tier, kind, key)]；单元在考点级、卡片挂在章级。"""
    data = json.loads(pathlib.Path(content_path).read_text(encoding="utf-8"))
    items = []
    for subj in data["subjects"]:
        for chap in subj.get("chapters", []):
            tier = chap.get("tier", 3)
            for p in chap.get("points", []):
                for i in range(len(p.get("units") or [])):
                    items.append((tier, "unit", e.unit_key(p["id"], i)))
            for c in chap.get("cards", []):
                items.append((tier, "card", c["id"]))
    return items


def simulate(content_path=DEFAULT_CONTENT, cap=260, learn_days=45):
    items = load_items(content_path)
    by_tier = collections.defaultdict(list)
    for tier, kind, key in items:
        by_tier[tier].append((kind, key))

    # 学习顺序：高梯队先学（模拟 plan_engine 的权重×未完成度排序）
    todo = []
    for tier in (1, 2, 3):
        group = by_tier[tier]
        n = len(group)
        for pos, (kind, key) in enumerate(group):
            todo.append({"tier": tier, "kind": kind, "key": key,
                         "learn": int(pos * learn_days / n), "stage": 0, "due": None})

    per_day = collections.Counter()
    tail_hit = collections.Counter()
    completed = collections.Counter()
    deferred = 0

    for day in range(EXAM + 1):
        dl = EXAM - day
        for it in todo:
            if it["learn"] == day and it["stage"] == 0:
                # 首次学习评分：stage 0 → 1，并按公式排下一次复习
                g = e.next_intervals(0, e.target_k(it["kind"], it["tier"]), dl, it["key"])["good"]
                it["stage"] = 1
                it["due"] = day + g if g is not None else None

        due = [it for it in todo if it["due"] is not None and it["due"] <= day]
        due.sort(key=lambda x: (x["tier"], x["due"]))       # 容量不足时的分配策略
        take = due[:cap]
        deferred += max(0, len(due) - cap)

        for it in take:
            k = e.target_k(it["kind"], it["tier"])
            g = e.next_intervals(it["stage"], k, dl, it["key"])["good"]
            it["stage"] += 1
            per_day[day] += 1
            if day >= EXAM - TAIL:
                tail_hit[it["tier"]] += 1
            if g is None:
                it["due"] = None                            # 毕业
                completed[it["tier"]] += 1
            else:
                it["due"] = day + g

    totals = {t: len(by_tier[t]) for t in (1, 2, 3)}
    values = [per_day.get(d, 0) for d in range(EXAM + 1)]
    return {
        "daily_avg": sum(values) // len(values),
        "peak": max(values),
        "deferred": deferred,
        "tier1_tail_coverage": tail_hit[1] / totals[1],
        "tier1_ladder_completion": completed[1] / totals[1],
        "tier_tail_coverage": {t: tail_hit[t] / totals[t] for t in (1, 2, 3)},
        "tier_ladder_completion": {t: completed[t] / totals[t] for t in (1, 2, 3)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", default=str(DEFAULT_CONTENT))
    ap.add_argument("--cap", type=int, default=260)
    ap.add_argument("--learn-days", type=int, default=45)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    out = simulate(a.content, a.cap, a.learn_days)
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    print(f"日均 {out['daily_avg']}  峰值 {out['peak']}  顺延 {out['deferred']}")
    for t in (1, 2, 3):
        print(f"  第{t}梯队  考前 {TAIL} 天覆盖 {out['tier_tail_coverage'][t] * 100:.0f}%"
              f"  走完阶梯 {out['tier_ladder_completion'][t] * 100:.0f}%")


if __name__ == "__main__":
    main()
```

`--json` 输出原始数据，默认输出表格。

- [ ] **Step 4: 运行测试与脚本**

Run: `cd /Users/huajun/Sync/kaoyan-system && .venv/bin/pytest tests/test_simulate_schedule.py -v && .venv/bin/python scripts/simulate_schedule.py`

Expected: 测试 PASS；脚本输出第 1/2 梯队覆盖率均 ≥ 95%/90%、第 3 梯队 ≥ 40%、日均 ≤ 180。**若第 1/2 梯队低于阈值**，按 Spec §7.2 下调 `K_BY_TIER` 中低梯队取值，而非再提高 cap（cap 只影响突发日、不影响均值），并同步更新 Spec §4.3 表格。

- [ ] **Step 5: 全量回归 + 提交**

Run: `cd /Users/huajun/Sync/kaoyan-system && make test`
Expected: 全绿

```bash
cd /Users/huajun/Sync/kaoyan-system
git add scripts/simulate_schedule.py tests/test_simulate_schedule.py docs/superpowers/specs/2026-10-15-kaoyan-v5-schedule.md
git commit -m "feat(schedule): add load simulation script with spec acceptance thresholds"
```

---

## 验收清单

- [ ] `make test` 全绿
- [ ] `scripts/simulate_schedule.py` 输出满足 Spec §7.2 五条阈值
- [ ] 浏览器金路径 5 项通过（T5 Step 2）
- [ ] 响应体与前端均已无 `frozen_graduation`
- [ ] 真实库 `data/kaoyan.db` 无需迁移即可启动（表结构未变）
- [ ] Spec §4.3 的 K 表与 `K_BY_TIER` 一致
