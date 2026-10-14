# 考点解析补全 + 204 内容 实施计划

**Spec:** `docs/superpowers/specs/2026-10-14-point-notes-and-204.md`

## Task 1: 生成脚本 + 试点（先看效果再全量）

- [ ] `scripts/gen_notes.py`：
  - 复用 `app.config.get_settings()` 取 opencode 网关；非流式 POST `/chat/completions`
  - 入参：`--subject 101 --subject 315`（可多）、`--limit N`、`--force`、`--merge`、`--concurrency 3`
  - 每点位上下文：科目名 + 章节名 + 点位 text + 同章其余点位标题（截断）
  - 输出严格 JSON `{"note","exam","keywords"}`；解析失败重试 2 次
  - 逐点落盘 `content/notes/<subject>.json`；已存在且非 force 跳过（断点续跑）
- [ ] 试点：每科 2 点（101-02-01、101-22-01、315-06-01、315-04-01、812-*、204-*）→ 人工确认风格

## Task 2: 204 章节/点位构建

- [ ] 依据源 HTML §2 构建 `204-01..204-08` 八章约 50 点（text 为考点名、listen_ok:false、audio 空、has_content:true）
- [ ] 写入 content.json（脚本或直接编辑），merge 后 validate 通过
- [ ] 抽查：204 看页可进入、八章齐、无音频按钮

## Task 3: 全量生成 468+50 点

- [ ] `python scripts/gen_notes.py --all --concurrency 3`（后台，预计 30-60 分钟）
- [ ] 失败清单清零；`--merge` 写回 content.json
- [ ] 抽样每科 ≥5 点复核（note/exam/keywords 与考点匹配）

## Task 4: 校验与前端验收

- [ ] `validate_content.py` 扩展：字段存在时须为合法形状（note/exam 非空字符串、keywords 为字符串数组）
- [ ] `pytest -q` 全绿
- [ ] 浏览器：看页（标题不重复、note/exam 渲染、搜索/跳转/徽标）、204 tab（八章 + 无音频）、今日/听/测无回归

## Task 5: 提交

- [ ] `git add -A`（连同 M2/M3 未提交改动一起）→ 汇报 → 用户确认后 commit

```bash
git add -A && git commit -m "feat(content): per-point notes (note/exam/keywords), 204 English outline, tab/empty-state fixes"
```
