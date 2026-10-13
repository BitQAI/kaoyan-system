# kaoyan-system 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建"考研陪跑"个人学习系统：FastAPI+SQLite 后端、原生 JS PWA 前端（听/看/测/进度/AI 问答）、内容管线（解析→口语化→TTS≤60s/点→媒体→题库）、宝塔部署文档，推送 BitQAI/kaoyan-system。

**Architecture:** 构建期在 Mac 上把四科合并版 HTML 加工为 `content.json + audio/ + media/`；运行期 FastAPI 提供内容/进度/测验/计划/AI 五组 API，Nginx 静态直出音频与前端；AI 走 opencode go 网关（deepseek-v4.1-flash，SSE），百炼兜底。

**Tech Stack:** Python 3.10+ / FastAPI / uvicorn / SQLite(WAL) / pytest+httpx / 原生 JS(ES Modules)+KaTeX(内联 vendor) / RDKit / matplotlib / PyMuPDF(裁图，仅本地) / ffmpeg

**Spec:** `docs/superpowers/specs/2026-10-13-kaoyan-system-design.md`

## Global Constraints

- 密钥只存 `.env`（600 权限），仓库只有 `.env.example`；**教材裁图放 `private-media/` 且 gitignore，不入库**。
- TTS：百炼 `qwen3-tts-flash`，**男声 Ethan**，按知识点切段 **≤60 秒/段（≤220 汉字）**，mp3 64kbps mono。
- 对话模型：opencode go 网关 `deepseek-v4.1-flash`（需 `x-opencode-session` 头=线程 id）；`.env` 的 `AI_PROVIDER` 切换 `opencode|bailian`。
- Python 业务文件软上限 300 行/硬上限 500 行；JS 模块 ≤300 行；超限先拆分。
- UI 全中文；不做 204 内容（仅进度看板）；不加前端框架。
- **Git 提交纪律**：仅里程碑边界提交（M1=T1-T7、M2=T8-T14、M3=T15-T17、M4=T18 共 4 次）+ 最终 push，此范围已获用户授权；范围外任何 git 操作先问。
- 每个任务的实现以本计划的 Interfaces 签名为准，不一致处先核对 Spec。

## Review Focus

- **首屏依赖 /api/content，接口失败/未登录时不得白屏**：应有登录跳转、加载态、失败重试（Task 8 测试：断开 content 接口时页面显示错误提示而非空白）。
- **音频断点与切段边界**：`-p1/-p2` 同点连续、只在最后一段播完时把该点标 `listened`（Task 9 测试：p1 播完只存位置不标状态；p2 播完标记）。
- **SSE 中断**：生成中途断流需保存已生成部分并在 UI 显示"已中断，可重试"（Task 7 测试：mock 流抛错后 assistant 消息仍入库）。
- **错题连对出本跨入口一致**：练习模式与错题重练都走 `apply_attempt`（Task 5 测试：两入口序列 wrong→correct→correct 均 resolved）。
- **口语化漏替换**：词典回归测试固定样本（`ΔG`、`KMnO₄`、`Ψ_w`、`H⁺-ATP 酶` → 断言输出），Task 13。

---

## 文件结构（全部新建，根目录 `~/Sync/kaoyan-system/`）

```
app/            main.py config.py db.py auth.py schema.sql
app/routers/    content.py progress.py quiz.py plan.py ai.py settings.py
app/services/   providers.py(双通道SSE) plan_engine.py progress_engine.py wrongbook.py
web/            index.html app.css js/{api,main,player,look,quiz,today,me,ai}.js sw.js manifest.json vendor/katex/*
content/        content.json audio/ media/ quiz/{812,315,101}.json media_config.py
scripts/        parse_content.py normalize.py gen_audio.py gen_media.py crop_textbook.py validate_content.py package.py
tests/          conftest.py test_*.py（与模块同名）
docs/superpowers/{specs,plans}/   DEPLOY.md  .env.example  Makefile  requirements.txt  .gitignore
```

---

### Task 1: 项目骨架 + 配置 + 数据库

**Files:**
- Create: `.gitignore`, `requirements.txt`, `Makefile`, `app/__init__.py`, `app/config.py`, `app/db.py`, `app/schema.sql`, `app/main.py`, `tests/conftest.py`, `tests/test_config.py`, `tests/test_db.py`

