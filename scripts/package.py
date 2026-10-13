#!/usr/bin/env python3
"""打包 dist/：web + content.json + audio + media，附版本清单。

用法：python scripts/package.py [--with-private] [--out dist]
  --with-private  同时打入 private-media/（教材裁图，个人使用；上传目标服务器）
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent


def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def copy_tree(src: pathlib.Path, dst: pathlib.Path, pattern: str = "*") -> int:
    n = 0
    if not src.exists():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.rglob(pattern):
        if f.is_file():
            rel = f.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--with-private", action="store_true")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    content = ROOT / "content"

    manifest = {
        "packed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "content_version": json.loads((content / "content.json").read_text(encoding="utf-8"))["version"],
        "content.json": sha256(content / "content.json"),
    }
    manifest["web_files"] = copy_tree(ROOT / "web", out / "web")
    shutil.copy2(content / "content.json", out / "content.json")
    manifest["audio_files"] = copy_tree(content / "audio", out / "audio")
    manifest["media_files"] = copy_tree(content / "media", out / "media")
    if args.with_private:
        manifest["private_media_files"] = copy_tree(ROOT / "private-media", out / "media-private")

    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"dist/ 完成：{manifest}")
    print(f"总大小 {total/1e6:.1f} MB")


if __name__ == "__main__":
    main()
