# 部署与运维

> 面向：在 Linux 服务器（宝塔面板）上自行部署本应用的人。
> 本仓库是**单人自用**应用，没有多用户、没有鉴权体系之外的权限模型。

---

## 一、架构

```
浏览器
  │  https/http
  ▼
nginx (宝塔站点 kaoyan.bitqai.com)
  ├── /api/*  ──► 127.0.0.1:8000   FastAPI（uvicorn，systemd: kaoyan-backend）
  └── /*      ──► 127.0.0.1:3000   Next.js（next start，systemd: kaoyan-frontend）
                                        │
                                        ▼
                                 SQLite: data/ky.db
```

- 登录由**应用自身**负责（`/login`），nginx 不做基础认证。
- AI 问答走 SSE，nginx 必须 `proxy_buffering off`，否则回答会「全部生成完才一次性出现」。

---

## 二、前置条件

| 项 | 要求 | 检查命令 |
|---|---|---|
| Python | **3.10+**（代码用了 `X \| None` 语法） | `python3 -V` |
| Node.js | **18+**（Next 14 要求） | `node -v` |
| nginx | 宝塔自带即可 | — |
| 磁盘 | 应用 + 依赖约 300MB，数据库 10–30MB | — |

服务器上要能访问 npm 与 PyPI（脚本已默认使用国内镜像）。

---

## 三、首次部署

```bash
# 1. 拉代码到站点目录
git clone https://github.com/BitQAI/kaoyan-system.git /www/wwwroot/kaoyan.bitqai.com
cd /www/wwwroot/kaoyan.bitqai.com

# 2. 配置密钥（不入库）
cp backend/.env.example .env
chmod 600 .env
#   编辑 .env，至少填 DEEPSEEK_API_KEY；opencode 通道可选

# 3. 一键安装（建库、导入元数据、构建前端、装 systemd 与 nginx）
bash deploy/install_server.sh
```

脚本结束时会打印：

```
登录账号：kaoyan    密码：xxxxxxxx
```

**这行密码只出现一次**，请立即记下。

> 站点目录已有内容也可以：脚本只写入 `backend/ frontend/ data/` 与 nginx 配置，
> nginx 配置会先备份成 `kaoyan.bitqai.com.conf.bak.<时间戳>`。

---

## 四、日常更新

```bash
cd /www/wwwroot/kaoyan.bitqai.com
git pull
bash deploy/install_server.sh
```

脚本是幂等的：重复执行只会做「装依赖 → 迁移 → 重新导入元数据 → 重建前端 → 重启服务」。

**有数据库结构变更时**（`backend/migrations/versions/` 新增文件），脚本里的 `alembic upgrade head` 会自动升级；
升级前建议先备份数据库：

```bash
cp data/ky.db data/ky.db.bak.$(date +%F)
```

---

## 五、登录与密码

| 场景 | 做法 |
|---|---|
| 忘记密码 | 面板终端执行下面这段，会重置为随机新密码并打印 |
| 想固定密码 | 在 `.env` 写 `KY_AUTH_USER=xxx` / `KY_AUTH_PASS=yyy`，**删掉数据库里的 auth 记录**后重跑脚本 |

```bash
cd /www/wwwroot/kaoyan.bitqai.com/backend
.venv/bin/python - <<'PY'
from app import auth, db, config
conn = db.connect()
conn.execute("DELETE FROM settings WHERE key='auth'")
conn.commit()
print(auth.ensure_credentials(conn))
PY
```

登录态是 HMAC 签名令牌：勾「记住我」30 天，否则 12 小时；**改密会让所有已发令牌立即失效**。

---

## 六、备份

需要备份的**只有** `data/ky.db`（学习进度、收藏、问答历史都在里面）。
代码与元数据都在 git 里，不必备份。

```bash
# 每天 03:17 备份，保留 7 天
crontab -e
17 3 * * * cp /www/wwwroot/kaoyan.bitqai.com/data/ky.db /root/ky-backup/ky.$(date +\%F).db && find /root/ky-backup -name 'ky.*.db' -mtime +7 -delete
```

恢复：停服务 → 用备份覆盖 `data/ky.db` → 起服务。

---

## 七、日志与排查

```bash
systemctl status kaoyan-backend kaoyan-frontend
journalctl -u kaoyan-backend -n 100 --no-pager
journalctl -u kaoyan-frontend -n 100 --no-pager
curl -s localhost:8000/api/health     # {"ok":true,"points":538,"ai_configured":true,...}
```

### 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 页面白屏 / 报 `Cannot find module './xxx.js'` | 在 dev server 运行时跑了 `npm run build`，构建产物覆盖了 dev 的 `.next` | 重启前端服务；本地开发时不要在 `next dev` 期间跑 build |
| AI 回答一次性全部出现、不逐字 | nginx 缓冲了 SSE | 确认 `/api/` 段有 `proxy_buffering off;` 与 `proxy_read_timeout 120s;` |
| AI 报「未配置密钥」 | 根目录没有 `.env` 或没有 `DEEPSEEK_API_KEY` | 补齐 `.env` 后 `systemctl restart kaoyan-backend` |
| `alembic check` 报漂移 | 手工改过库 | 以迁移为准：备份后 `alembic upgrade head`，再核对 `alembic check` |
| 元数据更新后页面没变 | 只 pull 了代码，没重跑导入 | `bash deploy/install_server.sh`（会重新导入） |
| 朗读没声音 | 系统无中文语音包 / 浏览器策略 | 换 Chrome；确认系统已装中文 TTS 语音 |
| iOS 锁屏后朗读中断 | Safari 会停止后台 `speechSynthesis` | 网页层无法规避，需改为预生成音频方案 |
| 域名打不开但 IP 可以 | 未备案 / DNS 未指向 | 先用 `http://服务器IP` 访问；备案后再配域名 |

---

## 八、目录说明

```
backend/          FastAPI 源码、迁移、导入脚本、.venv（本地生成）
frontend/         Next.js 源码与 .next 构建产物（本地生成）
data/ky.db        运行时数据库（唯一需要备份的东西）
deploy/           nginx 配置模板、systemd 单元、安装脚本
知识点元数据/      只读数据源，导入后不改
.env              LLM 密钥与可选配置（不入库）
```

**不要提交**：`.env`、`data/`、`.next/`、`node_modules/`、`backend/.venv/`（`.gitignore` 已覆盖）。

---

## 九、回滚

```bash
cd /www/wwwroot/kaoyan.bitqai.com
git log --oneline -10          # 找到上一个可用版本
git checkout <commit>
bash deploy/install_server.sh
```

回滚后若数据库已升级，需要用升级前的备份恢复 `data/ky.db`（迁移不会自动降级）。
确认没问题后再 `git checkout main`。

---

## 十、安全须知

- 公网暴露时至少保留应用内登录；`/api` 除 `/api/health` 与 `/api/auth/login` 外都需要令牌。
- 单账号模型：知道密码的人可以读写你的全部学习数据与 AI 额度。
- `.env` 里是真实的 LLM key，权限 600、不入库、不贴日志。
- 建议只在 80/443 暴露 nginx，`8000` 与 `3000` 只监听 `127.0.0.1`（安装脚本已如此配置）。
