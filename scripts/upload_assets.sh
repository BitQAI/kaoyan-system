#!/usr/bin/env bash
# 本机 → 服务器：上传音频与教材裁图（git 之外的两样内容资产）
# 用法：bash scripts/upload_assets.sh root@你的服务器IP [远端项目路径] [--force-audio]
#   --force-audio：覆盖已存在的同名音频（音频重新生成后必须加，否则服务器保留旧文件）
set -euo pipefail

HOST="${1:?用法: bash scripts/upload_assets.sh root@服务器IP [远端路径] [--force-audio]}"
REMOTE_DIR="${2:-/www/wwwroot/kaoyan-system}"
FORCE_AUDIO="${3:-}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

AUDIO_OPTS=(-avz --progress)
if [ "$FORCE_AUDIO" != "--force-audio" ]; then
  AUDIO_OPTS+=(--ignore-existing)
  echo "提示：默认跳过已存在音频；本章级音频为新重生成版本时请加 --force-audio 覆盖。"
fi

echo "→ 上传音频 $(ls "$HERE/content/audio"/*.mp3 2>/dev/null | wc -l | tr -d ' ') 段 ..."
rsync "${AUDIO_OPTS[@]}" \
  "$HERE/content/audio/" "$HOST:$REMOTE_DIR/content/audio/"

if [ -d "$HERE/content/media-private" ] && [ "$(ls -A "$HERE/content/media-private" 2>/dev/null)" ]; then
  echo "→ 上传教材裁图 ..."
  rsync -avz --progress \
    "$HERE/content/media-private/" "$HOST:$REMOTE_DIR/content/media-private/"
fi

echo "→ 完成。服务器上执行：docker compose restart app"
