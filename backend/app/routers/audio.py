"""音频只读接口：把已生成的卡片 MP3 交给「听」页。

音频由 gen_card_audio.py 离线生成后上传，缺失时返回 404，前端据此回退浏览器 TTS。
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app import config, db

router = APIRouter(prefix="/api", tags=["audio"])

#: 卡片 id 形如 c8120001-1；白名单同时挡住路径穿越
CARD_ID = re.compile(r"^c[0-9]{6,8}-[0-9]{1,2}$")


@router.get("/audio/{card_id}")
def card_audio(card_id: str, conn=Depends(db.get_db)):
    if not CARD_ID.match(card_id):
        raise HTTPException(404, "无音频")
    row = conn.execute(
        "SELECT p.subject_id FROM card c JOIN point p ON p.id = c.point_id "
        "WHERE c.card_id = ?", (card_id,)).fetchone()
    if not row:
        raise HTTPException(404, "无音频")
    path = config.AUDIO_DIR / row["subject_id"] / f"{card_id}.mp3"
    if not path.is_file():
        raise HTTPException(404, "无音频")
    # 文本一改音频就会被重新生成，一周的浏览器缓存足以省掉重复下载
    return FileResponse(path, media_type="audio/mpeg",
                        headers={"Cache-Control": "private, max-age=604800"})
