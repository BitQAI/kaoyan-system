# 听记卡片笔记 + AI 助手回复收敛

日期：2026-10-30
状态：已确认方向，待实施

## 1. 背景

两个问题都来自真实使用：

1. **听/记时没有地方记自己的理解。** 听到一个单词，某个例句没看懂，查明白之后没有落点；下次再听到同一张卡，看不出「我上次卡在哪、后来怎么想通的」。收藏只能标记，不能写内容。
2. **AI 助手回复又长又散。** 当前 `backend/app/ai.py` 的 SYSTEM_PROMPT 强制输出 5 个固定部分、400–800 字，还要「类比 + 因果链 + 考试落点」，在手机上一屏读不完，重点被稀释。

exa 调研（AI tutor 提示词、anti-bloat 提示词实践）的共识：**具体的长度与条目上限 + 明确的「不要写什么」+ 先给结论再展开**，比「请简洁一点」有效得多；同时建议保留一个「需要时再展开」的出口，避免为短而牺牲深度。

## 2. 目标与非目标

目标：

1. 每张卡一条笔记，**听与记共享同一条**（按 `card_id` 唯一）。在「听」卡片内和「记」翻面后的卡片内都能写、都能看到。
2. 笔记在再次遇到该卡时自动展示，不需要额外点开面板。
3. AI 助手默认回复 **结论先行、150–250 字、最多 3 个要点**；用户明确要求「展开/细讲」时才放宽到 500 字。
4. 回答的要点在手机上**排版可扫读**（结论行突出、要点为紧凑列表），并给出追问入口。

非目标：

- 不做全局笔记列表、搜索、导出（用户选择只在卡片内就地展示；后续需要再加）。
- 不做「每条例句一条笔记」（用户选择每卡一条）。
- 不改 AI 上下文组装（L1–L4）、会话归档、历史记录接口。
- 不改「记」的评分与调度逻辑。
- 不新增前端依赖。

## 3. 数据模型

新增运行时表 `card_note`：

| 列 | 类型 | 说明 |
|---|---|---|
| `card_id` | TEXT PRIMARY KEY | 卡片 id，听/记共用 |
| `content` | TEXT NOT NULL | 笔记正文，纯文本，保留换行 |
| `created_at` | TEXT NOT NULL | ISO 时间 |
| `updated_at` | TEXT NOT NULL | ISO 时间 |

与 `models.py` 同步新增，并写迁移 `0008_add_card_note.py`（同一次提交）。

## 4. API

| 方法 | 路径 | 入参 | 行为 |
|---|---|---|---|
| GET | `/api/notes?card_id=` | query | 返回 `{card_id, content, updated_at}`；无笔记时 `content` 为空串 |
| PUT | `/api/notes` | `{card_id, content}` | 保存（upsert）；`content` 去空白后为空则删除该行 |

约束：

- `content` 最长 2000 字，超出 400。
- `card_id` 不存在于 `card` 表时 404，避免无关行。
- 队列接口额外下发 `note` 字段：
  - `POST /api/queue/custom`（`memo` 与 `listen` 两种模式）
  - 通过 `LEFT JOIN card_note` 一次带回，避免逐卡请求。

## 5. 前端

### 5.1 卡片笔记组件（新文件）

`frontend/src/components/CardNote.tsx`，听、记两处复用。props：`cardId`、`note`、`onSaved(text)`。

状态与行为：

- 无笔记：一个折叠按钮「记下我的理解」（或已有内容时直接展示正文）。
- 有笔记：展示正文（`white-space: pre-wrap`），右上角「编辑」。
- 编辑态：`textarea` + 「保存」「取消」；`Ctrl/⌘ + Enter` 保存。
- 保存后回调 `onSaved`，父组件更新本地 `items/index` 数据，两视图切换后仍是新内容。
- 切换卡片时重置编辑态；失焦时若内容有变化则自动保存（幂等，空内容即删除）。
- 保存成功短暂提示「已保存」。

### 5.2 听视图 `ListenView.tsx`

- 位置：内容块之后、「评分要点」之后、播放器之前。
- 笔记不朗读、不进入分段。
- 父组件把 `item.note` 记为本地状态，保存后只更新当前 `items[idx].note`。

### 5.3 记视图 `MemoView.tsx`

- 位置：翻面后的内容块之后、`CardMeta` 之前。
- 卡片点击翻面逻辑需忽略笔记区（`closest("button, a, input, textarea, summary, .options, .card-note")`），滑动评分在笔记区按下时不启动。
- 键盘快捷键（空格翻面、1/2/3 评分）在 `textarea` 内不触发（现有判断已覆盖 `TEXTAREA`，需确认 `Ctrl/⌘+Enter` 保存冲突）。