**Interfaces:**
- Produces: `config.get_settings() -> Settings`（字段：`password_hash, session_secret, ai_provider, opencode_key, opencode_base, bailian_key, bailian_base, content_dir, db_path, data_dir`）；`db.get_db() -> sqlite3.Connection`（per-request，WAL，`row_factory=sqlite3.Row`）；`db.init_db()`；`main.app`（FastAPI，含 `GET /api/health -> {"ok":true}`）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_db.py
from app import db
def test_init_db_creates_tables(tmp_path, monkeypatch):
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path/"t.db"))
    from app.config import get_settings; get_settings.cache_clear()
    db.init_db()
    con = db.get_db()
    names = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"progress","audio_pos","quiz_attempts","wrong_book","favorites",
            "ai_threads","ai_messages","daily_log","settings"} <= names

def test_health(tmp_path, monkeypatch):
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path/"t.db"))
    from app.config import get_settings; get_settings.cache_clear()
    from fastapi.testclient import TestClient
    from app.main import app
    assert TestClient(app).get("/api/health").json() == {"ok": True}
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_db.py -v` → FAIL（模块不存在）
- [ ] **Step 3: 实现**
  - `.gitignore`：`.env / data/ / dist/ / private-media/ / __pycache__/ / *.pdf / .venv/ content/audio/`
  - `requirements.txt`：`fastapi / uvicorn[standard] / python-dotenv / requests / pytest / httpx`
  - `config.py`：`Settings` dataclass + `get_settings()`（`lru_cache`；读 `KY_*` 环境变量覆盖，`.env` 兜底；env 名：`KY_PASSWORD_HASH, KY_SESSION_SECRET, AI_PROVIDER, OPENCODE_GO_KEY, OPENCODE_GO_BASE, BAILIAN_KEY, BAILIAN_BASE, KY_DB_PATH, KY_CONTENT_DIR, KY_DATA_DIR`）
  - `schema.sql`：按 Spec §5.2 建 9 张表（原样 SQL，`IF NOT EXISTS`）
  - `db.py`：`init_db()` 执行 schema.sql；`get_db()` 每请求新连接（`check_same_thread=False`、WAL）
  - `main.py`：FastAPI + `/api/health`；`@asynccontextmanager lifespan` 里 `init_db()`
  - `Makefile`：`test`（pytest -q）、`dev`（uvicorn app.main:app --reload --port 8000）
- [ ] **Step 4: 运行确认通过** — `pytest tests/test_db.py tests/test_config.py -v` → PASS
- [ ] **Step 5: git init + 首次提交**（M1 内不单独提交，累积到 M1 边界；此处仅 `git init`、`git add -A` 暂存）

---

### Task 2: 认证（单密码 + 90 天会话）

**Files:**
- Create: `app/auth.py`, `app/routers/__init__.py`, `tests/test_auth.py`
- Modify: `app/main.py`（挂路由）

**Interfaces:**
- Produces: `auth.hash_password(pw)->str`（scrypt，格式 `scrypt$N$r$p$salt_hex$hash_hex`）；`auth.verify_password(pw, hash)->bool`；`auth.create_token(secret, days=90, now=None)->str`（`base64url(payload) + "." + hmac_sha256_hex`，payload=`{"exp": unix_ts}`）；`auth.verify_token(token, secret, now=None)->bool`；依赖 `auth.require_auth(request) -> None`（失败 raise `HTTPException(401)`，被 `main.py` 的 exception handler 转成 JSON）。
- Routes（在 `app/routers/auth_router.py`，允许 >1 文件拆分行数）：`POST /api/login {password}` → 200 + `Set-Cookie: ky_session=…; Max-Age=7776000; HttpOnly; SameSite=Lax; Path=/`；错误密码 → 401 `{"error":"bad_password"}`；`POST /api/logout` 清 cookie；`GET /api/me` → `{"ok":true,"expires_at":…}`（需鉴权）。

- [ ] **Step 1: 写失败测试**

```python
def test_token_roundtrip_and_expiry():
    from app import auth
    t = auth.create_token("s3cret", days=90, now=1000)
    assert auth.verify_token(t, "s3cret", now=1000)
    assert not auth.verify_token(t, "s3cret", now=1000 + 90*86400 + 1)
    assert not auth.verify_token(t + "x", "s3cret", now=1000)

def test_login_flow(tmp_path, monkeypatch):
    # fixture: 设置 KY_PASSWORD_HASH = hash_password("pw")；TestClient
    # 1) 未登录访问 /api/me → 401；2) 错密码登录 → 401；3) 对密码 → 200 且 cookie 存在
    # 4) 带 cookie 访问 /api/me → 200
