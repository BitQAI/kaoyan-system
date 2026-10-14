#!/usr/bin/env python3
"""教材扫描 PDF 裁图（个人学习用，产物入 private-media/，不入库）。

用法：
  单张：python scripts/crop_textbook.py --pdf BK.pdf --page 123 --box 80,120,900,700 --out name.png
  批量：python scripts/crop_textbook.py --config content/figures_textbook.json
  找图：python scripts/crop_textbook.py --pdf BK.pdf --scan 100-160 --step 4 --thumbs /tmp/th
"""
import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRIVATE = ROOT / "content" / "media-private"   # 与 FastAPI 的 /media-private 挂载一致；gitignore 排除


def crop(pdf: str, page: int, box: tuple, out: pathlib.Path, dpi: int = 150) -> dict:
    import pymupdf

    doc = pymupdf.open(pdf)
    pg = doc[page - 1]
    zoom = dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    clip = pymupdf.Rect(box[0] / zoom, box[1] / zoom, box[2] / zoom, box[3] / zoom)
    pix = pg.get_pixmap(matrix=mat, clip=clip)
    out.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out))
    return {"out": str(out), "w": pix.width, "h": pix.height}


def scan_thumbnails(pdf: str, start: int, end: int, step: int, outdir: pathlib.Path,
                    width: int = 420) -> list[str]:
    import pymupdf

    doc = pymupdf.open(pdf)
    outdir.mkdir(parents=True, exist_ok=True)
    outs = []
    for pno in range(start - 1, min(end, doc.page_count), step):
        pg = doc[pno]
        zoom = width / pg.rect.width
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        path = outdir / f"p{pno + 1:04d}.png"
        pix.save(str(path))
        outs.append(str(path))
    return outs


def tile_thumbnails(paths: list[str], out: pathlib.Path, cols: int = 6,
                    cell_w: int = 190) -> dict:
    """把缩略图拼成一张网格图（一次目检多页，用于定位插图）。"""
    from PIL import Image, ImageDraw

    imgs = []
    for p in paths:
        im = Image.open(p)
        h = int(im.height * cell_w / im.width)
        imgs.append((pathlib.Path(p).stem, im.resize((cell_w, h))))
    cell_h = max(im.height for _, im in imgs) + 18
    rows = (len(imgs) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    for i, (name, im) in enumerate(imgs):
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        canvas.paste(im, (x, y + 16))
        draw.text((x + 4, y + 2), name, fill="#b33a3a")
        draw.rectangle([x, y, x + cell_w - 1, y + cell_h - 1], outline="#dddddd")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return {"out": str(out), "pages": len(imgs), "size": [canvas.width, canvas.height]}


def run_config(cfg_path: pathlib.Path) -> list[dict]:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    results = []
    for item in cfg:
        out = PRIVATE / item["out"]
        info = crop(item["pdf"], item["page"], tuple(item["box"]), out, item.get("dpi", 150))
        results.append({**info, "point_id": item.get("point_id"),
                        "caption": item.get("caption", ""),
                        "source_name": item.get("source_name", "textbook")})
    return results


def attach(results: list[dict]) -> None:
    """教材图挂载：src 指向 /media-private/<file>（部署时随 private-media 上传）。"""
    content_path = ROOT / "content" / "content.json"
    content = json.loads(content_path.read_text(encoding="utf-8"))
    by_id = {}
    for r in results:
        if not r.get("point_id"):
            continue
        by_id.setdefault(r["point_id"], []).append({
            "type": "diagram", "src": f"media-private/{pathlib.Path(r['out']).name}",
            "caption": r["caption"], "source": "textbook",
            "license": "个人学习使用（不外传）",
            "attribution": r.get("source_name", ""),
        })
    for subj in content["subjects"]:
        for ch in subj.get("chapters", []):
            for p in ch.get("points", []):
                for m in by_id.get(p["id"], []):
                    p.setdefault("media", [])
                    if not any(x.get("src") == m["src"] for x in p["media"]):
                        p["media"].append(m)
    content_path.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf")
    ap.add_argument("--page", type=int)
    ap.add_argument("--box", help="x0,y0,x1,y1（像素@dpi）")
    ap.add_argument("--out")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--config")
    ap.add_argument("--scan", help="起止页 如 100-160")
    ap.add_argument("--step", type=int, default=4)
    ap.add_argument("--thumbs", default="/tmp/ky_thumbs")
    ap.add_argument("--tile", help="把缩略图拼成网格图输出到该路径（配合 --scan）")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--attach", action="store_true")
    args = ap.parse_args()

    if args.config:
        results = run_config(pathlib.Path(args.config))
        print(f"批量裁图 {len(results)} 张 → private-media/")
        if args.attach:
            attach(results)
            print("已挂到 content.json")
        return
    if args.scan and args.pdf:
        s, e = (int(x) for x in args.scan.split("-"))
        outs = scan_thumbnails(args.pdf, s, e, args.step, pathlib.Path(args.thumbs))
        print(f"缩略图 {len(outs)} 张 → {args.thumbs}")
        if args.tile:
            print(tile_thumbnails(outs, pathlib.Path(args.tile), cols=args.cols))
        return
    if args.pdf and args.page and args.box and args.out:
        info = crop(args.pdf, args.page, tuple(float(x) for x in args.box.split(",")),
                    PRIVATE / args.out, args.dpi)
        print(info)
        return
    ap.error("需要 --config 或 --pdf/--page/--box/--out 或 --pdf/--scan")


if __name__ == "__main__":
    main()
