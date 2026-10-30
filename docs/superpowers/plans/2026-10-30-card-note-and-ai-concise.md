# 实施计划：听记卡片笔记 + AI 助手回复收敛

依据：[spec](../specs/2026-10-30-card-note-and-ai-concise-design.md)

## Global Constraints

- 模型与迁移同一次提交：`models.py` 改动必须附 `0008_add_card_note.py`。
- `.tsx` / `.py` 硬上限 500 行，新增组件控制在 150 行内。
- 不新增依赖；样式只用现有 CSS 变量。
- 每个 Task 完成后向用户确认再 commit；commit message 用英文 `type(scope): description`。
- 所有验证命令必须实际执行并附输出，禁止声称未跑过的测试通过。

## Task 1 后端：card_note 表、接口与队列字段

文件：

- `backend/app/models.py`
- `backend/migrations/versions/0008_add_card_note.py`
- `backend/app/service.py`
- `backend/app/routers/notes.py`（新增）
- `backend/app/main.py`
- `backend/tests/test_notes.py`（新增）

接口定义：

```python
# service.py
NOTE_MAX_LEN = 2000

def get_note(conn, card_id: str) -> dict | None
def set_note(conn, card_id: str, content: str) -> dict | None  # 卡不存在返回 None
```

```python
# routers/notes.py
class NoteIn(BaseModel):
    card_id: str
    content: str

@router.get("")   -> {"card_id": str, "content": str, "updated_at": str | None}
@router.put("")   -> {"ok": True, "content": str}
```

步骤：

- [ ] `models.py` 新增 `card_note` 表（`card_id` PK、`content`、`created_at`、`updated_at`），加入 `ALL_TABLES`。
- [ ] 新建 `0008_add_card_note.py`，`down_revision = "0007"`，`upgrade` 建表、`downgrade` 删表。
- [ ] `service.py`：实现 `get_note` / `set_note`（`content.strip()` 为空时删除；超长抛 `ValueError`；卡不存在返回 `None`）。
- [ ] `custom_cards` 与 `custom_listen` 加 `LEFT JOIN card_note cn ON cn.card_id = c.card_id`，SELECT `cn.content AS note`，返回项加 `"note": r["note"] or ""`。不改排序与过滤。
- [ ] 新增 `routers/notes.py`：`GET` 返回空串而非 404；`PUT` 校验长度（400）与卡存在（404）。
- [ ] `main.py` 注册 notes 路由（与现有 router 并列）。
- [ ] `tests/test_notes.py`：保存、覆盖、清空删除、超长 400、未知卡 404、`custom_cards` / `custom_listen` 带 `note`。

验证：

```bash
cd backend && .venv/bin/alembic check
cd backend && .venv/bin/alembic upgrade head
backend/.venv/bin/python -m pytest backend/tests/test_notes.py -q
```

## Task 2 前端：CardNote 组件 + 听/记接入

文件：

- `frontend/src/components/CardNote.tsx`（新增）
- `frontend/src/components/ListenView.tsx`
- `frontend/src/components/MemoView.tsx`
- `frontend/src/lib/types.ts`
- `frontend/src/app/listen.css`
- `frontend/src/app/memo.css`

接口定义：

```ts
// CardNote.tsx
export default function CardNote(props: {
  cardId: string;
  note?: string;
  onSaved: (text: string) => void;
}): JSX.Element;
```

步骤：

- [ ] `types.ts`：`Card` 与 `ListenItem` 增加 `note?: string`。
- [ ] `CardNote.tsx`：
  - 无笔记显示按钮「记下我的理解」；有笔记显示正文 + 「编辑」。
  - 编辑态 textarea + 保存/取消；`⌘/Ctrl+Enter` 保存。
  - 失焦时内容变化则自动保存；保存中禁用按钮。
  - 保存成功展示「已保存」，2 秒后消失；失败展示「保存失败，请重试」。
  - 切换 `cardId` 时重置为只读展示。
- [ ] `ListenView.tsx`：在「评分要点」之后、播放器之前渲染 `<CardNote cardId={item.card_id} note={item.note} onSaved={...} />`；回调更新 `items` 中当前项的 `note`。
- [ ] `MemoView.tsx`：翻面内容块之后、`CardMeta` 之前渲染 `CardNote`；`onSaved` 更新 `cards[index].note`。
- [ ] `MemoView` 卡片点击翻面忽略列表加入 `textarea, .card-note`；`onPointerDown` 在 `.card-note` 内不启动滑动评分。
- [ ] `listen.css` 与 `memo.css` 增加 `card-note` 样式（标题层级、正文 `pre-wrap`、编辑态聚焦描边、提示文字）。
- [ ] `npm --prefix frontend run typecheck`。

## Task 3 AI：提示词重写与 max_tokens

文件：

- `backend/app/ai.py`

步骤：

- [ ] 重写 `SYSTEM_PROMPT`：结论一行（≤30 字，加粗）+ 最多 3 个要点（每点 ≤50 字）+ 可选 `考场：` 一行；全文 150–250 字；明确「展开/细讲」时才到 500 字。
- [ ] 写入禁止项：复述问题、开场白、结尾客套、小标题、表格、emoji、同义反复。
- [ ] 资料补充用「补充：」单独一行；保留事实纪律四条。
- [ ] `stream_answer` 的请求增加 `max_tokens`：默认 800；聊天供应商为 opencode 时取 `max(800, config.OPENCODE_MIN_MAX_TOKENS)`。
- [ ] `backend/.venv/bin/python -m pytest backend/tests -q` 全绿。

## Task 4 AI 面板：要点排版与追问入口

文件：

- `frontend/src/app/ai.css`
- `frontend/src/components/AiChat.tsx`

步骤：

- [ ] `.ai-md`：首段作为结论行（加粗、13.8px、左侧 `--accent` 2px 竖线、内边距）；列表紧凑（`li + li` 6px、行距 1.62）；标题统一 13.5px、上下边距收紧。
- [ ] `AiChat.tsx`：最后一条 AI 回答、非流式、且内容非空时，下方显示追问 chip：`展开讲讲`、`举个例子`、`怎么考`，点击调用 `ask(chip)`。
- [ ] 追问 chip 样式（与 `.ai-suggest` 一致的小圆角按钮），移动端可换行。
- [ ] `npm --prefix frontend run typecheck`。

## Task 5 联合验证

- [ ] `cd backend && .venv/bin/alembic check`（clean）。
- [ ] `cd backend && .venv/bin/alembic upgrade head`。
- [ ] `backend/.venv/bin/python -m pytest backend/tests -q`。
- [ ] `npm --prefix frontend run typecheck`。
- [ ] `npm --prefix frontend run build`。
- [ ] 起前后端，浏览器自验：
  - 听视图写笔记 → 记视图同卡翻面可见 → 返回听视图仍在。
  - 笔记内空格不翻面、1/2/3 不评分、⌘+Enter 保存。
  - 清空笔记后展示恢复为「记下我的理解」。
  - AI 三类问题回答 ≤250 字、首句为结论；点「展开讲讲」后 ≤500 字。
  - 375px 宽度无横向溢出。
- [ ] 向用户汇报实测结果与差异，确认后按 Task 分别提交。