def test_password_hash_unique_salt():
    from app import auth
    h1, h2 = auth.hash_password("pw"), auth.hash_password("pw")
    assert h1 != h2                          # 盐不同
    assert auth.verify_password("pw", h1)     # 正确密码通过
    assert not auth.verify_password("bad", h1)  # 错误密码拒绝
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现** `auth.py`（`hashlib.scrypt(n=2**14, r=8, p=1)`、`hmac.compare_digest`、时间可注入）+ `auth_router.py` + `main.py` 挂载与 401 异常处理（`require_auth` 在路由依赖中使用）。
- [ ] **Step 4: 运行确认通过** — `pytest tests/test_auth.py -v`
- [ ] **Step 5: 暂存** `git add -A`（提交点见 Task 7 末尾）

---

### Task 3: 内容加载 + 进度引擎 + 进度 API

**Files:**
- Create: `app/services/__init__.py`, `app/services/progress_engine.py`, `app/routers/content.py`, `app/routers/progress.py`, `tests/fixtures/content_small.json`, `tests/test_progress_engine.py`, `tests/test_progress_api.py`
- Modify: `app/main.py`

**Interfaces:**
- Produces: `progress_engine.STATE_COEF = {"known":1.0,"review":0.6,"half":0.5,"listened":0.3,"new":0.0}`；`compute_chapter(points:[id], states:dict) -> float`（0..1，均值）；`compute_subject(chapters:[{points,weight_center}], states) -> {"weighted":float,"raw":float}`；`compute_all(content, states) -> list[subject_report]`。
- `content.load_content() -> dict`（启动时读 `content_dir/content.json`，缓存 + `version` 字段；文件缺失抛 `ContentMissing`，接口 503）；`GET /api/content` → 全量 JSON（鉴权）；`GET /api/progress` → `{"states":{point_id:state}, "reports":[…]}`；`POST /api/progress {"point_id","state"}`（state 白名单校验，upsert，`state=new` 视为删除行）。

- [ ] **Step 1: 写失败测试（纯函数优先）**

```python
def test_chapter_and_weighted_progress():
    from app.services.progress_engine import compute_subject
    chapters = [
      {"weight_center": 23, "points": ["a","b"]},   # 第一梯队
      {"weight_center": 6,  "points": ["c","d"]},   # 第三梯队
    ]
    states = {"a":"known","b":"half","c":"new","d":"new"}
    r = compute_subject(chapters, states, coef=None)
    assert r["raw"] == (1.0+0.5+0+0)/4
    assert abs(r["weighted"] - (0.75*23 + 0*6)/29) < 1e-9
def test_state_whitelist():
    # POST 非法 state → 422
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现** 两个 router（`dependencies=[Depends(require_auth)]` 统一挂）+ `load_content` 用 `lru_cache`；`progress.py` 的 upsert 用 `INSERT … ON CONFLICT(point_id) DO UPDATE`。
- [ ] **Step 4: 运行确认通过** — `pytest tests/test_progress_engine.py tests/test_progress_api.py -v`
- [ ] **Step 5: 暂存**

---

### Task 4: 播放位置 + 收藏 API

**Files:**
- Create: `app/routers/media_state.py`, `tests/test_media_state.py`
- Modify: `app/main.py`

**Interfaces:**
- Produces: `POST /api/audio_pos {"clip_id","position_sec","plays_delta":0|1}` → upsert（`position_sec = max(pos, 已存)`——回退不覆盖更长位置；`plays_delta=1` 时 plays+1）；`GET /api/audio_pos` → `{clip_id:{position_sec,plays}}`；`POST /api/favorite {"type","ref_id","action":"add"|"remove"}`（type 白名单 point/quiz/card/clip；insert or delete）；`GET /api/favorites` → `{"point":[…],"quiz":[…]}`。

- [ ] **Step 1: 写失败测试**：位置回退不覆盖（POST 120 后 POST 30 → GET 仍 120）；plays 累积；favorite add/remove 幂等。
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行确认通过** — `pytest tests/test_media_state.py -v`
- [ ] **Step 5: 暂存**

---

### Task 5: 测验引擎 + 测验 API（错题本连对出本）

**Files:**
- Create: `app/services/wrongbook.py`, `app/routers/quiz.py`, `tests/test_wrongbook.py`, `tests/test_quiz_api.py`
- Modify: `app/main.py`

**Interfaces:**
- Produces: `wrongbook.apply_attempt(state:{"wrong_count","streak","resolved_at"} | None, correct: bool, now: str) -> {"wrong_count","streak","resolved_at"}`（wrong：count+1、streak=0、resolved_at=None；correct 且未出本：streak+1，streak≥2 → `resolved_at=now`；correct 且无记录 → None）。
- Routes：`POST /api/quiz/attempt {"quiz_id","chosen"}` → `{"correct":bool,"explain":str}`（答案取自 content.json；写 attempts + wrong_book via `apply_attempt`）；`GET /api/quiz/wrong` → 未出本错题（含题干/选项/我的错选/次数）；`GET /api/quiz/run?mode=chapter&chapter=812-04&n=15` 与 `mode=wrong|favorites` → 组卷（错题模式仅未出本；favorites 模式从收藏 quiz 取）；`POST /api/cards/review {"card_id","verdict":"know"|"fuzzy"|"no"}` → 映射到关联 point 的 state（known/half/review 且 review 记入 daily_log.cards）。

- [ ] **Step 1: 写失败测试**

```python
def test_wrongbook_streak():
    from app.services.wrongbook import apply_attempt
    s = apply_attempt(None, False, "t1"); assert s == {"wrong_count":1,"streak":0,"resolved_at":None}
    s = apply_attempt(s, True, "t2");   assert s["streak"]==1 and s["resolved_at"] is None
    s = apply_attempt(s, True, "t3");   assert s["streak"]==2 and s["resolved_at"]=="t3"
    s = apply_attempt(s, False, "t4");  assert s["streak"]==0 and s["resolved_at"] is None
    assert apply_attempt(None, True, "t5") is None
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**（两个入口均调 `apply_attempt`——Review Focus 第 4 条）
- [ ] **Step 4: 运行确认通过** — `pytest tests/test_wrongbook.py tests/test_quiz_api.py -v`
- [ ] **Step 5: 暂存**

