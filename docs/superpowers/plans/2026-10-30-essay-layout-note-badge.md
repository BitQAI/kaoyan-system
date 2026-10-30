# 实施计划：作文版式、答案排版与笔记入口精简

依据：[spec](../specs/2026-10-30-essay-layout-note-badge-design.md)

## Global Constraints

- 元数据只改源文件 `204-essays.jsonl`，`204-essay-points.json` / `204.json` 由脚本生成。
- 不改后端表结构、不改迁移；`data/` 不入库。
- `.tsx` 硬上限 500 行；新增组件各控制在 150 行内。
- 提交前需用户确认；commit message 用英文。

## Task 1 范文扩写与数据校验

文件：

- `知识点元数据/subjects/204/204-essays.jsonl`
- `知识点元数据/scripts/essay_build.py`

- [x] 12 篇范文各段末尾追加句子，既有句子不改（`blanks` 挖空位置不变）。
- [x] 落款/日期保持在段末：追加句插在 `Yours sincerely` / 中文署名 / 通知日期之前。
- [x] 中文译文同步补齐。
- [x] `essay_build.py` 增加 `MIN_WORDS`（204-08 = 100，204-09 = 150），构建时校验，不达标直接失败。
- [x] 词数结果：小作文 102–115，大作文 151–159。

## Task 2 作文 payload

文件：

- `知识点元数据/scripts/essay_build.py`

- [x] 新增 `_essay_payload()`：`type/format/exam/title/scope/paragraphs(role,en,cn,keys)/word_count/(min_words|index,total)`。
- [x] 模板卡 `scope=full`，回译/默写卡 `scope=paragraph`；句型卡不挂 payload。
- [x] `format` 识别：`Dear` 开头 → letter，`Notice`/通知 → notice，其余 → chart。
- [x] 重新生成 `204-essay-points.json`、`204.json`，并导入 `data/ky.db`、`data/ky-verify.db`。

## Task 3 作文版式组件

文件：

- `frontend/src/components/EssayFace.tsx`（新增）
- `frontend/src/lib/types.ts`
- `frontend/src/lib/render.ts`

- [x] `EssayPayload` / `isEssayPayload` / `isWordPayload` 类型守卫。
- [x] 信件拆称呼与落款（右对齐），通知拆标题与日期，图表按段渲染。
- [x] 好词好句 `highlightKeys()`：拆分 `keys` 片段并首次出现处 `<mark>`。
- [x] 词数徽标：达标绿色、不足琥珀；单段卡显示「第 i/n 段」。
- [x] 听、记两个模块接入 EssayFace；`wordPayloadOf` 不再把作文 payload 当词卡。

## Task 4 通用答案解析排版

文件：

- `frontend/src/lib/render.ts`
- `frontend/src/components/MemoView.tsx`
- `frontend/src/app/globals.css`

- [x] `paragraphs()` 先按换行切块，再在块内每 2 句成段（英文段落保持整段）。
- [x] 「记」的解析改用 `paragraphs()` 渲染，不再是一整段纯文本。

## Task 5 笔记入口与冗余按钮

文件：

- `frontend/src/components/NoteDialog.tsx`（新增，替代 `CardNote.tsx`）
- `frontend/src/components/ListenView.tsx`
- `frontend/src/components/MemoView.tsx`
- `frontend/src/components/WordFace.tsx`
- `frontend/src/app/globals.css`

- [x] 顶部工具条「笔记」按钮：有笔记高亮「笔记 ·」，点击打开弹窗。
- [x] 弹窗：textarea + 保存 + 关闭；关闭时若有改动自动保存；⌘/Ctrl+Enter 保存；空内容即删除。
- [x] 删除卡片正文的笔记区块与占位。
- [x] 去掉「记」翻面后的「读释义」。

## Task 6 验证

- [x] `essay_build.py` 校验通过（12 篇全部达标），`vocab_assemble.py` 重建成功。
- [x] 重新导入两个库，卡片 payload 正确。
- [x] 浏览器：信件称呼/落款/三段、通知标题与日期、图表三段、好词好句高亮、词数徽标。
- [x] 浏览器：笔记按钮无笔记不高亮、有笔记高亮，弹窗回显与保存；听/记共享。
- [x] 浏览器：315 解析分成两段、812 答案分段；翻面后无「读释义」。
- [x] `pytest` 127 passed、`tsc --noEmit` 通过、`next build` 通过。
- [ ] 用户确认后提交。

---

## 补充任务（同日第二轮）

- [x] `essay_build.py`：回译/默写/句型卡标记 `memo_hidden`；整篇卡挂 `figure`。
- [x] `service.custom_cards` / `custom_listen` 过滤 `memo_hidden=1` 的卡（听、记都是 48 → 6）。
- [x] 新增 `scripts/essay_figures.py` 与 `204-essay-figures.json`（6 图表 + 6 情景）。
- [x] `EssayPayload.figure` 类型与 EssayFace 图片区、图注样式。
- [x] 新增 `RateWheel.tsx` 与滚轮样式；`ListenView` 播放条改为按钮入口。
- [x] 移除「我的 → 账号」的朗读语速滑杆。
- [x] 重建数据并导入两个库；`pytest` 127 passed、`tsc`、`next build` 通过。
- [x] 浏览器实测：听、记均 1/6；图与图注正常；语速滚轮 1.50→2.00 生效并持久化。
