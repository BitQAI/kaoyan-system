#!/usr/bin/env python3
"""百炼 TTS 批量生成：spoken → 按 ≤60s/段切分 → mp3（Ethan 男声）。

用法：python scripts/gen_audio.py [--subject 812] [--voice Ethan] [--dry-run] [--sleep 0.8]
断点续跑：已存在的 mp3 跳过；失败清单写入 content/audio_failed.json。
"""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
import time

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts.normalize import split_clips  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODEL = "qwen3-tts-flash"


def load_settings():
    from app.config import get_settings

    return get_settings()


def clip_plan(content: dict, only: set | None = None) -> list[dict]:
    out = []
    for subj in content.get("subjects", []):
        if only and subj["id"] not in only:
            continue
        if not subj.get("has_content"):
            continue
        for ch in subj.get("chapters", []):
            for p in ch.get("points", []):
                if not p.get("listen_ok", True) or not p.get("spoken"):
                    continue
                clips = split_clips(p["spoken"])
                for i, text in enumerate(clips, 1):
                    cid = p["id"] if len(clips) == 1 else f"{p['id']}-p{i}"
                    out.append({"clip_id": cid, "text": text,
                                "point_id": p["id"], "subject": subj["id"]})
    return out


def synth(text: str, voice: str, settings, retries: int = 3, sleep: float = 1.0) -> bytes:
    """百炼 TTS → wav bytes。"""
    base = settings.bailian_base.rstrip("/")
    if base.endswith("/compatible-mode/v1"):
        base = base[: -len("/compatible-mode/v1")]
    url = base + "/api/v1/services/aigc/multimodal-generation/generation"
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {settings.bailian_key}",
                         "Content-Type": "application/json"},
                json={"model": MODEL, "input": {"text": text, "voice": voice}},
                timeout=120,
            )
            r.raise_for_status()
            audio_url = r.json()["output"]["audio"]["url"]
            wav = requests.get(audio_url, timeout=120)
            wav.raise_for_status()
            return wav.content
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(sleep * (attempt + 1))
    raise RuntimeError(str(last))


EDGE_VOICE = "zh-CN-YunxiNeural"   # 云希：中文男声

# 百炼 Qwen-Audio-TTS（SpeechSynthesizer 端点；tts-flash 在本工作区未开通，用 tts-next）
QWEN_AUDIO_MODEL = "qwen-audio-3.1-tts-next"
QWEN_AUDIO_VOICE = "longanyang"    # 龙安阳：中文男声
QWEN_AUDIO_PROMPT = "以考研复习讲解的语气，平静、清晰、连贯地朗读"


def synth_qwen_audio(text: str, voice: str | None, settings, retries: int = 3,
                     sleep: float = 1.0) -> bytes:
    """Qwen-Audio-TTS → mp3 bytes，voice 默认 longanyang（男声）。"""
    base = settings.bailian_base.rstrip("/")
    if base.endswith("/compatible-mode/v1"):
        base = base[: -len("/compatible-mode/v1")]
    url = base + "/api/v1/services/audio/tts/SpeechSynthesizer"
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {settings.bailian_key}",
                         "Content-Type": "application/json"},
                json={"model": QWEN_AUDIO_MODEL, "input": {
                    "text": text, "voice": voice or QWEN_AUDIO_VOICE,
                    "format": "mp3", "sample_rate": 24000,
                    "text_prompt": QWEN_AUDIO_PROMPT}},
                timeout=120,
            )
            r.raise_for_status()
            audio_url = r.json()["output"]["audio"]["url"]
            data = requests.get(audio_url, timeout=120)
            data.raise_for_status()
            return data.content
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(sleep * (attempt + 1))
    raise RuntimeError(str(last))


def synth_edge(text: str, voice: str | None = None, retries: int = 3, sleep: float = 1.0) -> bytes:
    """edge-tts（微软，免费）→ mp3 bytes；百炼额度不足时的兜底引擎。"""
    import asyncio

    import edge_tts

    async def _run() -> bytes:
        comm = edge_tts.Communicate(text, voice or EDGE_VOICE)
        buf = bytearray()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                buf.extend(chunk["data"])
        return bytes(buf)

    last = None
    for attempt in range(retries):
        try:
            data = asyncio.run(_run())
            if not data:
                raise RuntimeError("empty audio")
            return data
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(sleep * (attempt + 1))
    raise RuntimeError(str(last))