---

### Task 6: 每日计划引擎 + 计划/统计 API

**Files:**
- Create: `app/services/plan_engine.py`, `app/routers/plan.py`, `tests/test_plan_engine.py`, `tests/test_plan_api.py`
- Modify: `app/main.py`

**Interfaces:**
- Produces: `plan_engine.build_plan(content, states, wrong_ids, cfg) -> {"listen":[clip_id…], "look":[point_id…], "test":[quiz_id…], "est_minutes":int}`；`plan_engine.pace(content, states, days_left) -> {"remaining_weighted":float,"per_day":float,"behind":bool}`。策略（确定性贪心）：listen=有音频且 state∈{new} 的按 `weight_center*(1-chapter_completion)` 降序取到 `cfg.listen_minutes`（默认 40，`含图`点跳过）；look=state∈{half,review}∪wrong 关联点 按权重取 `cfg.look_n`（默认 8）；test=当日 look/listen 章节的 quiz 随机 `cfg.quiz_n`（默认 15）+ 未出本错题。
- Routes：`GET /api/plan/today` → `{"plan":…,"pace":…,"logs_30d":[…]}`；`GET /api/stats` → `{"streak_days":int,"today":{…},"ring":[四科 reports]}`；设置读写：`GET/POST /api/settings {"listen_minutes","look_n","quiz_n","voice","rate"}`（存 settings 表）；`POST /api/settings/password {"old","new"}`（验证旧密码后更新 `.env` 的 KY_PASSWORD_HASH 并返回提示"需重启生效"）。

- [ ] **Step 1: 写失败测试**

```python
def test_build_plan_priority(fixture_content, states):
    from app.services.plan_engine import build_plan
    p = build_plan(fixture_content, states, wrong_ids=set(), cfg={"listen_minutes":10,"look_n":2,"quiz_n":5})
    # 第一梯队未完成章节的知识点必须排在 listen 前列
    first = p["listen"][0]
    assert first.startswith("812-04")  # 光合作用（权重 23 的章节）
```

- [ ] **Step 2: 运行确认失败** → **Step 3: 实现** → **Step 4: PASS** — `pytest tests/test_plan_engine.py tests/test_plan_api.py -v` → **Step 5: 暂存**

---

### Task 7: AI 通道（双 provider SSE + 线程）＋ M1 里程碑提交

**Files:**
- Create: `app/services/providers.py`, `app/routers/ai.py`, `tests/test_providers.py`, `tests/test_ai_api.py`
- Modify: `app/main.py`

**Interfaces:**
- Produces: `providers.stream_chat(messages, session_id, settings, timeout=120) -> Iterator[dict]`（yield `{"type":"reasoning"|"content","delta":str}`；内部解析 SSE：`delta.reasoning_content` → reasoning、`delta.content` → content；opencode 通道加 `x-opencode-session: {session_id}` 头；bailian 通道不加）。`providers.build_messages(thread_owner, history, content) -> list[{"role","content"}]`（system 助教人设 + 当前锚点原文（point 取 text+spoken+媒体图注；quiz 取题干+答案+解析）+ 最近 10 轮）。
- Routes：`GET /api/ai/threads`（按 updated_at 倒序，含 owner 标题）；`GET /api/ai/threads/{id}/messages`；`POST /api/ai/chat {"owner_type":"point|quiz|free","owner_ref":…,"message":…}` → **SSE**：`data: {"type":"reasoning","delta":…}` … `data: {"type":"done","message_id":…}`；无线程自动创建（id=`uuid4`，即 `x-opencode-session` 值）。
- 中断处理（Review Focus 第 3 条）：流中途异常时把已累积的 content/reasoning 仍写入 `ai_messages`，并向客户端发 `data: {"type":"error","partial_saved":true}`。

