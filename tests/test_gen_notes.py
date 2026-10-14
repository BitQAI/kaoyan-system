import json


def test_parse_reply_tolerates_fence_and_noise():
    from scripts.gen_notes import parse_reply

    got = parse_reply('```json\n{"note":"n","exam":"e","keywords":["a","b"]}\n```')
    assert got == {"note": "n", "exam": "e", "keywords": ["a", "b"]}
    got = parse_reply('好的：{"note":"n","exam":"e","keywords":["a"]} 完成')
    assert got["note"] == "n"
    assert parse_reply("没有 JSON 的回复") is None
    assert parse_reply('{"note":"n"}') is None          # 缺 exam → 判失败
    assert parse_reply('{"note":"","exam":"e","keywords":["a"]}') is None


def test_parse_reply_caps_keywords():
    from scripts.gen_notes import parse_reply

    got = parse_reply(json.dumps({"note": "n", "exam": "e",
                                  "keywords": [f"k{i}" for i in range(10)]}, ensure_ascii=False))
    assert len(got["keywords"]) == 6


def test_merge_into_content_writes_fields(tmp_path, monkeypatch):
    from scripts import gen_notes as g

    content_path = tmp_path / "content.json"
    content_path.write_text(json.dumps({
        "subjects": [{"id": "101", "chapters": [{"id": "101-02", "points": [
            {"id": "101-02-01", "text": "哲学基本问题"},
            {"id": "101-02-02", "text": "唯物主义与唯心主义"},
        ]}]}]}, ensure_ascii=False), encoding="utf-8")
    notes = tmp_path / "notes.jsonl"
    notes.write_text(
        json.dumps({"id": "101-02-01", "text": "哲学基本问题", "note": "讲解",
                    "exam": "考法", "keywords": ["甲", "乙"]}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(g, "NOTES_FILE", notes)

    n = g.merge_into_content(content_path)
    assert n == 1
    data = json.loads(content_path.read_text(encoding="utf-8"))
    p1, p2 = data["subjects"][0]["chapters"][0]["points"]
    assert p1["note"] == "讲解" and p1["exam"] == "考法" and p1["keywords"] == ["甲", "乙"]
    assert "note" not in p2


def test_iter_points_skips_self_in_siblings():
    from scripts.gen_notes import iter_points

    content = {"subjects": [{"id": "812", "name": "植物生理学", "chapters": [
        {"id": "812-00", "name": "绪论", "points": [
            {"id": "a", "text": "甲"}, {"id": "b", "text": "乙"}]}]}]}
    rows = list(iter_points(content, {"812"}))
    assert [r[2]["id"] for r in rows] == ["a", "b"]
    assert rows[0][3] == ["乙"] and rows[1][3] == ["甲"]
    assert list(iter_points(content, {"315"})) == []
