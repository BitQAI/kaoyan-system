#!/usr/bin/env python3
"""媒体生成：结构式(RDKit SVG) / 数据图表(matplotlib PNG) / Commons 检索候选。

用法：
  python scripts/gen_media.py structures   # 依据 content/media_config.py 的 SMILES 表生成
  python scripts/gen_media.py charts
  python scripts/gen_media.py commons --query "photosynthesis diagram"
并入 content.json：生成后由 attach() 把 media 挂到对应知识点。
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from content import media_config  # noqa: E402

MEDIA_DIR = ROOT / "content" / "media"


def gen_structures() -> list[dict]:
    from rdkit import Chem
    from rdkit.Chem import Draw

    out = []
    for point_id, spec in media_config.STRUCTURES.items():
        smiles_list = spec if isinstance(spec, list) else [spec]
        cap = media_config.STRUCTURES_CAPTION.get(point_id, "结构式")
        caps = cap if isinstance(cap, list) else [cap]
        for i, smiles in enumerate(smiles_list):
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                print(f"  ! SMILES 解析失败: {point_id} {smiles}")
                continue
            drawer = Draw.rdMolDraw2D.MolDraw2DSVG(320, 220)
            Draw.rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
            drawer.FinishDrawing()
            svg = drawer.GetDrawingText()
            suffix = "-s.svg" if len(smiles_list) == 1 else f"-s{i + 1}.svg"
            path = MEDIA_DIR / f"{point_id}{suffix}"
            path.write_text(svg, encoding="utf-8")
            out.append({"point_id": point_id, "media": {
                "type": "structure", "src": f"media/{path.name}",
                "caption": caps[i] if i < len(caps) else "结构式",
                "source": "rdkit", "license": "self"}})
    return out


def gen_charts() -> list[dict]:
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt

    out = []
    for point_id, spec in media_config.CHARTS.items():
        fig, ax = plt.subplots(figsize=(4.4, 2.7), dpi=140)
        spec["draw"](ax)
        ax.set_title(spec.get("title", ""), fontsize=9)
        ax.set_xlabel(spec.get("xlabel", ""), fontsize=8)
        ax.set_ylabel(spec.get("ylabel", ""), fontsize=8)
        ax.tick_params(labelsize=7)
        fig.tight_layout()
        path = MEDIA_DIR / f"{point_id}-c.png"
        fig.savefig(path)
        plt.close(fig)
        out.append({"point_id": point_id, "media": {
            "type": "chart", "src": f"media/{path.name}",
            "caption": spec.get("caption", ""), "source": "matplotlib", "license": "self"}})
    return out


def commons_search(query: str, limit: int = 8) -> list[dict]:
    import requests

    r = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params={"action": "query", "format": "json", "generator": "search",
                "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": limit,
                "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 900},
        headers={"User-Agent": "kaoyan-system/0.1 (personal study)"},
        timeout=30,
    )
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages", {})
    out = []
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        out.append({
            "title": p.get("title"), "url": info.get("thumburl") or info.get("url"),
            "license": (meta.get("LicenseShortName") or {}).get("value", "?"),
            "attribution": (meta.get("Artist") or {}).get("value", "?"),
        })
    return out


def attach(entries: list[dict]) -> None:
    content_path = ROOT / "content" / "content.json"
    content = json.loads(content_path.read_text(encoding="utf-8"))
    by_id: dict[str, list] = {}                 # 同点可挂多张（如一组结构式）
    for e in entries:
        by_id.setdefault(e["point_id"], []).append(e["media"])
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
    ap.add_argument("cmd", choices=["structures", "charts", "commons"])
    ap.add_argument("--query", default="")
    ap.add_argument("--no-attach", action="store_true")
    args = ap.parse_args()
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    if args.cmd == "structures":
        entries = gen_structures()
        print(f"结构式 {len(entries)} 张")
    elif args.cmd == "charts":
        entries = gen_charts()
        print(f"图表 {len(entries)} 张")
    else:
        cands = commons_search(args.query)
        cand_path = MEDIA_DIR / "_candidates.json"
        cand_path.write_text(json.dumps(cands, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"候选 {len(cands)} 条 → {cand_path}（人工挑选后写入 media_config.STATIC）")
        return
    if entries and not args.no_attach:
        attach(entries)
        print("已挂到 content.json")


if __name__ == "__main__":
    main()