- [ ] **Step 1: 写失败测试（mock 通道）**

```python
def test_build_messages_includes_point_text(fixture_content):
    from app.services.providers import build_messages
    msgs = build_messages(("point","812-04-01"), history=[], content=fixture_content)
    assert any("光合作用" in m["content"] for m in msgs if m["role"]=="system")

def test_stream_chat_parses_reasoning(monkeypatch):
    # monkeypatch requests.post 返回带 reasoning_content/content 的 SSE 行
    # 断言 yield 序列含 {"type":"reasoning"} 后接 {"type":"content"}

def test_ai_chat_saves_partial_on_error(monkeypatch):
    # mock stream 抛异常；断言 ai_messages 仍有半段 assistant 记录，SSE 含 error 事件
```

- [ ] **Step 2: 运行确认失败** → **Step 3: 实现** → **Step 4: PASS** — `pytest tests/ -v`（全量）
- [ ] **Step 5: M1 里程碑提交 + 汇报**

```bash
git add -A && git commit -m "feat(m1): backend skeleton — auth, content, progress, quiz, plan, ai (SSE)"
```
向用户汇报 M1 完成（任务 1-7 全绿），继续 M2 不等确认。

---

### Task 8: 前端骨架（PWA shell + 登录 + API 客户端 + 今日页最小版）

**Files:**
- Create: `web/index.html`, `web/app.css`, `web/js/api.js`, `web/js/main.js`, `web/js/today.js`, `web/manifest.json`, `web/sw.js`, `web/vendor/katex/`（下载 katex.min.css/js + mhchem.min.js + fonts）
- Modify: `app/main.py`（`StaticFiles` 挂 `web/` 于 `/`，`/audio`、`/media` 指向 content 目录）

**Interfaces:**
- Consumes: 全部 `/api/*`（cookie 鉴权，同源）。
- Produces: `api.get/post/postStream(path, body, onEvent)`（catch 401 → 显示登录屏）；`main.go(tab)`、登录屏（密码输入 → `/api/login`）；今日页最小版渲染 `GET /api/plan/today` + `/api/stats` 的进度环与听单列表。

- [ ] **Step 1: 实现 + 浏览器冒烟（本任务无 pytest，验收=浏览器）**：`make dev` 起服务后实测——
  - 未登录访问 `/` → 出现登录屏（**不白屏**，Review Focus 第 1 条）；断网/接口 500 时显示"加载失败，重试"按钮
  - 正确密码 → 进入今日页；倒计时按 2026-12-19 计算；进度环来自 `/api/stats`
  - `sw.js` 注册成功；manifest 可"添加到主屏幕"
- [ ] **Step 2: 暂存**

---

### Task 9: 前端-听页（播放器全量）

**Files:**
- Create: `web/js/player.js`
- Modify: `web/index.html`（听页 DOM/模板）、`web/js/main.js`（挂载）

**Interfaces:**
- Consumes: `GET /api/content`（points[].audio）、`GET/POST /api/audio_pos`、`POST /api/progress`。
- Produces: `player.load(queue: [clipRef])`、`player.playClip(id)`、`player.next()/prev()`、倍速/循环/±15s；播放中每 5s 节流保存位置；**单元播完 → 若该 clip 是某 point 的最后一段且 state=='new' → POST progress listed**；Media Session（锁屏标题=知识点标题、章节、前进后退）。

- [ ] **Step 1: 浏览器验收（Review Focus 第 2 条）**：队列连续播放；切段边界验证——p1 播完只存位置不标状态、p2 播完标记 listened；锁屏控制可见（iPhone Safari 实测项，桌面先验 Media Session 对象存在）；断点续听刷新后位置正确。
- [ ] **Step 2: 暂存**

---

### Task 10: 前端-看页（知识点卡 + KaTeX + 媒体 + 三态）

**Files:**
- Create: `web/js/look.js`
- Modify: `web/index.html`、`web/app.css`（媒体区样式，从原型移植）、`web/js/main.js`

