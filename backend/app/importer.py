"""元数据 JSON → SQLite 导入（只读上游，幂等）。

源：知识点元数据/subjects/<sid>/<sid>.json（ky-point/3.0）
策略：单事务「先删后插」，重跑结果与首跑一致。
"""
import json
from pathlib import Path

from app import config, db

CONTENT_TABLES = ("relation", "media", "card", "unit", "point", "chapter",
                  "subject")


def _json(value, default="[]") -> str:
    if value is None:
        return default
    return json.dumps(value, ensure_ascii=False)


def import_all(conn, meta_dir: Path | None = None) -> dict[str, int]:
    meta = Path(meta_dir or config.META_DIR)
    docs = []
    for sid in config.SUBJECTS:
        path = meta / "subjects" / sid / f"{sid}.json"
        docs.append(json.loads(path.read_text(encoding="utf-8")))

    for table in CONTENT_TABLES:
        conn.execute(f"DELETE FROM {table}")

    for sort_idx, (sid, doc) in enumerate(zip(config.SUBJECTS, docs)):
        _insert_subject(conn, sid, doc, sort_idx)
        _insert_chapters(conn, sid, doc)
        for point in doc["points"]:
            _insert_point(conn, sid, point)
            _insert_units(conn, point)
            _insert_cards(conn, point)
            _insert_media(conn, point)
            _insert_relations(conn, point)

    _fill_relation_names(conn)
    conn.commit()
    db.rebuild_fts(conn)
    return counts(conn)


def _insert_subject(conn, sid: str, doc: dict, sort_idx: int) -> None:
    conn.execute(
        "INSERT INTO subject (id, name, score, status, generated_at, source_file, sort) "
        "VALUES (?,?,?,?,?,?,?)",
        (sid, doc["name"] if doc["name"].startswith(sid) else f"{sid} {doc['name']}",
         doc.get("score"), doc.get("status"),
         doc.get("generated_at"), doc.get("source_file"), sort_idx),
    )


def _insert_chapters(conn, sid: str, doc: dict) -> None:
    for idx, ch in enumerate(doc["chapters"]):
        conn.execute(
            "INSERT INTO chapter (id, subject_id, name, module, tier, weight_center, "
            "weight_range, weight_basis, entry_count, note, sort) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ch["id"], sid, ch["name"], ch["module"], ch["tier"],
             int(ch["weight_center"]), _json(ch.get("weight_range"), "null"),
             ch["weight_basis"], ch["entry_count"], ch.get("note"), idx),
        )


def _insert_point(conn, sid: str, p: dict) -> None:
    src = p.get("source") or {}
    ev = p.get("exam_evidence") or {}
    listen = p.get("listen") or {}
    tts = p.get("tts") or {}
    conn.execute(
        "INSERT INTO point (id, subject_id, chapter_id, ord, point, title, explain, exam, "
        "keywords, priority, tags, exam_types, source_ref, source_file, source_section, "
        "source_basis, source_kind, spoken, listen_script, listen_card_id, listen_kind, "
        "tts_enabled, tts_est_sec, evidence_level, evidence_basis, evidence_sources) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (p["id"], sid, p["chapter"], p.get("order", 0), p["point"], p["title"],
         p["explain"], p["exam"], _json(p.get("keywords")), p["priority"],
         _json(p.get("tags")), _json(p.get("exam_types")),
         src.get("ref"), src.get("file"), src.get("section"), src.get("basis"),
         src.get("kind"), p.get("spoken") or "", listen.get("script") or "",
         listen.get("card_id"), listen.get("kind"),
         1 if tts.get("enabled") else 0,
         int(tts["est_sec"]) if tts.get("est_sec") else None,
         ev.get("level", "pending"), ev.get("basis", ""),
         _json(ev.get("sources"))),
    )


def _insert_units(conn, p: dict) -> None:
    for idx, text in enumerate(p.get("units") or [], start=1):
        conn.execute(
            "INSERT INTO unit (point_id, idx, text) VALUES (?,?,?)",
            (p["id"], idx, text),
        )


def _insert_cards(conn, p: dict) -> None:
    for idx, c in enumerate(p.get("cards") or []):
        conn.execute(
            "INSERT INTO card (card_id, point_id, ord, kind, card_type, question, answer, "
            "options, answer_points, analysis, unit_refs, difficulty, payload) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c["card_id"], p["id"], idx, c.get("kind", ""), c.get("card_type", ""),
             c.get("question", ""), c.get("answer", ""),
             _json(c.get("options")), _json(c.get("answer_points")),
             c.get("analysis", ""), _json(c.get("unit_refs")),
             c.get("difficulty"), _json(c.get("payload") or {}, "{}")),
        )


def _insert_media(conn, p: dict) -> None:
    for idx, m in enumerate(p.get("media") or []):
        conn.execute(
            "INSERT INTO media (point_id, idx, kind, caption, alt, svg) "
            "VALUES (?,?,?,?,?,?)",
            (p["id"], idx, m.get("kind", "diagram"), m.get("caption", ""),
             m.get("alt", ""), m.get("svg", "")),
        )


def _insert_relations(conn, p: dict) -> None:
    pid = p["id"]
    for idx, target in enumerate(p.get("prerequisites") or []):
        conn.execute(
            "INSERT INTO relation (point_id, kind, target_id, name, distinction, idx) "
            "VALUES (?,?,?,?,?,?)",
            (pid, "prerequisite", target, "", "", idx),
        )
    for idx, target in enumerate(p.get("related") or []):
        conn.execute(
            "INSERT INTO relation (point_id, kind, target_id, name, distinction, idx) "
            "VALUES (?,?,?,?,?,?)",
            (pid, "related", target, "", "", idx),
        )
    for idx, c in enumerate(p.get("confusables") or []):
        conn.execute(
            "INSERT INTO relation (point_id, kind, target_id, name, distinction, idx) "
            "VALUES (?,?,?,?,?,?)",
            (pid, "confusable", c.get("point_id"), c.get("name", ""),
             c.get("distinction", ""), idx),
        )


def _fill_relation_names(conn) -> None:
    """prerequisite/related 只有 id，补上目标点的 title 供 UI 直接显示。"""
    conn.execute(
        "UPDATE relation SET name = COALESCE("
        "(SELECT p.title FROM point p WHERE p.id = relation.target_id), '') "
        "WHERE kind IN ('prerequisite', 'related')"
    )


def counts(conn) -> dict[str, int]:
    out = {}
    for table in ("subject", "chapter", "point", "unit", "card", "media",
                  "relation", "point_fts", "card_fts"):
        out[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return out


def expected_counts(meta_dir: Path | None = None) -> dict[str, int]:
    """从源 JSON 直接算期望值，供导入后比对。"""
    meta = Path(meta_dir or config.META_DIR)
    exp = {"subject": 0, "chapter": 0, "point": 0, "unit": 0, "card": 0,
           "media": 0, "relation": 0}
    for sid in config.SUBJECTS:
        doc = json.loads(
            (meta / "subjects" / sid / f"{sid}.json").read_text(encoding="utf-8"))
        exp["subject"] += 1
        exp["chapter"] += len(doc["chapters"])
        for p in doc["points"]:
            exp["point"] += 1
            exp["unit"] += len(p.get("units") or [])
            exp["card"] += len(p.get("cards") or [])
            exp["media"] += len(p.get("media") or [])
            exp["relation"] += (len(p.get("prerequisites") or [])
                                + len(p.get("related") or [])
                                + len(p.get("confusables") or []))
    exp["point_fts"] = exp["point"]
    exp["card_fts"] = exp["card"]
    return exp