def wav_to_mp3(wav_bytes: bytes, mp3_path: pathlib.Path) -> float:
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        tmp = f.name
    try:
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", tmp,
             "-codec:a", "libmp3lame", "-b:a", "64k", "-ac", "1", str(mp3_path)],
            check=True)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(mp3_path)],
            check=True, capture_output=True, text=True)
        return float(probe.stdout.strip() or 0)
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)


def probe_dur(mp3: pathlib.Path) -> float:
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(mp3)],
            capture_output=True, text=True)
        return round(float(probe.stdout.strip() or 0), 1)
    except Exception:  # noqa: BLE001
        return 0


def generate(content: dict, out_dir: pathlib.Path, voice: str = "Ethan",
             only: set | None = None, dry_run: bool = False,
             sleep_between: float = 0.8, settings=None, engine: str = "bailian") -> dict:
    settings = settings or load_settings()
    plan = clip_plan(content, only)
    stats = {"planned": len(plan), "done": 0, "skipped": 0, "failed": 0}
    failed = []
    durs: dict[str, float] = {}
    for item in plan:
        mp3 = out_dir / f"{item['clip_id']}.mp3"
        if mp3.exists():
            stats["skipped"] += 1
            continue
        if dry_run:
            continue
        try:
            if engine == "edge":
                edge_voice = voice if voice and voice != "Ethan" else None
                data = synth_edge(item["text"], edge_voice)
                mp3.parent.mkdir(parents=True, exist_ok=True)
                mp3.write_bytes(data)
                durs[item["clip_id"]] = probe_dur(mp3)
            elif engine == "qwen_audio":
                qa_voice = voice if voice and voice != "Ethan" else None
                data = synth_qwen_audio(item["text"], qa_voice, settings)
                mp3.parent.mkdir(parents=True, exist_ok=True)
                mp3.write_bytes(data)
                durs[item["clip_id"]] = probe_dur(mp3)
            else:
                wav = synth(item["text"], voice, settings)
                durs[item["clip_id"]] = wav_to_mp3(wav, mp3)
            stats["done"] += 1
            if sleep_between:
                time.sleep(sleep_between)
        except Exception as e:  # noqa: BLE001
            stats["failed"] += 1
            failed.append({"clip_id": item["clip_id"], "error": str(e)[:200]})
    if failed:
        (out_dir.parent / "audio_failed.json").write_text(
            json.dumps(failed, ensure_ascii=False, indent=1), encoding="utf-8")
    backfill_audio(content, out_dir, durs)
    return stats


def backfill_audio(content: dict, out_dir: pathlib.Path, durs: dict) -> None:
    """把已存在的 mp3 回填到每个点的 audio 数组。"""
    for subj in content.get("subjects", []):
        for ch in subj.get("chapters", []):
            for p in ch.get("points", []):
                pid = p["id"]
                own = sorted(out_dir.glob(f"{pid}.mp3")) + \
                    sorted(out_dir.glob(f"{pid}-p*.mp3"),
                           key=lambda x: int(x.stem.rsplit("-p", 1)[1]))
                audio = []
                for mp3 in own:
                    cid = mp3.stem
                    dur = durs.get(cid)
                    if dur is None:
                        try:
                            probe = subprocess.run(
                                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(mp3)],
                                capture_output=True, text=True)
                            dur = round(float(probe.stdout.strip() or 0), 1)
                        except Exception:  # noqa: BLE001
                            dur = 0
                    audio.append({"src": f"audio/{mp3.name}", "dur": dur})
                p["audio"] = audio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", action="append", default=None)
    ap.add_argument("--voice", default="Ethan")
    ap.add_argument("--engine", choices=["bailian", "qwen_audio", "edge"], default="bailian")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.8)
    ap.add_argument("--content", default=str(ROOT / "content" / "content.json"))
    args = ap.parse_args()

    content_path = pathlib.Path(args.content)
    content = json.loads(content_path.read_text(encoding="utf-8"))
    out_dir = content_path.parent / "audio"
    only = set(args.subject) if args.subject else None
    stats = generate(content, out_dir, voice=args.voice, only=only,
                     dry_run=args.dry_run, sleep_between=args.sleep, engine=args.engine)
    if not args.dry_run:
        content_path.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"计划 {stats['planned']} · 新生成 {stats['done']} · 跳过 {stats['skipped']} · 失败 {stats['failed']}")
    if stats["failed"]:
        print("失败清单见 content/audio_failed.json（重跑本脚本自动续）")


if __name__ == "__main__":
    main()
