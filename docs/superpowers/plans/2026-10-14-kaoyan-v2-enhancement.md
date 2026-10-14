# kaoyan-system V2 增强 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按真实考试题型扩充题库（多选/填空/主观卡，总数 470→≥700）、听感修复（315/101 章级听单+导览语）、间隔重复复习、模拟考试闭环、离线音频、媒体每章 ≥1、101 时政机制、安全检索加固。

**Architecture:** 后端新增 3 个服务（review_engine/quiz_grader/exam_engine）+ 2 张表（reviews/exam_runs）+ 1 个路由（stats_router）；content.json 扩展三种题型与 chapter.listen；前端扩展测页（多题型/模拟考试/会话持久化）、听页（章级听单/预加载/离线下载）、今日页（复习）、看页（搜索/待复习徽标）；内容管线新增章级听单生成器与两批题库扩充。

**Tech Stack:** 既有栈不变（FastAPI/SQLite/原生 JS PWA/百炼 qwen-audio-3.1-tts-next/RDKit/matplotlib/王忠教材裁图）。

**Spec:** `docs/superpowers/specs/2026-10-14-kaoyan-v2-enhancement.md`

## Global Constraints

- 旧字段与旧接口全部保留（向后兼容）；`quiz_attempts.chosen` 保留，新增 `response TEXT` 列（`init_db` 内 `PRAGMA table_info` 幂等 ALTER）
- 日期一律用服务器本地日期 ISO 字符串（`datetime.date.today().isoformat()`），due 比较为字符串 `<=`（东八区一致）
- 多选判分：与答案集合**完全一致**才得分（真题规则）；填空：归一化后匹配 `accept` 列表任一即对，不匹配必须提供「自评」兜底入口
- 真题原文不编造；时政事件不编造（机制+模板，用户供稿）
- TTS 生成沿用 `--engine qwen_audio` 与断点续跑；章级听单每段 ≤60s
- 视频/多用户/推送通知：不做
- 里程碑提交：M1 后端（T1-T6）、M2 前端（T7-T10）、M3 内容（T11-T17）各一次；完成后询用户再 push

## Review Focus

