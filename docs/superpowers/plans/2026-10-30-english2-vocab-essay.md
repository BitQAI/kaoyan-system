# 英语（二）词汇与作文纳入复习 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 1500 核心词、80 词组、30 组易混与 12 篇背诵范文做成可翻面、可发音、可听、可默写的卡片，接入现有复习队列。

**Architecture:** 元数据仍是 ky-point/3.0，词汇与词组各成一个新章节，作文作为新知识点挂在 204-08 / 204-09 下；卡片新增 `payload` JSON 列承载词卡结构化内容，前端在「记」视图按 payload 走专门渲染分支，其余队列、调度、进度、AI 归档全部复用。内容由离线脚本从真题语料生成，产物经 `validate.py` 校验后导入。

**Tech Stack:** FastAPI + SQLite（原生 sqlite3）+ Alembic；Next.js 14 + React 18 + TypeScript；Python 3.11 脚本；Fish Audio TTS（英文片可换 edge-tts）。

**Spec:** `docs/superpowers/specs/2026-10-30-english2-vocab-essay.md`

**原型:** `docs/prototypes/2026-10-30-vocab-essay-cards.html`

## Global Constraints

- 所有 `git commit` 必须先向用户汇报并得到明确同意，不得自行提交；每个 Task 结束时停下等确认。
- 模型改动与 Alembic 迁移必须同一次提交；改完依次跑 `alembic check`、`alembic upgrade head`。
- 业务逻辑文件软上限 300 行、硬上限 500 行；函数软上限 30 行。超限先拆再写。
- 元数据只读上游：`知识点元数据/` 是唯一真源，应用不反写。
- 真题原文、题面、答案只放本地语料缓存（`知识点元数据/research/204-corpus/`，加入 `.gitignore`），仓库内只保留句子级片段。
- 12 篇范文全部自写，不抄市面范文。
- 卡片里凡不是真题原句的例句，必须带 `"note": "例句（非真题原句）"`。
- 前端改动完成后必须用浏览器实机验证（dev server + 真实点击），不能只跑 typecheck。

## Review Focus

1. **老卡片没有 payload**：3171 张既有卡片 `payload` 为空对象，前端必须继续按问答卡渲染，翻面、评分、AI 追问一个不能坏。
2. **分片音频缺失或 404**：播放按钮不能变成死按钮或报错弹窗，应静默回退浏览器 TTS。
3. **`clip` 参数被构造**：`?clip=../../etc/passwd` 之类必须 404，不能读到音频目录外的文件。
4. **默写卡空格数与答案数不一致**：前端不能越界渲染或把多出的答案丢掉，应显示可诊断提示。
5. **真题标签失真**：卡面标「真题」的条目必须能回溯到语料中的那一句，抽查不一致即为缺陷。

---

### Task 0（已完成，2026-10-30）: 删除 204 技巧内容

204 原有 51 个技巧点 / 301 张卡整体删除：`204.md` 只留写作 A/B 两章、知识点与关联表清空；
`import_meta.py` 重建后卡片 3171 → 2870；新增 `backend/scripts/prune_orphans.py` 清理悬空的
进度、事件、收藏记录。后续装配（Task 11）不得把技巧点写回 204。

---

### Task 1: 卡片 payload 贯通（库表、导入器、队列）

**Files:**
- Create: `backend/migrations/versions/0007_add_card_payload.py`
- Modify: `backend/app/models.py`（`card` 表加列）
- Modify: `backend/app/importer.py:_insert_cards`
- Modify: `backend/app/service.py`（`card_queue`、`custom_cards` 的 SELECT 与返回字典）
- Test: `backend/tests/test_importer.py`、`backend/tests/test_study.py`

**Interfaces:**
- Produces: `card.payload TEXT NOT NULL DEFAULT '{}'`；API 卡片对象新增 `payload: dict`（解析后的 JSON，缺省 `{}`）。
- Produces: 元数据卡片字段 `cards[].payload`（可选对象），导入器原样序列化写库。