**Interfaces:**
- Consumes: `GET /api/content`、`GET /api/progress`、`POST /api/progress`、`POST /api/favorite`、AI 抽屉 `ai.open(owner_type, owner_ref)`（Task 11 提供，先留调用点）。
- Produces: 科目切换（101/315/812；204 灰显"仅看板"）→ 章节卡（权重徽章 `第一梯队·23分`、加权进度条）→ 考点行（三态轮转按钮、收藏星、AI 按钮、媒体区：`tex`→KaTeX 渲染 / `img`→`<img loading=lazy>` + 图注含来源许可）。

- [ ] **Step 1: 浏览器验收**：KaTeX 公式显示（用 fixture 含 `"\ce{CH3CH2OH ->[浓H2SO4] CH2=CH2}"` 与 `"\Psi_w=\Psi_s+\Psi_p+\Psi_m"` 的条目）；状态轮转写库；刷新后保持；媒体图注显示来源。
- [ ] **Step 2: 暂存**

---

### Task 11: 前端-测页 + AI 抽屉

**Files:**
- Create: `web/js/quiz.js`, `web/js/ai.js`
- Modify: `web/index.html`（测页 + AI 抽屉 DOM）、`web/js/main.js`

**Interfaces:**
- Consumes: `GET /api/quiz/run`、`POST /api/quiz/attempt`、`GET /api/quiz/wrong`、`POST /api/cards/review`、`POST /api/ai/chat`（fetch + ReadableStream 手工解析 SSE）、`GET /api/ai/threads*`。
- Produces: `quiz.start(mode, chapter?)`；答题即判色 + 解析 + "追问 AI"；背题卡翻面 + 会了/模糊/不会；`ai.open(owner_type, owner_ref)`（标题显示锚点、思考折叠、快捷 chips、历史加载）。

- [ ] **Step 1: 浏览器验收（Review Focus 第 3 条）**：做错一题 → 错题本出现 → 错题重练连对两次 → 出本；AI 抽屉流式输出（思考区独立折叠）；手动断网模拟中途断流 → 显示"已中断，可重试"。
- [ ] **Step 2: 暂存**

---

### Task 12: 前端-今日页完整版 + 我的页

**Files:**
- Create: `web/js/me.js`
- Modify: `web/js/today.js`（今日任务/打卡/追平提示）、`web/index.html`

**Interfaces:**
- Consumes: `GET /api/plan/today`、`GET /api/stats`、`GET /api/settings`、`POST /api/settings`、`POST /api/settings/password`、`GET /api/ai/threads`。
- Produces: 今日页（听单/看单/测单跳转、连续打卡、`pace.behind` 时显示"今天补 X 个知识点可追平"）；我的页（加权/原始双值、AI 对话历史列表点击续聊、设置表单、修改密码）。

- [ ] **Step 1: 浏览器验收**：全五页串联走查（登录→听→标记→看→测→AI→我的→设置）无控制台报错；修改密码后用新密码可登录。
- [ ] **Step 2: 暂存**（M2 内容任务完成后一并提交）

---

### Task 13: 管线-解析与口语化（812 跑通）

**Files:**
- Create: `scripts/parse_content.py`, `scripts/normalize.py`, `content/media_config.py`（结构式/图表清单，先置 812 首批）, `tests/test_normalize.py`
- 输入: `../master_eaxm/2027考研_四科知识全景与章节权重.html`

**Interfaces:**
- Produces: `normalize.to_speech(text)->str`（规则表 ≥40 条：`Δ`→"德尔塔", `Ψ_w|Ψw`→"水势", `℃`→"摄氏度", `H⁺-ATP 酶`→"氢离子ATP酶", 化学式表 `KMnO₄|KMnO4`→"高锰酸钾" 等 20+ 化学式, `→`→"生成", `≈`→"约等于", `α|β|γ`→希腊读法, `⁺|⁻`→"正/负离子", 下标数字→去下标, `；`→"。", 括号内容保留但去嵌套符号）；`normalize.split_clips(text, max_chars=220)->list[str]`（按 `。；` 边界切，超长句按 `，` 再切，**保证不跨公式断**）。`parse_content.build() -> content.json`（812 12 部分→points 拆条，挂 tier/weight_center/weight_range/tags；`spoken=to_speech(text)`；`audio=[]`）。
- CLI：`python scripts/parse_content.py --subject 812 [--merged PATH]`

- [ ] **Step 1: 写失败测试**