- **填空归一化误判**：全角括号、上标（²/²）、乘号（×/x/*）、单位空格——归一化须覆盖这些变体，且自评入口在 UI 上永远可达（T2 测试含变体样例 + T7 手测）。
- **多选部分对不给分**：判分与前端提交的数据形状必须严格一致（T2 测试：少选/多选均判错；T7 手测勾选-提交-判分闭环）。
- **复习日期时区**：所有 due 计算使用同一来源的本地日期；测试注入固定日期，验证 1/3/7/15 链路（T1）。
- **章级听单完成标记**：整段播完才标记全部 point_ids；中途退出/切段不标（T8 手测：播到一半刷新，进度未标）。
- **离线缓存版本错配**：音频重新生成后旧缓存会播放过期内容——Cache 名嵌入 content version，版本不符提示重新下载（T8 检查）。

---

### Task 1: 复习调度引擎（reviews）

**Files:**
- Create: `app/services/review_engine.py`, `tests/test_review_engine.py`
- Modify: `app/schema.sql`（reviews 表）、`app/routers/progress_router.py`（状态变更挂钩）、`app/routers/quiz_router.py`（答错挂钩）、`tests/test_progress_api.py`（挂钩断言）

**Interfaces:**
- Produces: `review_engine.on_state_change(con, point_id, new_state, today) -> None`；`due_points(con, today) -> list[str]`（due_date<=today）；`schedule(con, point_id, today) -> None`（stage=0, due=today+1）；`advance(con, point_id, today) -> None`（stage+1：1→+7、2→+15、≥3 删除）。
- 规则矩阵：`half|review` → schedule（重置 stage 0）；`known` 且无记录 → 建（stage1, due+3）；`known` 且有记录 → advance；`new` → 删除记录。

- [ ] **Step 1: 写失败测试（规则矩阵 + 挂钩）**

```python
def test_review_rule_matrix(tmp_path, monkeypatch):
    # ky db 初始化后直连
    from app.services import review_engine as re
    con = make_db(tmp_path)  # helper: db.init_db + connect
    t = "2026-10-14"
    re.schedule(con, "p1", t); row = get(con, "p1")
    assert row["stage"] == 0 and row["due_date"] == "2026-10-15"
    re.advance(con, "p1", "2026-10-15"); row = get(con, "p1")
    assert row["stage"] == 1 and row["due_date"] == "2026-10-22"      # +7
    re.advance(con, "p1", "2026-10-22")
    assert get(con, "p1")["due_date"] == "2026-11-06"                 # +15
    re.advance(con, "p1", "2026-11-06")
    assert get(con, "p1") is None                                     # 毕业
    re.on_state_change(con, "p2", "half", t)
    assert get(con, "p2")["due_date"] == "2026-10-15"
    re.on_state_change(con, "p2", "known", t)                          # 有记录→advance
    assert get(con, "p2")["stage"] == 1
    re.on_state_change(con, "p3", "known", t)                          # 无记录→stage1 due+3
    assert get(con, "p3")["due_date"] == "2026-10-17"
    assert re.due_points(con, "2026-10-14") == []
    assert set(re.due_points(con, "2026-10-15")) == {"p2"} or "p2" in re.due_points(con, "2026-10-15")
```

- [ ] **Step 2: 失败运行** — `pytest tests/test_review_engine.py -v` → FAIL
- [ ] **Step 3: 实现** `review_engine.py` + schema.sql 加 `reviews` 表 + progress_router 在 upsert 后调 `on_state_change`（`state=="new"` 时调删除分支）+ quiz_router 答错且 `point_id` 存在时 `schedule`
- [ ] **Step 4: 通过运行** — `pytest tests/test_review_engine.py tests/test_progress_api.py -v` → PASS
- [ ] **Step 5: 暂存**

---

### Task 2: 题型引擎（多选/填空判分）

**Files:**
- Create: `app/services/quiz_grader.py`, `tests/test_quiz_grader.py`
- Modify: `app/schema.sql`（quiz_attempts 加 `response TEXT`）、`app/db.py`（幂等 ALTER）、`app/routers/quiz_router.py`（attempt 接受多形状 response）、`scripts/validate_content.py`（新题型校验）、`tests/test_quiz_api.py`

**Interfaces:**
- Produces: `quiz_grader.grade(quiz, response) -> {"correct": bool, "answer": any}`；`normalize_blank(s) -> str`（全→半角、去所有空白、lower、统一 ×x·→*、⁰⁻⁹/₀₋₉→0-9、⁻→-）。
- POST `/api/quiz/attempt` 请求体：`{"quiz_id", "response"}`——single: int；multi: list[int]；blank: list[str]；兼容旧 `{"chosen": int}`。

- [ ] **Step 1: 写失败测试**

```python
def test_grade_multi_all_or_nothing():
    q = {"type": "multi", "options": ["a","b","c","d"], "answer": [0,2]}
    assert grade(q, [0,2])["correct"] and not grade(q, [0])["correct"] and not grade(q, [2,0,1])["correct"]
def test_grade_blank_variants():
    q = {"type": "blank", "blanks": [{"accept": ["1.8×10-5", "1.8x10^-5"]}]}
    assert grade(q, ["1.8×10⁻⁵"])["correct"]        # 归一化：⁻⁵→-5
    assert grade(q, [" 1.8X10-5 "])["correct"]
    assert not grade(q, ["2.0×10-5"])["correct"]
def test_legacy_single_still_works(): ...  # {"chosen": idx} 旧形状
```

- [ ] **Step 2: FAIL** → **Step 3: 实现**（grader + ALTER + attempt 改造 + validate_content 扩展：multi answer 为不重复数组且在下标域内；blank accept 非空）→ **Step 4: PASS**
- [ ] **Step 5: 暂存**

---

### Task 3: 考试引擎（模拟考试）

**Files:**
- Create: `app/services/exam_engine.py`, `app/routers/exam_router.py`, `tests/test_exam_engine.py`, `tests/test_exam_api.py`
- Modify: `app/schema.sql`（exam_runs）、`app/main.py`（挂路由）

**Interfaces:**
- Produces: `exam_engine.assemble(content, subject, kind) -> paper`；`exam_engine.score(content, paper, responses, verdicts) -> result`。
  - `kind="objective"`：315 → 30 single + 20 blank；101 → 16 single + 17 multi（不足时按实际数量，`total` 如实）；`kind="subjective"`：812 → 名解 ×6/简答 ×6/论述 ×2（按 `cards.kind` 抽，不足时放宽）。
  - `paper`：`{"exam_id", "subject", "kind", "time_limit_min": 90|60, "sections": [{"name","type","score_per","items":[{"id","stem","options"?,...}]}]}`
  - `result`：`{"score", "total", "per_section", "per_chapter": {chap_id: {"n","correct"}}}`；主观卡 verdict：know=1.0 / fuzzy=0.5 / no=0 × 分值。
- 表 `exam_runs(id TEXT PK, subject, kind, started_at, finished_at, detail_json, score, total)`；`detail_json` 存卷面+已答（增量写，刷新恢复）。
- Routes：`POST /api/exam/new {subject,kind}`（建卷入库）；`POST /api/exam/submit {exam_id, responses:[{item_id,response}], verdicts:[{card_id,verdict}]}`；`GET /api/exam/{id}`（恢复）。

- [ ] **Step 1: 写失败测试**

```python
def test_assemble_315_counts(fixture_content):
    paper = assemble(fixture_content, "315", "objective")
    types = [s["type"] for s in paper["sections"]]
    assert types == ["single", "blank"] and paper["time_limit_min"] == 90
def test_score_partial_multi_zero(fixture_content):
    paper, resp = build_315_paper_with(bad_multi=[0])   # 少选
    r = score(fixture_content, paper, resp, [])
    assert per_chapter 里 multi 所在章 correct 数不含该题
def test_submit_roundtrip(tmp_path, monkeypatch):
    # API：建卷→提交→GET 恢复→finished 状态
```

- [ ] **Step 2: FAIL** → **Step 3: 实现** → **Step 4: PASS** → **Step 5: 暂存**

---

### Task 4: 章节正确率统计与导出

**Files:**
- Create: `app/routers/stats_router.py`, `tests/test_stats_export.py`
- Modify: `app/content.py`（`quiz_chapter_map(content) -> {quiz_id: chap_id}`）、`app/main.py`

**Interfaces:**
- `GET /api/stats/chapters?subject=315` → `[{chap_id, name, n, correct, rate}]`（quiz_attempts 聚合）
- `GET /api/export/wrong` → `text/markdown`（错题：题干/选项/答案/解析/所属章/错过次数）
- `GET /api/export/progress` → `text/markdown`（四科加权/原始进度 + 各章 completion 表）

- [ ] **Step 1: 写失败测试**（做 2 题 1 对 → chapters stats rate=0.5；export 返回含题干原文）→ **Step 2: FAIL** → **Step 3: 实现** → **Step 4: PASS** → **Step 5: 暂存**

---

### Task 5: 安全加固（Cookie Secure + 登录限速）

**Files:**
- Modify: `app/routers/auth_router.py`, `app/auth.py`（内存限速器）, `tests/test_auth_security.py`

**Interfaces:**
- `auth.login_allowed(ip) -> bool` / `auth.record_login_fail(ip)`（滑窗 15 分钟 5 次，超限返回 429 `{"error":"too_many_attempts","retry_after":秒}`）
- Cookie：请求 scheme 为 https 或 `X-Forwarded-Proto: https` 时加 `secure=True`（本机 http 不加，保 dev 可用）。

- [ ] **Step 1: 写失败测试**（5 次错密码后第 6 次 429；`X-Forwarded-Proto: https` 时 Set-Cookie 含 `Secure`；纯 http 不含）→ **Step 2: FAIL** → **Step 3: 实现** → **Step 4: PASS** → **Step 5: 暂存；M1 至此全绿后提交**

```bash
git add -A && git commit -m "feat(m1): review scheduling, quiz types (multi/blank), exam engine, stats/export, security"
```

---

### Task 6: plan_engine 章级听单单元 + 复习置顶

**Files:**
- Modify: `app/services/plan_engine.py`, `tests/test_plan_engine.py`
- Modify: `app/routers/plan_router.py`（/plan/today 返回 `reviews_due`、`review_points`）

**Interfaces:**
- listen 单元规则：章有 `listen[]` → 以其片段为单元（章全部点 `known/listened` 时跳过）；否则点级 audio；单位排序不变（权重×未完成度）；`est_minutes` 用 dur 求和。
- look：`due_points` 最先（按权重降序），再现有逻辑，去重取 look_n。
- `/api/plan/today` 增加 `"reviews_due": N, "review_points": [...]`。

- [ ] **Step 1: 测试**（fixture 增加一个带 `listen[]` 的章节：listen 队列首个为该章片段 id；due point 出现在 look[0]；reviews_due 计数）→ **Step 2: FAIL** → **Step 3: 实现** → **Step 4: PASS** → **Step 5: 暂存**

---

### Task 7: 前端-测页三题型 + 会话持久化 + 跳过/标记

**Files:**
- Modify: `web/js/quiz.js`（重构答题流程）、`web/index.html`（multi/blank 容器）、`web/app.css`（复选框/输入框样式）

**Interfaces:**
- 按 `q.type` 渲染：single 现逻辑；multi 复选 + 「提交答案」；blank 每空一个 input + 提交。
- 提交体：`{quiz_id, response}`（int | list[int] | list[str]）；判错且填空时，解析区显示输入 vs 答案 + 「我答对了」自评按钮（本地计对，不写服务端）。
- 会话持久化：`localStorage['ky_quiz_run']` 存 `{at, mode, chapter, itemIds, i, right, flagged: []}`；进入测页若有未完成任务（同日）显示「继续上次练习 / 重新开始」；跳过 = i+1 不判；标记 = flagged 切换（列表头显示标记数）。
- **浏览器验收**：三类题型各做一题；中途刷新 → 恢复；多选少选判错；填空变体「1.8×10⁻⁵」判对；自评按钮可用。

- [ ] **Step 1: 实现** → **Step 2: 浏览器验收（上列五项）** → **Step 3: 暂存**

---

### Task 8: 前端-听页章级听单 + 预加载 + 离线下载

**Files:**
- Modify: `web/js/state.js`（索引 `chapter.listen`：`{chap, subj, clip, point_ids}`，chapter 片段标题=「章名·考点串讲」）、`web/js/player.js`（完成时批量标 listened、预取下一段、下载按钮状态）、`web/sw.js`（`/audio/*` 缓存优先）、`web/js/look.js`（章卡「离线下载」入口）

**Interfaces:**
- 完成标记：chapter 片段 `ended` → 对该 `point_ids` 逐个 POST `/api/progress {state:"listened"}`（仅当现状态为 new，沿用进度缓存）。
- 预取：`loadAndPlay` 中 `new Audio('/audio/'+queue[idx+1]+'.mp3')` 预热。
- 离线：`window.kyOffline = {download(chapId), status(chapId), clear()}`；按章把该章全部片段（听单片段 + 点级 audio）`caches.open('ky-audio')` 存入；SW 对 `/audio/` 改缓存优先；缓存名附 content version（`ky-audio-<version>`），版本变化提示重下。
- **浏览器验收**：315 章连播（整段结束全章标 listened；半途刷新未标记）；预取存在（Network 面板下一段已加载）；下载一章→DevTools 断网→仍可播；未下载章节断网有提示。

- [ ] **Step 1: 实现** → **Step 2: 浏览器验收（上列四项）** → **Step 3: 暂存**

---

### Task 9: 前端-模拟考试 UI

**Files:**
- Modify: `web/js/quiz.js`（测页新增「模拟考试」入口与屏）、`web/index.html`、`web/app.css`

**Interfaces:**
- 流程：选科目/卷型 → `POST /api/exam/new` → 作答屏（分区推进、顶部倒计时、区间内可回跳、刷新后 `GET /api/exam/{id}` 恢复）→ 交卷（客观自动 + 812 主观逐卡自评）→ 结果页（总分/分区得分/按章正确率/错题「一键入错题本」按钮逐个调 attempt）。
- 计时器仅前端展示；超时不强制交卷（提示）。

- [ ] **Step 1: 实现** → **Step 2: 浏览器验收**（315 客观卷全流程 + 刷新恢复 + 结果页正确率；101 多选卷抽做）→ **Step 3: 暂存**

---

### Task 10: 前端-复习 UI + 搜索 + 导出按钮 + 待复习徽标

**Files:**
- Modify: `web/js/today.js`（「今日复习 N 点」区块与列表）、`web/js/look.js`（搜索框 + 待复习徽标 + 高亮跳转）、`web/js/me.js`（导出按钮）

**Interfaces:**
- 今日复习：来自 `/api/plan/today` 的 `review_points`；点击 → 看页打开对应章并滚动定位该点。
- 待复习徽标：`GET /api/reviews/due` 集合 ∩ 当前可见点；状态轮转标记 known 即自动推进（服务端挂钩已存在）。
- 搜索：输入 ≥2 字符，内存过滤全科 468 点（命中标题高亮），点击直达。
- 导出：`fetch('/api/export/wrong')` → Blob 下载 `错题清单-YYYYMMDD.md`；同理 progress。
- **浏览器验收**：制造一个 due 复习点（改库日期）→ 今日显示 → 点击直达；搜索「光呼吸」命中并跳转；导出文件打开正常。

- [ ] **Step 1: 实现** → **Step 2: 浏览器验收（上列三项）** → **Step 3: 暂存；M2 全绿后提交**

```bash
git add -A && git commit -m "feat(m2): multi-type quiz UI, exam mode, chapter listen, offline audio, reviews/search/export UI"
```

---

### Task 11: 内容-315/101 章级听单（导览语 + 合并生成）

**Files:**
- Create: `content/chapter_intros.py`（315 26 章 + 101 27 组导览语，每章 1-2 句，含梯队提示）、`scripts/gen_chapter_listen.py`, `tests/test_gen_chapter_listen.py`
- Modify: `content/content.json`（写入 `chapters[].listen`）

**Interfaces:**
- `build_chapter_text(intro, points) -> str`（导览语 + 全部点文本以「。」连接）；`split_clips` ≤220 字切段；片段 id `{chap_id}-c{n}`；TTS 复用 `synth_qwen_audio`；`listen[]` 记录 `{src,dur,point_ids}`（全部章内点）。
- 生成完成后**删除 315/101 的点级 mp3**（812 不动）；断点续跑：`listen[]` 已存在且文件在 → 跳过。
- **验收**：53 章全生成；抽听 10 章连贯；每段 dur ≤60；`python scripts/validate_content.py` 扩展校验 `listen[].point_ids` ⊆ 章内点。

- [ ] **Step 1: 写 `build_chapter_text`/切段测试（FAIL→实现→PASS）** → **Step 2: 撰写 53 条导览语** → **Step 3: dry-run 列出片段清单与预估时长（超 60s 的章拆段确认）** → **Step 4: 真实生成（后台，~55 段）** → **Step 5: 抽听验收 + 暂存**

---

### Task 12: 内容-题库扩充批 1：101 多选 + 分析题卡

**Files:**
- Modify: `content/quiz/101.json`（追加 `type:"multi"` 题目与分析卡）
- 遵守 Task 2 的 schema；`scripts/validate_content.py` 校验

- [ ] **Step 1: 撰写 60 道多选**（每模块 ~10：马原/毛中特/习概/史纲/思修/时政；4 选项 2-3 个正确，选项为教材标准表述变体）→ **Step 2: 撰写 18 张分析题卡**（`cards` 使用 `kind:"分析"`，back 为「原理+材料落点+小结」三段式作答骨架）→ **Step 3: `--merge` + validate 0 问题** → **Step 4: 输出抽查清单（题干/答案/解析三列 markdown）→ 暂存**

---

### Task 13: 内容-题库扩充批 2：315 选择 +60、填空 40

**Files:**
- Modify: `content/quiz/315.json`

- [ ] **Step 1: 选择题补齐至每章 ≥12**（新增 60：四大平衡/热力学/结构/有机反应网络为主，计算类给解题步骤解析）→ **Step 2: 填空 40 道**（弱酸 pH、Ksp 换算、电势计算、命名、方程式补全等；`accept` 列 2-3 个可接受变体）→ **Step 3: merge + validate（含新题型校验）** → **Step 4: 抽查清单 → 暂存**

---

### Task 14: 内容-题库扩充批 3：315 综合卡 20 + 812 卡片补齐

**Files:**
- Modify: `content/quiz/315.json`（`kind:"综合"` 卡：计算题完整步骤）、`content/quiz/812.json`（`kind` 标注 + 补齐）

- [ ] **Step 1: 315 综合卡 20**（滴定计算/热力学 ΔG 判断/平衡移动/有机合成路线，back 含完整解题步骤链）→ **Step 2: 812 卡片重标 kind（名解/简答/论述）并补齐每章 ≥5（净增 ~23）** → **Step 3: merge + validate + 计数 ≥700 断言** → **Step 4: 抽查 → 暂存**

---

### Task 15: 内容-媒体扩 315（结构式 8→28 + 图表 +6）

**Files:**
- Modify: `content/media_config.py`,（运行）`scripts/gen_media.py`

- [ ] **Step 1: 补 20 个结构式 SMILES**（苯酚/苯甲酸/乙酸乙酯/乙胺/乙酰胺/丙烯/丙炔/环己烷(椅式叠简)/乳酸/柠檬酸/果糖链式/麦芽糖/甘氨酸/半胱氨酸/葡萄糖醛酸/吲哚/吡啶/嘧啶/喹啉/乙酸酐，按对应章 point_id 挂载）→ **Step 2: 图表 +6**（0.1/0.01/0.001M NaOH 滴定 HAc 曲线族、缓冲容量-pH 曲线、同周期原子半径与第一电离能双轴图、4s/3d 能级交错示意图）→ **Step 3: 生成 + attach + 逐张目检（Read 渲染图）** → **Step 4: validate + 暂存**

---

### Task 16: 内容-媒体扩 812 教材裁图 +8~12、101 时间轴

**Files:**
- Modify: `content/figures_textbook.json`（新增条目）、`content/media/`（101 时间轴 SVG）、`content/media_config.py`（STATIC 挂载时间轴）

- [ ] **Step 1: 王忠版逐章扫描定位**（呼吸/生长物质/成花/抗逆/细胞/矿质章，缩略图拼版→放大目检→裁图→Read 复核，沿用既有流程）→ **Step 2: 目标 8-12 张**（优先：TCA 循环图、五大激素表、光周期示意、抗逆膜伤害图、细胞结构图、根系矿质吸收图）→ **Step 3: 手绘史纲时间轴 SVG（1840→2026 关键节点）挂入 101-22** → **Step 4: attach + validate（每章 ≥1 检查脚本通过：统计各章 media 非空）** → **Step 5: 暂存**

---

### Task 17: 内容-101 时政月度机制

**Files:**
- Create: `content/current_affairs/TEMPLATE.md`, `content/current_affairs/README.md`, `scripts/apply_current_affairs.py`, `tests/test_apply_current_affairs.py`
- Modify: `DEPLOY.md`（月度流程一节）

**Interfaces:**
- 输入：`content/current_affairs/YYYY-MM.md`（格式：`## 事件标题` + `- 要点` 行 + `[考纲挂钩: xxx]` 可选）→ 生成 points（id `101-27-ca{n}`，tags `["时政","高频"]`）追加到 101-27 章 → `spoken=to_speech(text)` → 音频生成（qwen_audio）→ 合并。
- 幂等：同月重复执行先移除旧生成点再重建。
- **本期内容**：仅建机制 + 模板 + README（写明"每月从官方/机构时政材料摘要粘贴，运行一条命令"）；**不编造事件**，待用户供稿执行。

- [ ] **Step 1: 解析器测试**（模板样例 → 2 点 + 音频调用 mock）→ **Step 2: FAIL→实现→PASS** → **Step 3: README/模板/DEPLOY 文档** → **Step 4: 暂存；M3 全绿后提交**

```bash
git add -A && git commit -m "feat(m3): chapter listen audio, quiz expansion (multi/blank/subjective), media coverage, current-affairs pipeline"
```

---

### Task 18: 端到端验收与交付

- [ ] **Step 1: 全量测试** — `pytest -q` 全绿（存量 52 + 新增 ≥25）
- [ ] **Step 2: 内容校验** — `validate_content --merge` 0 问题；计数断言 `题+卡 ≥700`；媒体每章 ≥1 脚本通过
- [ ] **Step 3: 浏览器全流程实测** — 章级听单连播/离线断网播放/三题型/模拟考试（315 客观全流程 + 刷新恢复）/复习链路（半标记→改库日期→今日复习→标记 known→毕业）/搜索/导出
- [ ] **Step 4: 汇报 + 询用户确认后 push**（含本轮新增内容量与遗留说明）

---

## Self-Review（已执行）

- **Spec 覆盖**：§二 1→T11/T6/T8；2→T1/T6/T10；3→T2/T12/T13/T14；4→T8；5→T15/T16；6→T17；7→T3/T7/T9；8→T5/T10。全覆盖。
- **占位符扫描**：无 TBD；内容作者任务给出体量、过程与验收（内容本身在执行期创作，同 V1 惯例）。
- **类型一致性**：`response` 形状（int|list[int]|list[str]）在 T2（服务）与 T7（前端）一致；`listen[]` 结构在 T6/T8/T11 一致；`exam_runs.detail_json` 在 T3/T9 一致。
- **Review Focus**：五条均挂具体任务测试/手测（T2/T7/T1/T8/T8）。
