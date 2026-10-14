#!/usr/bin/env bash
# 本机 → 服务器：上传音频与教材裁图（git 之外的两样内容资产）
# 用法：bash scripts/upload_assets.sh root@你的服务器IP [远端项目路径]
set -euo pipefail

HOST="${1:?用法: bash scripts/upload_assets.sh root@服务器IP [远端路径]}"
REMOTE_DIR="${2:-/www/wwwroot/kaoyan-system}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

echo "→ 上传音频 $(ls "$HERE/content/audio"/*.mp3 2>/dev/null | wc -l | tr -d ' ') 段 ..."
rsync -avz --progress --ignore-existing \
  "$HERE/content/audio/" "$HOST:$REMOTE_DIR/content/audio/"

if [ -d "$HERE/content/media-private" ] && [ "$(ls -A "$HERE/content/media-private" 2>/dev/null)" ]; then
  echo "→ 上传教材裁图 ..."
  rsync -avz --progress \
    "$HERE/content/media-private/" "$HOST:$REMOTE_DIR/content/media-private/"
fi

echo "→ 完成。服务器上执行：docker compose restart app"