- [ ] **Step 1: 写失败测试** — 在 `backend/tests/test_importer.py` 加 `test_card_payload_imports`：用 `_insert_cards(conn, {"id": "2041001", "cards": [{"card_id": "c2041001-1", "kind": "词汇", "card_type": "记忆", "question": "q", "answer": "a", "analysis": "x" * 40, "answer_points": ["a", "b"], "unit_refs": [1], "payload": {"word": "momentum"}}]})`，断言 `SELECT payload FROM card WHERE card_id='c2041001-1'` 解析出 `{"word": "momentum"}`；再加 `test_card_payload_defaults_empty`：不带 payload 的卡读到 `{}`。

- [ ] **Step 2: 跑测试确认失败** — `backend/.venv/bin/python -m pytest backend/tests/test_importer.py -k payload -v`，预期 `no such column: payload`。

- [ ] **Step 3: 加列与导入** — `models.py` 的 `card` 表加 `Column("payload", Text, nullable=False, default="{}")`；`_insert_cards` 的 INSERT 增加 `payload` 列，值用 `json.dumps(c.get("payload") or {}, ensure_ascii=False)`；迁移 `0007_add_card_payload.py` 用 `op.add_column('card', sa.Column('payload', sa.Text(), nullable=False, server_default='{}'))`，`downgrade` 用 `batch_alter_table` 删列。

- [ ] **Step 4: 队列带出 payload** — `service.py` 两处 SELECT 加 `c.payload`，返回字典加 `"payload": _loads(r["payload"], {})`。

- [ ] **Step 5: 补队列测试** — `backend/tests/test_study.py` 加 `test_queue_returns_payload`：往 `card` 插入一张带 payload 的卡（直接 SQL），调用 `/api/queue/custom`，断言该项 `payload["word"] == "momentum"`；再断言普通卡返回 `{}`。

- [ ] **Step 6: 跑全量后端测试** — `backend/.venv/bin/python -m pytest backend/tests -q`，预期全绿。

- [ ] **Step 7: 汇报并等确认提交** — `alembic check` 与 `alembic upgrade head` 输出贴给用户，同意后 `git commit -m "feat(card): carry structured payload for vocabulary cards"`。

---

### Task 2: 音频分片接口

**Files:**
- Modify: `backend/app/routers/audio.py`
- Test: `backend/tests/test_audio.py`

**Interfaces:**
- Produces: `GET /api/audio/{card_id}?clip={word|meaning|sentence|para}`；无 `clip` 时行为不变；文件路径 `{AUDIO_DIR}/{subject}/{card_id}-{clip}.mp3`。
- Consumes: Task 1 的卡片查询（不变）。

- [ ] **Step 1: 写失败测试** — `test_audio_clip_hit`：写 `{card_id}-word.mp3`，请求 `?clip=word` 得 200 且内容匹配；`test_audio_clip_missing`：文件不存在得 404；`test_audio_clip_invalid`：`?clip=../../etc/passwd` 得 404；`test_audio_clip_keeps_default`：不带 clip 仍读 `{card_id}.mp3`。

- [ ] **Step 2: 跑测试确认失败** — `backend/.venv/bin/python -m pytest backend/tests/test_audio.py -q`，预期新用例失败（`clip` 被忽略）。

- [ ] **Step 3: 实现** — 路由签名加 `clip: str | None = None`；合法值集合 `{"word", "meaning", "sentence", "para"}`，不合法直接 404；文件名 `f"{card_id}-{clip}.mp3" if clip else f"{card_id}.mp3"`。卡片 id 白名单正则不变。

- [ ] **Step 4: 跑测试** — 同命令，预期全绿。

- [ ] **Step 5: 汇报并等确认提交** — `git commit -m "feat(audio): serve card audio clips by part"`。

---