```python
def test_to_speech_symbols():
    from scripts.normalize import to_speech
    s = to_speech("水势 Ψ_w = Ψ_s+Ψ_p，ΔG<0 时反应自发，KMnO₄ 氧化，H⁺-ATP 酶供能。")
    assert "水势" in s and "德尔塔" in s and "高锰酸钾" in s and "氢离子" in s
    assert "Ψ" not in s and "Δ" not in s
def test_split_clips_cap_and_boundary():
    from scripts.normalize import split_clips
    t = "光合作用分三个阶段。" + "第一阶段是原初反应，完成光能吸收传递与激发；" * 6
    clips = split_clips(t, 120)
    assert all(len(c) <= 120 for c in clips) and "".join(clips).replace("。","") .startswith("光合作用")
```

- [ ] **Step 2: 失败 → Step 3: 实现 → Step 4: PASS** — `pytest tests/test_normalize.py -v`
- [ ] **Step 5: 对 812 全量生成并人工抽查 30 条 spoken**（重点看化学式/希腊字母/箭头）；问题条目在 `normalize.py` 词典补规则后重跑
- [ ] **Step 6: 暂存**

---

### Task 14: 管线-TTS 批量生成（812）

**Files:**
- Create: `scripts/gen_audio.py`
- Modify: `content/content.json`（回填 audio[]）

**Interfaces:**
- Consumes: `config` 同款环境变量（`source ~/.config/kaoyan/bailian.env` 或 `.env` 的 BAILIAN_KEY/BAILIAN_BASE）；`normalize.split_clips`。
- Produces: `gen_audio.generate(content, only=None, retries=3, sleep=1.0)`——对每个 clip：POST `{bailian_base去掉compatible-mode}/api/v1/services/aigc/multimodal-generation/generation` `{"model":"qwen3-tts-flash","input":{"text":clip,"voice":"Ethan"}}` → 取 `output.audio.url` → 下载 wav → `ffmpeg -i x.wav -codec:a libmp3lame -b:a 64k -ac 1 audio/{clip_id}.mp3` → 用 ffprobe 读时长回填 `audio:[{src,dur}]`；已存在 mp3 跳过（断点续跑）；失败重试 3 次后记入 `content/audio_failed.json`。
- CLI：`python scripts/gen_audio.py --subject 812 [--dry-run]`

- [ ] **Step 1: 单元测试**（不真调 API）：clip 清单构造顺序、跳过已存在的逻辑、失败清单写入（monkeypatch `requests.post` 与 `subprocess.run`）
- [ ] **Step 2: 失败 → Step 3: 实现 → Step 4: PASS** — `pytest tests/test_gen_audio.py -v`
- [ ] **Step 5: 真跑 812 全量**（约 120-180 段，预计 15-25 分钟）→ 抽听 10 段（含化学式章节：溶液依数性、能斯特、杂化）
- [ ] **Step 6: 暂存；M2 里程碑提交**

```bash
git add -A && git commit -m "feat(m2): web PWA 5 tabs + audio pipeline(812) + katex/media"
```
向用户汇报 M2（前端全量 + 812 音频可听）。

---

### Task 15: 管线-媒体（RDKit / matplotlib / Commons / 教材裁图）

**Files:**
- Create: `scripts/gen_media.py`, `scripts/crop_textbook.py`, `content/media_config.py`（扩充：812 示意图清单）
- Modify: `content/content.json`（回填 media[]）

**Interfaces:**
- `gen_media.structures(mapping: {point_id: smiles}, out_dir)`（RDKit `MolFromSmiles`→`rdMolDraw2D.MolDraw2DSVG`→`media/{point_id}-s.svg`）；`gen_media.charts(cfg: {point_id: chart_fn}, out_dir)`（matplotlib，Agg；首批：812 光响应曲线、315 滴定曲线（用 calc 生成））；`gen_media.commons_search(query, n=5) -> candidates`（Commons API，返回 `{title,url,license,attribution}` 写 `media/_candidates.json` 供人工挑选，挑选结果手动写入 config）；`crop_textbook.crop(fig_cfg: {out: (pdf, page, bbox)}, out_dir)`（PyMuPDF `page.get_pixmap(clip=...)`→PNG，输出到 `private-media/`）。
- 所有入库媒体必须带 `source/license/attribution/caption`（AI 生成 `source:"ai"`、标注"AI 生成示意图"）。

- [ ] **Step 1: 实现 + 单测**（RDKit SVG 含 `<svg` 且非空；charts 文件存在且 >5KB；crop 输出尺寸=bbox 缩放）
- [ ] **Step 2: 812 首批跑通**：结构式 0 个（812 无）→ 图表 2 张 + 教材裁图 10-15 张（人工定位页码区域）+ Commons 候选 10 个人工挑 3-5 个。首批目标：812 每章至少 1 张媒体（共 ≥12）
- [ ] **Step 3: 回填 content.json 并浏览器核验显示（看页媒体区）**
- [ ] **Step 4: 暂存**

