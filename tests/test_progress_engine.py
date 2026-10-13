def test_compute_chapter_mean():
    from app.services.progress_engine import compute_chapter

    assert compute_chapter(["a", "b"], {"a": "known", "b": "half"}) == 0.75
    assert compute_chapter([], {}) == 0.0
    assert compute_chapter(["a"], {}) == 0.0  # 无记录视为 new


def test_compute_subject_weighted():
    from app.services.progress_engine import compute_subject

    chapters = [
        {"weight_center": 23, "points": ["a", "b"]},
        {"weight_center": 6, "points": ["c", "d"]},
    ]
    states = {"a": "known", "b": "half", "c": "new", "d": "new"}
    r = compute_subject(chapters, states)
    assert r["raw"] == 0.375
    assert abs(r["weighted"] - (0.75 * 23 + 0.0 * 6) / 29) < 1e-9


def test_compute_all_reports_include_empty_subject():
    import json
    import pathlib

    from app.services.progress_engine import compute_all

    content = json.loads((pathlib.Path(__file__).parent / "fixtures" / "content_small.json").read_text())
    reports = compute_all(content, {"812-04-01": "known"})
    by_id = {r["id"]: r for r in reports}
    assert set(by_id) == {"812", "204"}
    assert by_id["204"]["weighted"] == 0.0 and by_id["204"]["chapters"] == []
    ch = {c["id"]: c for c in by_id["812"]["chapters"]}
    assert ch["812-04"]["completion"] == 0.5  # 2 点 1 会
    assert ch["812-04"]["tier"] == 1