### Task 3: 前端类型与词卡渲染

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/components/WordFace.tsx`
- Modify: `frontend/src/components/MemoView.tsx`（正反面按 payload 分支）
- Modify: `frontend/src/app/memo.css`（词卡专用样式，尺寸与原型一致）

**Interfaces:**
- Consumes: Task 1 的 `payload` 对象。
- Produces: `export interface WordPayload`，字段 `type: "word" | "phrase" | "confusable"`、`word?`（仅 word / phrase 类型有）、`phonetic?`、`meanings: {pos: string; cn: string}[]`、`examples: WordExample[]`、`confusables?: {word: string; diff: string}[]`、`phrases?: {en: string; cn: string}[]`、辨析卡另有 `group?: string[]`、`stem?`、`answer?`、`diff?`；`WordExample` 含 `kind: "真题" | "例句"`、`quote`、`cn?`、`year?`、`part?`、`text?`、`qno?`、`tested?`、`note?`。
- Produces: `<WordFace card={card} side="front" | "back" />`，纯展示，不持有翻面状态。

- [ ] **Step 1: 类型** — `types.ts` 的 `Card` 加 `payload: WordPayload | Record<string, never>`，并导出上述接口。

- [ ] **Step 2: 组件** — 正面：词 + 音标 + 发音按钮（`/api/audio/{card_id}?clip=word`，失败回退 `speechSynthesis`）；背面按原型顺序渲染释义、真题情境（`kind === "真题"` 用绿色 `真题` 徽标、否则琥珀色「非真题原句」）、考法、易混、词组。释义与例句各有独立发音按钮（`clip=meaning` / `clip=sentence`）。

- [ ] **Step 3: MemoView 分支** — 翻面卡内部：`card.payload?.type` 存在时正面渲染 `<WordFace side="front" />`、背面 `<WordFace side="back" />`，保留顶部徽标、收藏、去学、问 AI、评分与滑动逻辑；payload 为空时走原有渲染，一行不改。

- [ ] **Step 4: 类型检查** — `npm --prefix frontend run typecheck`，预期无错误。

- [ ] **Step 5: 造一张样例卡实机验证** — 在测试库插入一张带 payload 的卡（或临时在元数据加一张），启动 backend + frontend，打开「记」，确认：正面居中、翻面分段正确、两种徽标颜色正确、缺失音频时按钮不报错。截图与结论汇报给用户。

- [ ] **Step 6: 汇报并等确认提交** — `git commit -m "feat(memo): render vocabulary cards from payload"`。

---

### Task 4: 默写卡渲染与比对

**Files:**
- Create: `frontend/src/lib/cloze.ts`
- Create: `frontend/src/components/ClozeFace.tsx`
- Modify: `frontend/src/components/MemoView.tsx`（`kind === "默写"` 分支）
- Test: `frontend/e2e/vocab.mjs`（新增，Task 13 复用）

**Interfaces:**
- Produces: `parseCloze(question: string): string[]`（按 `____` 切段，返回 n+1 段文本）；`checkCloze(inputs: string[], answers: string[]): boolean[]`，比对规则：小写、去首尾标点与多余空格、忽略大小写。
- Produces: `<ClozeFace card={card} onChange={...} />`，输入值由 MemoView 持有，翻面后展示完整段落。

- [ ] **Step 1: 写失败测试** — `frontend/e2e/vocab.mjs` 里先写一条断言：构造 `parseCloze("a ____ b ____ c")` 返回 `["a ", " b ", " c"]`；`checkCloze(["Expect"], ["expect"])` 返回 `[true]`。用 `node frontend/e2e/vocab.mjs --unit` 直接跑（脚本内用 `node:assert`，不依赖浏览器）。

- [ ] **Step 2: 跑确认失败** — 预期模块不存在。

- [ ] **Step 3: 实现 cloze.ts** — 上述两个纯函数；`checkCloze` 长度不等时多余项一律 `false`，不抛异常。

- [ ] **Step 4: 实现 ClozeFace.tsx** — 正面按 `question` 的 `____` 顺序渲染 `input` + 「检查」按钮，结果按 Task 原型显示 `n / m 正确` 与标准答案；空格数少于 `answer_points` 长度时，底部显示「答案数与空格数不一致（n/m）」。背面展示 `answer` 全文。

- [ ] **Step 5: 跑单测 + 类型检查** — `node frontend/e2e/vocab.mjs --unit` 通过；`npm --prefix frontend run typecheck` 无错误。

- [ ] **Step 6: 实机验证** — 插入一张 `kind="默写"`、`question` 带两个 `____`、`answer_points` 两项的样例卡，浏览器里填对一格、填错一格，确认判定颜色、计数与标准答案展示。

- [ ] **Step 7: 汇报并等确认提交** — `git commit -m "feat(memo): add cloze card with answer checking"`。

---

### Task 5: 元数据 schema 与校验扩展

**Files:**
- Modify: `知识点元数据/schema/ky-point.schema.json`
- Modify: `知识点元数据/scripts/validate.py`
- Modify: `知识点元数据/数据校验规则.md`（补充 E24/E25 条目）
- Test: `知识点元数据/tests/test_validate_v3.py`（追加用例）

**Interfaces:**
- Produces: 卡片可选字段 `payload`（object）；204 的 `kind` 白名单扩为 `{词汇, 句型, 技巧, 模板, 回译, 默写}`。
- Produces: 校验错误码 `E24`（payload 类型或必填字段缺失）、`E25`（默写卡 `____` 数量与 `answer_points` 数量不等）。
- Produces: 按 `payload.type` 分支校验：`word` 必填 `word`、`meanings`（≥1）、`examples`（≥1）；`phrase` 必填 `word`、`meanings`、`examples`；`confusable` 必填 `group`（≥2）、`stem`、`answer`、`diff`。

- [ ] **Step 1: 写失败测试** — 在 `test_validate_v3.py` 追加：构造一个最小 204 文档，含一张 `kind="默写"` 且两个 `____` 但 `answer_points` 三项的卡，断言 errors 里有 `E25`；构造 `kind="词汇"` 但 payload 缺 `examples`，断言 `E24`；构造 `kind="回译"` 的合法卡，断言无 E16。

- [ ] **Step 2: 跑确认失败** — `python3 知识点元数据/tests/test_validate_v3.py`，预期新断言失败。

- [ ] **Step 3: 实现** — `validate.py`：`KINDS_BY_SUBJECT['204']` 加入 `回译`、`默写`；新增 `_check_payload(c)` 与 `_check_cloze(c)` 两个函数，在卡片循环里调用；schema 的 `cards.items.properties` 增加 `payload: {type: "object"}`。

- [ ] **Step 4: 跑测试** — 同命令，预期通过；再跑 `python3 知识点元数据/scripts/validate.py`，现有 204 不应新增告警。

- [ ] **Step 5: 汇报并等确认提交** — `git commit -m "feat(meta): validate vocabulary payload and cloze cards"`。

---

### Task 6: 真题语料与研究产物

**Files:**
- Create: `知识点元数据/research/204-corpus/raw/{year}-{part}.txt`（本地，不入 git）
- Create: `知识点元数据/research/204-corpus/index.json`（本地，不入 git）
- Create: `知识点元数据/research/204-corpus/sentences.jsonl`（本地，不入 git）
- Create: `知识点元数据/scripts/vocab_corpus.py`
- Modify: `.gitignore`（加 `知识点元数据/research/204-corpus/`）
- Modify: `知识点元数据/research/204-sources.md`（记录抓取来源与缺失年份）

**Interfaces:**
- Produces: `sentences.jsonl`，每行 `{"year": 2018, "part": "阅读A", "text": "Text 2", "para": 3, "sent": 5, "en": "...", "qno": 3, "stem": "...", "answer": "B", "explain": "..."}`；缺失字段留空。
- Produces: `vocab_corpus.py` 子命令 `merge`：把 `raw/` 下的原文切成句子写 `sentences.jsonl`；不联网。

- [ ] **Step 1: 抓语料** — 用 Exa 检索并抓取 2010–2025 英语二完形、阅读 A 四篇、阅读 B、翻译原文与对应题目/答案页，逐年存成 `raw/{year}-{part}.txt`，同时把来源 URL 与缺失年份写进 `204-sources.md`。抓不到的年份不猜、留空并在文档中标注。

- [ ] **Step 2: 写解析脚本** — `vocab_corpus.py`：读 `raw/`，按空行分段落、按 `. ? !` 分句（保留引号内的句号不切），输出 `sentences.jsonl`；题目段以 `Question N` / `第N题` 起头，紧跟的选项与答案解析归到该题。

- [ ] **Step 3: 覆盖率自检** — 打印统计：每年各题型句数、带题目的句子占比、总句数。目标：阅读 A + 翻译 ≥ 5000 句，带题目信息的句子 ≥ 40%。数字贴给用户。

- [ ] **Step 4: 汇报并等确认提交** — 只提交脚本与 `.gitignore`、`204-sources.md`：`git commit -m "chore(research): build kaoyan english-2 corpus pipeline"`。

---

### Task 7: 选词（1500 词表）

**Files:**
- Create: `知识点元数据/scripts/vocab_pick.py`
- Create: `知识点元数据/subjects/204/204-vocab-list.jsonl`
- Test: `知识点元数据/tests/test_vocab_pick.py`

**Interfaces:**
- Produces: `204-vocab-list.jsonl`，每行 `{"word": "momentum", "freq": 37, "years": [2018, 2021], "in_corpus": true}`，按 `freq` 降序，共 1500 行。
- Produces: `pick(sentences_path: Path, limit: int = 1500) -> list[dict]`。

- [ ] **Step 1: 写失败测试** — 用三句人造语料断言：功能词（the / of）被排除、只出现一次的词不入选（阈值可配）、排序按词频降序、同频按字母序稳定。

- [ ] **Step 2: 跑确认失败** — `python3 知识点元数据/tests/test_vocab_pick.py`。

- [ ] **Step 3: 实现** — 分词用正则 `[A-Za-z][A-Za-z'-]+`，小写化；排除停用词表（内联常量约 120 词）、中学基础词表（仓库内不存在则用长度 ≤ 3 且非学术词的近似规则，并在脚本头注释说明这是近似）；保留 `in_corpus=false` 的补充位：先取语料高频，不足 1500 时从备用高频词表（脚本内联，约 300 词）按字母序补齐并标 `in_corpus: false`。

- [ ] **Step 4: 跑并产出** — 生成 `204-vocab-list.jsonl`；打印词频分布与 `in_corpus` 计数给用户确认。

- [ ] **Step 5: 汇报并等确认提交** — `git commit -m "feat(vocab): pick 1500 high-frequency words from exam corpus"`。

---

### Task 8: 词条生成（释义、音标、易混、例句）

**Files:**
- Create: `知识点元数据/scripts/vocab_enrich.py`
- Create: `知识点元数据/subjects/204/204-vocab.jsonl`
- Test: `知识点元数据/tests/test_vocab_enrich.py`

**Interfaces:**
- Consumes: `204-vocab-list.jsonl`；`scripts/llm.py` 的 `call(prompt)` 接口。
- Produces: `204-vocab.jsonl`，每行 `{"word", "phonetic", "meanings": [{"pos", "cn"}], "confusables": [{"word", "diff"}], "phrases": [{"en", "cn"}], "examples": [{"kind", "quote", "cn", "year", "part", "text", "qno", "tested"}]}`；`examples` 至少 1 条，`kind="真题"` 的 `quote` 必须能在 `sentences.jsonl` 中精确命中（去空白后子串匹配）。
- Produces: `enrich(word: str, llm) -> dict`，单次调用失败返回 `None` 由调用方重试。

- [ ] **Step 1: 写失败测试** — 用假 LLM（返回固定 JSON）断言：解析出的对象被规范化（`meanings` 去空、`pos` 统一带点号）；`verify_example` 对语料中存在的句子返回 True、对改写过主语的句子返回 False。

- [ ] **Step 2: 跑确认失败** — `python3 知识点元数据/tests/test_vocab_enrich.py`。

- [ ] **Step 3: 实现** — 提示词固定输出 JSON（字段与上面一致），走 `llm.py` 的重试；`verify_example(sentence, corpus)` 做归一化子串匹配；真题例句按 `word → sentences` 索引在本地回填 `year/part/text/qno/tested`，匹配不到就把该条例句降级为 `{"kind": "例句", "note": "例句（非真题原句）"}`。

- [ ] **Step 4: 小批量验证** — 先跑 50 词，人工抽查 10 条（释义准确性、易混是否同词性、真题句是否真的含该词）后贴给用户；确认后再跑剩余。

- [ ] **Step 5: 全量跑 + 统计** — 输出：真题例句覆盖率、平均例句数、易混缺失词数（`confusables` 为空的词应 < 10%）。

- [ ] **Step 6: 汇报并等确认提交** — `git commit -m "feat(vocab): generate word entries with exam contexts"`。

---

### Task 9: 词组与辨析

**Files:**
- Create: `知识点元数据/scripts/vocab_phrases.py`
- Create: `知识点元数据/subjects/204/204-phrases.jsonl`、`204-confusable.jsonl`
- Test: `知识点元数据/tests/test_vocab_phrases.py`

**Interfaces:**
- Produces: `204-phrases.jsonl`，80 行 `{"phrase", "cn", "examples": [...], "confusables": [...]}`；`204-confusable.jsonl`，30 行 `{"group": [3 个词], "stem", "answer", "diff", "option_note"}`。
- Consumes: Task 6 的语料、Task 8 的 `verify_example`。

- [ ] **Step 1: 写失败测试** — 断言：词组抽取对给定 5 句样本产出 `pick up momentum` 这类三词搭配；辨析组的 `answer` 必须属于 `group`。

- [ ] **Step 2: 跑确认失败** — `python3 知识点元数据/tests/test_vocab_phrases.py`，预期新断言失败。

- [ ] **Step 3: 实现** — 词组用"动词 + 介词/副词"与"名词 + 介词"的 n-gram 统计取 top，再交 LLM 写中文与辨析；辨析组由 LLM 按"形近或义近且考场易混"生成，每组必须给出语境句且答案唯一。

- [ ] **Step 4: 人工抽查** — 各抽 10 条贴给用户确认。

- [ ] **Step 5: 汇报并等确认提交** — `git commit -m "feat(vocab): add phrase and confusable word sets"`。

---

### Task 10: 12 篇范文

**Files:**
- Create: `知识点元数据/scripts/essay_build.py`
- Create: `知识点元数据/subjects/204/204-essays.jsonl`
- Test: `知识点元数据/tests/test_essay_build.py`

**Interfaces:**
- Produces: `204-essays.jsonl`，12 行 `{"id": "2040805", "chapter": "204-08", "title", "type": "建议信" | "图表·柱状静态" …, "paragraphs": [{"en", "cn"}], "sentences": [{"en", "cn", "blank"}] , "transfer": ["可替换句式"]}`。
- Produces: `build_points(essays) -> list[dict]`，产出知识点 dict（含 `explain`、`spoken`、`listen`、`units`、`cards`），卡片 id 规则 `c{point_id}-{n}`，kind 依次为 `模板`（整篇）、`回译`（每段）、`默写`（每段）、`句型`（一篇一张）。

- [ ] **Step 1: 写失败测试** — 用一篇两段样例断言：产出 1 个点、`1 + 2 + 2 + 1` 张卡；每张默写卡的 `____` 数 == `answer_points` 数；`unit_refs` 全部落在 `units` 范围内。

- [ ] **Step 2: 跑确认失败** — `python3 知识点元数据/tests/test_essay_build.py`。

- [ ] **Step 3: 先写 2 篇跑通（M0 出口）** — 1 篇小作文 + 1 篇大作文，跑通装配、导入、整篇听、回译、默写后再补剩余 10 篇。

- [ ] **Step 4: 写剩余 10 篇正文** — 小作文：建议信（二选一）、道歉信、感谢信、通知、投诉信、询问/回复信；大作文：柱状静态对比、柱状两年升降、柱状单指标增长、饼状占比、折线上升、表格。每篇给出：英文全文、逐段中文、挖空句（每段 2–3 空，挖功能词与高分表达）、3–5 条可替换句式。小作文约 100 词，大作文约 150 词。

- [ ] **Step 5: 生成元数据** — 跑 `essay_build.py` 写 `204-essays.jsonl`；打印每篇词数与卡片数。

- [ ] **Step 6: 人工对照检查** — 12 篇全文贴给用户过目（这是要背的文本，必须本人认可）。

- [ ] **Step 7: 汇报并等确认提交** — `git commit -m "feat(essay): add 12 recitation essays covering all types"`。

---

### Task 11: 装配、导入与全量校验

**Files:**
- Create: `知识点元数据/scripts/vocab_assemble.py`
- Create: `知识点元数据/subjects/204/chapters/204-10.json`、`204-11.json`（脚本生成）
- Modify: `知识点元数据/subjects/204/204.json`（脚本生成，勿手改）
- Test: `知识点元数据/tests/test_vocab_assemble.py`

**Interfaces:**
- Consumes: `204-vocab-list.jsonl`、`204-vocab.jsonl`、`204-phrases.jsonl`、`204-confusable.jsonl`、`204-essays.jsonl`、既有 `chapters/204-01..09.json`。
- Produces: 5 个 canned 结构——词汇点 `2041001..2041050`（每点 30 词，units 与词一一对应，card id `c{pid}-{1..30}`）；词组点 `2041101..2041103`、辨析点 `2041104`；作文点 `2040805..2040810`、`2040906..2040911`；合并后的 `204.json`。
- Produces: `assemble(meta_dir: Path) -> dict`，返回各章节点数与卡片数；**幂等**：重复运行结果一致，且不改动 204-01..09 的章节文件。
- Produces: payload 映射规则（装配时统一成型，前端只认这一种形状）：词条 → `{"type":"word", "word", "phonetic", "meanings", "examples", "confusables", "phrases"}`；词组 → `{"type":"phrase", "word": phrase, "meanings": [{"pos":"phr.", "cn"}] , "examples", "confusables"}`；辨析 → `{"type":"confusable", "group", "stem", "answer", "diff"}`。

- [ ] **Step 1: 写失败测试** — 用 3 词 + 1 词组 + 1 辨析 + 1 篇作文的样例跑 `assemble`，断言：点 id 连续、每卡 `unit_refs=[i]`、`answer_points` 2–6 条、`analysis` ≥30 字、作文点被追加到对应章节、重复运行两次产物字节相同。

- [ ] **Step 2: 跑确认失败**。

- [ ] **Step 3: 实现装配** — 读基础章节（01–09）→ 生成 204-10 / 204-11 → 把作文点 append 到 08/09 章节 → 汇总写 `204.json`（`points` 扁平、`chapters` 带 counts）。章节字段：204-10 `module=词汇, tier=2, weight_center=30`；204-11 `module=词组辨析, tier=2, weight_center=20`；`weight_basis` 按 Spec 表。

- [ ] **Step 4: 全量装配 + 校验** — 跑 `validate.py`（预期 0 error），打印 204 的点数/卡数/unit 数；再跑 `backend/.venv/bin/python backend/scripts/import_meta.py`，贴导入计数。

- [ ] **Step 5: 抽查 30 条真题标注** — 随机取 30 条 `kind="真题"` 的例句，逐条与语料比对年份、题型、原句一致性，错 0 条才继续；结果贴给用户。

- [ ] **Step 6: 汇报并等确认提交** — `git commit -m "feat(meta): assemble vocabulary and essay chapters into 204"`。

---

### Task 12: 音频生成

**Files:**
- Create: `知识点元数据/scripts/vocab_audio.py`
- Modify: `data/audio/204/`（产物，不入 git）
- Test: `知识点元数据/tests/test_vocab_audio.py`

**Interfaces:**
- Consumes: `204.json`、`gen_audio.py` 的 `synth(text, voice, key)`。
- Produces: 词卡 `{card_id}-word.mp3`、`-meaning.mp3`、`-sentence.mp3`、`{card_id}.mp3`（三段字节拼接）；作文卡 `{card_id}-para.mp3` 与 `{card_id}.mp3`。
- Produces: `scripts_for(point) -> list[dict]`，每条 `{"clip", "text", "lang"}`，测试只断言文本，不联网。

- [ ] **Step 1: 写失败测试** — 断言词卡脚本恰好三条且顺序为「词 → 释义 → 句」，释义文本是中文、句子文本不带中文；作文整篇卡只有一条 `full`。

- [ ] **Step 2: 跑确认失败** — `python3 知识点元数据/tests/test_vocab_audio.py`。

- [ ] **Step 3: 音色验证（M0 出口）** — 先合成 5 个词 + 3 句的英文样本，交用户试听；Fish 英文不可用则改 edge-tts 生成英文片，中文片仍用 Fish。结论写进 `research/204-sources.md`。

- [ ] **Step 4: 实现与断点续跑** — 已存在的 mp3 跳过；失败重试 5 次；整卡音频用分片字节顺序拼接。

- [ ] **Step 5: 全量生成** — 预计约 4500 条片段；跑完统计缺失率，必须为 0。耗时与体积贴给用户。

- [ ] **Step 6: 汇报并等确认提交** — 只提交脚本与测试：`git commit -m "feat(audio): generate word and essay audio clips"`。

---

### Task 13: 端到端验收

**Files:**
- Create: `frontend/e2e/vocab.mjs`（在 Task 4 基础上补浏览器流程）
- Modify: `docs/superpowers/specs/2026-10-30-english2-vocab-essay.md`（若验收中口径有变，回写）
- Test: `frontend/e2e/vocab.mjs`

**Interfaces:**
- Consumes: 全部前置任务的产物与接口。

- [ ] **Step 1: 写端到端脚本** — 登录 → 「记」选词汇章节 → 翻面 → 断言释义与真题徽标出现 → 播放音频按钮存在 → 评分后进度 +1 → 「听」选同一章节 → 断言词卡可播 → 打开一篇作文点 → 断言整篇朗读卡、回译卡、默写卡都在 → 打开一张空格数与答案数不一致的样例卡，断言页面出现「答案数与空格数不一致」提示且不崩。

- [ ] **Step 2: 跑后端全量测试** — `backend/.venv/bin/python -m pytest backend/tests -q`，全绿。

- [ ] **Step 3: 跑前端检查** — `npm --prefix frontend run typecheck`；`node frontend/e2e/vocab.mjs`（带 `KY_USER` / `KY_PASS` 环境变量）；`node frontend/e2e/smoke.mjs` 确认旧流程未回归。

- [ ] **Step 4: 浏览器实测** — 桌面与手机宽度各走一遍：词卡翻面、三段发音、评分、批次续做、收藏、问 AI、默写判分、作文整篇播放；截图汇报。

- [ ] **Step 5: 进度口径核对** — 打开进度页，确认 204 卡数增加约 1650 张、记与听两条曲线分母一致。

- [ ] **Step 6: 汇报并等确认提交** — `git commit -m "test(e2e): cover vocabulary and essay review flow"`。
