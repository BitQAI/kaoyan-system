# 考研学习应用

538 个知识点 / 5293 条记忆单元 / 3171 张卡片 / 538 张图示，三视图 **听 · 学 · 记**，外加一个**常驻 AI 助手**（读不懂随时问，按知识点归档历史）。

数据源是仓库里的 `知识点元数据/`（`ky-point/3.0`），应用只读它，不反写。

---

## 结构

```
backend/     FastAPI + SQLite（原生 sqlite3）+ Alembic
frontend/    Next.js 14 App Router + React 18 + TypeScript
data/        运行时数据库 ky.db（git 忽略）
deploy/      nginx + systemd
知识点元数据/ 元数据上游（只读）
```

## 首次启动

```bash
# 1. 依赖
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend install

# 2. 密钥（从 backend/.env.example 复制，填 LLM 的 key）
cp backend/.env.example .env
chmod 600 .env

# 3. 建库并导入元数据
backend/.venv/bin/python backend/scripts/import_meta.py

# 4. 起服务（两个终端）
backend/.venv/bin/uvicorn app.main:app --port 8000 --app-dir backend
npm --prefix frontend run dev
```

打开 <http://localhost:3000>，用首次初始化时打印的账号密码登录（默认账号 `kaoyan`，密码随机生成，记在服务端 `settings` 表；忘记可重跑导入或设 `KY_AUTH_PASS` 后重建凭据）。

手机同 WiFi 访问：后端加 `--host 0.0.0.0`，前端 `npm --prefix frontend run dev -- -H 0.0.0.0`，用电脑局域网 IP 打开。

## 常用命令

| 目的 | 命令 |
|---|---|
| 元数据改动后重新导入 | `backend/.venv/bin/python backend/scripts/import_meta.py` |
| 后端测试 | `backend/.venv/bin/python -m pytest backend/tests -q` |
| 前端类型检查 | `npm --prefix frontend run typecheck` |
| 前端生产构建 | `npm --prefix frontend run build` |
| e2e 冒烟（需先起前后端） | `KY_USER=kaoyan KY_PASS=<密码> node frontend/e2e/smoke.mjs` |
| 迁移一致性 | `cd backend && .venv/bin/alembic check` |

## 约定

- **元数据只读**：只改 `知识点元数据/subjects/<sid>.md`，`<sid>.json` 由 `build.py` 生成。
- **模型与迁移同一次提交**：改 `backend/app/models.py` 必须附带 `backend/migrations/versions/` 里的迁移。
- **FTS5 用 trigram**：`unicode61` 对中文会把整句当一个 token，检索直接失效。
- **SVG 出口净化**：`app/sanitize.py` 白名单，前端拿到的永远是干净的。
- **LLM 故障不阻塞**：没配 key 或调用失败时给可读提示，看、记、听照常可用。

## 文档

- 设计规格：`docs/specs/2026-10-28-考研应用与AI助手设计.md`
- 实施计划：`docs/plans/2026-10-28-考研应用与AI助手-plan.md`
- 元数据：`知识点元数据/README.md`、`字段字典.md`、`UI展示规范.md`