### 5.4 样式

- `listen.css` / `memo.css` 共用一段 `card-note` 样式：与卡片内其他 block 一致的标题层级，编辑态边框用 `--line`、聚焦用 `--accent`，正文用 `--ink-2`。
- 不引入新颜色变量。

## 6. AI 助手

### 6.1 SYSTEM_PROMPT 重写（`backend/app/ai.py`）

结构：

1. 第一行直接给结论：一句人话，≤30 字，加粗。
2. 最多 3 个要点，`- ` 列表，每点 ≤50 字；只写原因、区别、怎么记这类有用信息。
3. 需要落到考试时，最后一行 `考场：……`，≤40 字；不需要就不写。
4. 全文 150–250 字；仅当用户明确说「展开 / 细讲 / 多说一点」时放宽到 500 字。
5. 明确禁止：复述问题、开场白、结尾客套、小标题、表格、emoji、同义反复。
6. 资料未覆盖的补充内容用「补充：」单独一行。
7. 保留事实纪律：资料优先、不编造考纲条款、`inferred` 说「这是推断」、不确定直说。

### 6.2 长度兜底

流式请求增加 `max_tokens`：

- 默认 800（约合 500–600 中文字符）。
- 当前聊天供应商是 opencode 时，取 `max(800, OPENCODE_MIN_MAX_TOKENS)`，避免推理模型思考占满预算返回空串。

### 6.3 UI 排版（`ai.css` + `AiChat.tsx`）

- `.ai-md` 首段作为结论行突出：加粗、略大字号、左侧一条 `--accent` 细线。
- 要点列表紧凑化：去掉默认大间距，行距收紧，`li` 之间 6px。
- 标题字号统一 13.5px，收紧上下边距（回答里即使出现小标题也不至于把版面撑散）。
- 最后一条回答下方追加追问 chip：`展开讲讲`、`举个例子`、`怎么考`，点击即发送，给短回答留出深入的口子。
- 流式输出过程中不显示追问 chip。

## 7. 影响范围

后端：

- `backend/app/models.py`（新增表 + `ALL_TABLES`）
- `backend/migrations/versions/0008_add_card_note.py`
- `backend/app/service.py`（`custom_cards` / `custom_listen` 左连接笔记；笔记读写函数）
- `backend/app/routers/notes.py`（新增）+ `backend/app/main.py`（注册路由）
- `backend/app/ai.py`（提示词 + `max_tokens`）
- `backend/tests/test_notes.py`（新增）

前端：

- `frontend/src/components/CardNote.tsx`（新增）
- `frontend/src/components/ListenView.tsx`、`MemoView.tsx`
- `frontend/src/components/AiChat.tsx`
- `frontend/src/app/listen.css`、`memo.css`、`ai.css`
- `frontend/src/lib/types.ts`（`Card.note?`、`ListenItem.note?`）

## 8. 验证

1. `cd backend && .venv/bin/alembic check` 无漂移；`alembic upgrade head` 成功。
2. `backend/.venv/bin/python -m pytest backend/tests -q` 全绿，新增笔记用例覆盖：保存、覆盖、清空即删除、超长 400、未知卡 404、队列带 `note`。
3. `npm --prefix frontend run typecheck` 与 `npm --prefix frontend run build` 通过。
4. 浏览器自验（localhost:3000）：
   - 听视图写笔记 → 切到「记」同一张卡翻面可见；再切回「听」仍在。
   - 笔记含换行、标点、英文，展示正常；清空后回到「记下我的理解」。
   - 在笔记 textarea 内按空格不翻面、按 1/2/3 不评分。
   - AI 助手用三类问题实测（概念解释 / 易混区别 / 真题怎么考），回答 150–250 字、首句为结论；追问「展开讲讲」后到 500 字以内。
5. 手机宽度（375px）下笔记与 AI 面板不溢出。

## 9. 风险

| 风险 | 处理 |
|---|---|
| 队列 SQL 改动影响现有消费方 | 只新增 `LEFT JOIN` 与一个字段，不改排序/过滤；两种模式都有测试 |
| 模型仍超字数 | 提示词给出硬上限 + `max_tokens` 兜底；验收时实测三类问题 |
| 失焦自动保存过于频繁 | 仅内容变化时写；服务端 upsert 幂等 |
| 一张卡在听/记同时打开（两个标签页） | 最后写入者生效；不做冲突合并，符合单用户场景 |
