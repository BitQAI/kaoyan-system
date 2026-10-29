#!/usr/bin/env bash
# 服务器端安装/更新脚本（在仓库根目录执行，git pull 之后跑一次即可）
#   用法：bash deploy/install_server.sh
#   前提：代码已 clone/pull 到站点目录；Node 18+、Python 3.10+ 已装；仓库根有 .env
set -euo pipefail

SITE="${SITE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$SITE"
log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m!! %s\033[0m\n' "$*" >&2; exit 1; }

# ---------- 0. 环境检查 ----------
log "检查运行环境（$SITE）"
python3 - <<'EOF' || die "需要 Python 3.10+，请在面板安装 Python 3.11"
import sys
if sys.version_info < (3, 10):
    sys.exit(1)
print("python", sys.version.split()[0])
EOF

command -v node >/dev/null 2>&1 || die "未安装 Node.js，请先在面板「软件商店」安装 Node 18+"
node -e 'const v=process.versions.node.split(".").map(Number);
         if (v[0] < 18) { console.error("Node 版本过低：" + process.version); process.exit(1) }
         console.log("node " + process.version)'

[ -f "$SITE/.env" ] || die "缺少 $SITE/.env（LLM 密钥），从 backend/.env.example 复制一份填好"
chmod 600 "$SITE/.env"
[ -f "$SITE/知识点元数据/subjects/812/812.json" ] || die "缺少 知识点元数据/，检查仓库是否完整"

# ---------- 1. 后端 ----------
log "安装后端依赖"
cd "$SITE/backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
.venv/bin/pip install -q -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

log "建表并导入元数据"
.venv/bin/alembic upgrade head
.venv/bin/python scripts/import_meta.py

log "初始化登录账号"
CREDS=$(.venv/bin/python - <<'PY'
from app import auth, db
created = auth.ensure_credentials(db.connect())
print(f"{created['user']} {created['password']}" if created else "")
PY
)

# ---------- 2. 前端（每次更新都要重新构建） ----------
log "构建前端"
cd "$SITE/frontend"
if [ -f package-lock.json ]; then
  npm ci --registry=https://registry.npmmirror.com --no-audit --no-fund
else
  npm install --registry=https://registry.npmmirror.com --no-audit --no-fund
fi
npm run build

# ---------- 3. systemd ----------
log "安装并启动服务"
cat >/etc/systemd/system/kaoyan-backend.service <<UNIT
[Unit]
Description=Kaoyan backend (FastAPI)
After=network.target

[Service]
Type=simple
WorkingDirectory=$SITE/backend
ExecStart=$SITE/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

cat >/etc/systemd/system/kaoyan-frontend.service <<UNIT
[Unit]
Description=Kaoyan frontend (Next.js)
After=network.target kaoyan-backend.service

[Service]
Type=simple
WorkingDirectory=$SITE/frontend
Environment=NODE_ENV=production
ExecStart=$(command -v npm) run start -- --port 3000 --hostname 127.0.0.1
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable kaoyan-backend kaoyan-frontend >/dev/null 2>&1 || true
systemctl restart kaoyan-backend
systemctl restart kaoyan-frontend
sleep 3

# ---------- 4. nginx ----------
log "配置 nginx"
CONF=/www/server/panel/vhost/nginx/kaoyan.bitqai.com.conf
if [ -d /www/server/panel/vhost/nginx ]; then
  [ -f "$CONF" ] && cp "$CONF" "${CONF}.bak.$(date +%s)"
  cat >"$CONF" <<'NGINX'
# 由 deploy/install_server.sh 生成；在宝塔里改伪静态/SSL 后再跑本脚本会被覆盖
# 登录由应用自身负责（/login），nginx 不做基础认证
server {
    listen 80;
    server_name kaoyan.bitqai.com;

    client_max_body_size 2m;

    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Connection "";

        # SSE 必需：不缓冲、长超时，否则 AI 回答会等全部生成完才一次性出现
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
NGINX
  nginx -t && (systemctl reload nginx 2>/dev/null || nginx -s reload)
else
  echo "未发现宝塔 nginx 目录，跳过（请自行配置反代：/api → 127.0.0.1:8000，/ → 127.0.0.1:3000）"
fi

# ---------- 5. 自检 ----------
log "自检"
curl -fsS --max-time 10 http://127.0.0.1:8000/api/health || die "后端没起来：journalctl -u kaoyan-backend -n 50"
echo
curl -fsS -o /dev/null -w "frontend http=%{http_code}\n" --max-time 10 http://127.0.0.1:3000/ \
  || die "前端没起来：journalctl -u kaoyan-frontend -n 50"

log "完成"
echo "访问：http://kaoyan.bitqai.com（本机 http://127.0.0.1:3000）"
if [ -n "$CREDS" ]; then
  set -- $CREDS
  echo "登录账号：$1    密码：$2"
  echo "（只在首次初始化时打印，请立即记下）"
else
  echo "登录账号已存在（沿用之前设置）"
fi
