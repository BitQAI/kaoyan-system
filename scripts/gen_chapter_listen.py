#!/usr/bin/env python3
"""315/101 章级听单生成：导览语 + 全部考点合并朗读（≤60s/段，超长自动拆 c1/c2）。

用法：python scripts/gen_chapter_listen.py [--subject 315] [--dry-run] [--sleep 0.6] [--force]
幂等：章已有 listen[] 且文件齐全则跳过；成功后删除该章点级 mp3 并清空点级 audio。
"""
import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from content.chapter_intros import CHAPTER_INTROS  # noqa: E402
from scripts.gen_audio import load_settings, probe_dur, synth_qwen_audio  # noqa: E402
from scripts.normalize import split_clips, to_speech  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUBJECTS = ("315", "101")


def build_chapter_spoken(chap: dict, intro: str, subject: str) -> str:
    parts = [to_speech(intro, subject=subject)]
    parts += [p["spoken"] for p in chap.get("points", []) if p.get("spoken")]
    return "。".join(x.rstrip("。") for x in parts if x) + "。"


def _listen_ready(chap: dict, out_dir: pathlib.Path) -> bool:
    entries = chap.get("listen") or []
    if not entries:
        return False
    return all((out_dir / c["src"].removeprefix("audio/")).exists() for c in entries)


def generate(content: dict, out_dir: pathlib.Path, only: set | None = None,
             dry_run: bool = False, sleep_between: float = 0.6,
             settings=None, force: bool = False) -> dict:
    settings = settings or load_settings()
    stats = {"chapters": 0, "clips": 0, "skipped": 0, "failed": 0}
    for subj in content["subjects"]:
        if subj["id"] not in SUBJECTS or (only and subj["id"] not in only):
            continue
        for chap in subj.get("chapters", []):
            intro = CHAPTER_INTROS.get(chap["id"])
            if not intro or not chap.get("points"):
                continue
            if not force and _listen_ready(chap, out_dir):
                stats["skipped"] += 1
                continue
            clips = split_clips(build_chapter_spoken(chap, intro, subj["id"]), 220)
            if dry_run:
                est = sum(len(c) for c in clips) / 4.2
                print(f"[dry] {chap['id']} {chap['name'][:14]:16s} {len(clips)} 段 "
                      f"约 {len(''.join(clips))} 字 · 预估 {est:.0f}s")
                continue
            point_ids = [p["id"] for p in chap["points"]]
            entries = []
            ok = True
            for i, text in enumerate(clips, 1):
                cid = f"{chap['id']}-c{i}"
                mp3 = out_dir / f"{cid}.mp3"
                try:
                    if not mp3.exists():
                        mp3.write_bytes(synth_qwen_audio(text, None, settings))
                        if sleep_between:
                            time.sleep(sleep_between)
                    entries.append({"src": f"audio/{cid}.mp3", "dur": probe_dur(mp3),
                                    "point_ids": point_ids})
                    stats["clips"] += 1
                except Exception as e:  # noqa: BLE001
                    ok = False
                    stats["failed"] += 1
                    print(f"  ! {cid} 失败：{str(e)[:80]}")
                    break
            if ok and entries:
                chap["listen"] = entries
                for p in chap["points"]:
                    for a in p.get("audio", []):
                        old = out_dir / a["src"].removeprefix("audio/")
                        old.unlink(missing_ok=True)
                    p["audio"] = []
                stats["chapters"] += 1
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", action="append", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.6)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--content", default=str(ROOT / "content" / "content.json"))
    args = ap.parse_args()

    path = pathlib.Path(args.content)
    content = json.loads(path.read_text(encoding="utf-8"))
    stats = generate(content, path.parent / "audio",
                     only=set(args.subject) if args.subject else None,
                     dry_run=args.dry_run, sleep_between=args.sleep, force=args.force)
    if not args.dry_run:
        path.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"章级听单：完成 {stats['chapters']} 章 · 片段 {stats['clips']} · "
          f"跳过 {stats['skipped']} · 失败 {stats['failed']}")


if __name__ == "__main__":
    main()
