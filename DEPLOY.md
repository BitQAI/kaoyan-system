# 部署指南（宝塔 + Docker · kaoyan.bitqai.com）

目标：把本仓库以 **Docker** 方式部署到云服务器，浏览器（手机/电脑）访问 `https://kaoyan.bitqai.com`。
架构：宝塔 Nginx（HTTPS + 静态直出）→ 反代 127.0.0.1:8000 → 容器内 FastAPI → SQLite（挂载卷）。

---

## 0. 前置

- 云服务器已装宝塔面板；在宝塔「软件商店」安装 **Docker 管理器**
- 域名 `kaoyan.bitqai.com` 已解析到服务器 IP（A 记录）
- 服务器可访问：`opencode.ai`（AI 对话）与 `*.aliyuncs.com`（TTS/兜底对话）

## 1. 拉代码与配置

```bash
cd /www/wwwroot
git clone https://github.com/BitQAI/kaoyan-system.git
cd kaoyan-system
cp .env.example .env && chmod 600 .env
```
`.env` 需填：
- `KY_PASSWORD_HASH`：本机生成后粘贴（`python3 -c "import hashlib,os;print('scrypt$16384$8$1$'+os.urandom(16).hex())"` 不行——用仓库脚本生成：）
  ```bash
  docker run --rm -v $PWD:/app -w /app python:3.11-slim \
    python -c "import sys;sys.path.insert(0,'.');from app.auth import hash_password;print(hash_password('你的登录密码'))"
  ```
- `KY_SESSION_SECRET`：`openssl rand -hex 24`
- `AI_PROVIDER=opencode` + `OPENCODE_GO_KEY`（本机 `~/.config/kaoyan/bailian.env` 里那把）
- `BAILIAN_KEY`（生成音频与兜底对话用）

服务器连通性自测（Docker 外即可）：
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://opencode.ai/zen/go/v1/models \
  -H "Authorization: Bearer $OPENCODE_GO_KEY"
# 200 → 保持 opencode；超时 → .env 改 AI_PROVIDER=bailian
```

## 2. 启动

```bash
mkdir -p data content/audio content/media-private
docker compose build
docker compose up -d
curl -s localhost:8000/api/health   # → {"ok":true}
```

## 3. 生成音频（容器内，断点续跑）

```bash
docker compose run --rm app python scripts/gen_audio.py --engine qwen_audio
# ~450 段约 1-2 小时；中断后重跑自动跳过已生成
# 也可 --subject 812 按科分批
docker compose restart app   # 音频回填了 content.json，重启让应用重新加载
```

（可选）本机已有音频时直接上传：`rsync -avz content/audio/ root@服务器:/www/wwwroot/kaoyan-system/content/audio/`
（可选）教材裁图：本机 `content/media-private/` → 服务器同路径 `content/media-private/`（该目录不入 git）

## 4. Nginx（宝塔站点 conf）

```nginx
location /audio  { alias /www/wwwroot/kaoyan-system/content/audio; }
location /media  { alias /www/wwwroot/kaoyan-system/content/media; }
location /media-private { alias /www/wwwroot/kaoyan-system/content/media-private; }

location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_buffering off;          # SSE 流式必需
    proxy_read_timeout 300s;
}
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
}
```
站点 SSL → Let's Encrypt → 强制 HTTPS。

## 5. 备份（宝塔计划任务，每日 02:00）

```bash
cd /www/wwwroot/kaoyan-system && tar czf /www/backup/kaoyan-$(date +%F).tar.gz data/ .env
find /www/backup -name "kaoyan-*.tar.gz" -mtime +7 -delete
```
恢复：解压覆盖 `data/` 与 `.env` → `docker compose restart app`。

## 6. 上线验收清单

- [ ] https://kaoyan.bitqai.com 登录一次后 90 天免登
- [ ] 听：队列连播、锁屏/后台播放、±15s、倍速、断点续听正确
- [ ] 看：公式（KaTeX）、结构式、图表、教材裁图显示正常
- [ ] 测：判分、错题本连对两次出本
- [ ] AI：流式回答 1-3 秒出首字；断流显示"已中断"
- [ ] 电脑同进度；备份任务执行成功

## 7. 日常维护

- 更新：`git pull && docker compose build && docker compose up -d`（内容/前端改动无需迁移）
- 补音频：`docker compose run --rm app python scripts/gen_audio.py --subject 315 --engine qwen_audio`
- 新增教材裁图：编辑 `content/figures_textbook.json` → 本机 `python scripts/crop_textbook.py --config content/figures_textbook.json --attach` → 上传 `content/media-private/`
- 查日志：`docker compose logs -f app`
- 语音引擎：`qwen_audio`（百炼 qwen-audio-3.1-tts-next，男声 longanyang，默认）/ `bailian`（qwen3-tts-flash，需充值）/ `edge`（微软免费，部分网络不可用）
