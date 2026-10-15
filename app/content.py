import json
import pathlib
from functools import lru_cache

from app.config import get_settings


class ContentMissing(Exception):
    pass


@lru_cache
def load_content() -> dict:
    p = pathlib.Path(get_settings().content_dir) / "content.json"
    if not p.exists():
        raise ContentMissing(str(p))
    return json.loads(p.read_text(encoding="utf-8"))


def reset_cache() -> None:
    load_content.cache_clear()


def iter_chapters(content: dict):
    for subj in content.get("subjects", []):
        for chap in subj.get("chapters", []):
            yield subj, chap


def find_quiz(content: dict, quiz_id: str):
    for subj, chap in iter_chapters(content):
        for q in chap.get("quiz", []):
            if q["id"] == quiz_id:
                return subj, chap, q
    return None


def find_card(content: dict, card_id: str):
    for subj, chap in iter_chapters(content):
        for card in chap.get("cards", []):
            if card["id"] == card_id:
                return subj, chap, card
    return None


def quiz_chapter_map(content: dict) -> dict:
    out = {}
    for _, chap in iter_chapters(content):
        for q in chap.get("quiz", []):
            out[q["id"]] = chap["id"]
    return out


def find_point(content: dict, point_id: str):
    for subj, chap in iter_chapters(content):
        for p in chap.get("points", []):
            if p["id"] == point_id:
                return subj, chap, p
    return None


def point_tier_map(content: dict) -> dict:
    """考点 → 所属章节梯队（单元级调度的 K 由它决定）。"""
    out = {}
    for _, chap in iter_chapters(content):
        tier = chap.get("tier", 3)
        for p in chap.get("points", []):
            out[p["id"]] = tier
    return out


def card_tier_map(content: dict) -> dict:
    """背题卡 → 所属章节梯队（卡片挂在章级，不在考点下）。"""
    out = {}
    for _, chap in iter_chapters(content):
        tier = chap.get("tier", 3)
        for c in chap.get("cards", []):
            out[c["id"]] = tier
    return out
