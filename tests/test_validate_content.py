import json
import pathlib


def _ok_content():
    return {"subjects": [{"id": "812", "chapters": [{
        "id": "812-04", "points": [{"id": "812-04-01", "media": []}],
        "quiz": [{"id": "q8120401", "chapter": "812-04", "stem": "s", "options": ["a", "b"],
                  "answer": 1, "explain": "e", "point_id": "812-04-01"}],
        "cards": [{"id": "c8120401", "chapter": "812-04", "front": "f", "back": "b",
                   "point_id": "812-04-01"}],
    }]}]}


def test_check_passes_clean():
    from scripts.validate_content import check

    assert check(_ok_content()) == []


def test_check_catches_bad_quiz():
    from scripts.validate_content import check

    c = _ok_content()
    q = c["subjects"][0]["chapters"][0]["quiz"][0]
    q["answer"] = 5                      # 越界
    q["point_id"] = "不存在"              # 悬空引用
    q["id"] = "q8120401"
    errs = check(c)
    assert any("answer" in e for e in errs)
    assert any("point_id" in e for e in errs)


def test_check_catches_duplicate_ids():
    from scripts.validate_content import check

    c = _ok_content()
    dup = dict(c["subjects"][0]["chapters"][0]["quiz"][0])
    c["subjects"][0]["chapters"][0]["quiz"].append(dup)
    errs = check(c)
    assert any("重复" in e for e in errs)


def test_check_media_file_exists(tmp_path):
    from scripts.validate_content import check

    c = _ok_content()
    c["subjects"][0]["chapters"][0]["points"][0]["media"] = [
        {"type": "diagram", "src": "media/missing.svg"}]
    errs = check(c, content_dir=tmp_path)
    assert any("missing.svg" in e for e in errs)


def test_merge_quiz_json(tmp_path):
    from scripts.validate_content import merge_quiz

    c = _ok_content()
    c["subjects"][0]["chapters"][0]["quiz"] = []
    c["subjects"][0]["chapters"][0]["cards"] = []
    quiz_dir = tmp_path / "quiz"
    quiz_dir.mkdir()
    (quiz_dir / "812.json").write_text(json.dumps({
        "quizzes": [{"id": "q8120401", "chapter": "812-04", "stem": "s",
                     "options": ["a", "b"], "answer": 0, "explain": "e",
                     "point_id": "812-04-01"}],
        "cards": [{"id": "c8120401", "chapter": "812-04", "front": "f",
                   "back": "b", "point_id": "812-04-01"}],
    }, ensure_ascii=False), encoding="utf-8")
    merge_quiz(c, quiz_dir)
    ch = c["subjects"][0]["chapters"][0]
    assert ch["quiz"][0]["id"] == "q8120401" and ch["cards"][0]["id"] == "c8120401"