---

### Task 16: 题库与背题卡（812）

**Files:**
- Create: `content/quiz/812.json`（我逐章撰写：每章 8-15 选择 + 名解/简答卡）, `scripts/validate_content.py`, `tests/test_validate_content.py`
- Modify: `content/content.json`

**Interfaces:**
- `validate_content.check(content) -> [errors]`：quiz 字段完整（stem/options≥2/answer 在界内/explain/point_id 存在/exam 关联章节存在）；cards front/back 非空；无重复 id；media 引用文件存在。`validate_content.merge()` 把 `content/quiz/*.json` 并进 `content.json`。

- [ ] **Step 1: 写校验器 + 失败测试**（构造缺 answer 的坏题断言报错）
- [ ] **Step 2: 我撰写 812 题库**（首批每章 8 题，第一梯队 12 题；解析 2-4 句；含图题引用 media）→ 运行 validate → 全绿
- [ ] **Step 3: 人工抽查 30 题**（用户抽查清单输出 `content/quiz/_review_812.md`：题干/答案/解析三列）
- [ ] **Step 4: 暂存**

---

### Task 17: 315 + 101 全量管线

**Files:**
- Modify: `content/quiz/315.json`, `content/quiz/101.json`, `content/media_config.py`, `content/content.json`

- [ ] **Step 1: parse+normalize 315**（26 章，化学式/公式最重）→ 抽查 50 条 spoken
- [ ] **Step 2: gen_audio 315** → 抽听 15 段（滴定/结构/热力学）
- [ ] **Step 3: parse+normalize+audio 101**（6 模块）→ 抽听 10 段
- [ ] **Step 4: 315 媒体**（结构式 15-25 个 SMILES：常见有机物；滴定曲线 4 张；Commons/教材裁图 ≥10）
- [ ] **Step 5: 315/101 题库**（315 每章 8 题；101 每模块 15 题）→ validate + 抽查
- [ ] **Step 6: 全量 validate_content + 打包 `make dist`**（dist= web+content+audio+media+hash 清单）
- [ ] **Step 7: M3 里程碑提交**

```bash
git add -A && git commit -m "feat(m3): full content for 315/812/101 — audio, media, quiz"
```

---

### Task 18: 部署文档 + 端到端验收 + 推送

**Files:**
- Create: `DEPLOY.md`, `.env.example`
- Modify: `Makefile`（`dist/deploy` 目标）

- [ ] **Step 1: 写 DEPLOY.md**（按 Spec §11：宝塔建站→Let's Encrypt→clone→venv→.env→`python scripts/gen_audio.py`（服务器端生成，需 BAILIAN_KEY）→init_db→Python 项目管理器启动→Nginx /api 反代→备份计划任务→**教材裁图单独上传 `private-media → content/media-private`**；含验收清单）
- [ ] **Step 2: 本地端到端**：`make dev` 全流程走查（登录、听 3 段连续、看含图点、做 10 题错 2 题、错题重练出本、AI 流式问答 3 轮、我的页进度/历史核对）
- [ ] **Step 3: Review Focus 五条逐条复核**并记录结果
- [ ] **Step 4: 用户确认后推送**

```bash
git add -A && git commit -m "feat(m4): deploy docs, e2e polish, ready for production"
git push -u origin main   # ← 执行前再次向用户确认
```

- [ ] **Step 5: 汇报交付**：仓库地址、DEPLOY.md 路径、已知限制（Commons 候选未全部审定、AI图核验清单）、后续增量说明（`make content`/`make audio` 重跑即可）

---

## Self-Review（已执行）

- **Spec 覆盖**：Spec §4 架构→T1/T8；§5 数据模型→T1(表)/T3-6(接口)/T13(JSON)；§6 AI→T7/T11；§7 多媒体→T15；§8 页面→T8-12；§9 管线→T13-17；§10 计划→T6/T12；§11 部署→T18；§12 验收→T18 Step 2-3 + 各任务浏览器验收；§13 里程碑→M1-M4 提交点；§14 风险→Review Focus + DEPLOY 注意事项。无遗漏。
- **占位符扫描**：无 TBD/TODO；每个任务含真实文件路径、接口签名、测试代码或验收步骤。
- **类型一致性**：`apply_attempt / build_plan / build_messages / to_speech / split_clips / stream_chat` 签名在定义处与使用处一致（Task 5→5，13→14，7→11）。`clip_id` 命名规则 `{point_id}[-p{n}]` 在 T9/T13/T14 一致。
- **Review Focus**：五条均已挂到具体任务测试（T8/T9/T7/T5/T13）。
