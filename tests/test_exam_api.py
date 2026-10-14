import json


def _boot(tmp_path, monkeypatch, content_dict):
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("KY_DATA_DIR", str(tmp_path))
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "content.json").write_text(json.dumps(content_dict, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("KY_CONTENT_DIR", str(content_dir))
    from app import auth

    monkeypatch.setenv("KY_PASSWORD_HASH", auth.hash_password("pw"))
    monkeypatch.setenv("KY_SESSION_SECRET", "s")
    from app.config import get_settings

    get_settings.cache_clear()
    from app import content as content_mod

    content_mod.reset_cache()


def test_exam_api_roundtrip(tmp_path, monkeypatch):
    from tests.test_exam_engine import _content

    _boot(tmp_path, monkeypatch, _content())
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        r = c.post("/api/exam/new", json={"subject": "315", "kind": "objective"})
        assert r.status_code == 200
        paper = r.json()
        exam_id = paper["exam_id"]
        # 刷新恢复：GET 拿到同一卷面
        got = c.get(f"/api/exam/{exam_id}").json()
        assert got["finished"] is False
        assert [s["name"] for s in got["paper"]["sections"]] == ["选择题", "填空题"]
        # 交卷
        responses = []
        for s in paper["sections"]:
            for it in s["items"]:
                responses.append({"item_id": it["id"],
                                  "response": 0 if s["type"] == "single" else ["7"]})
        responses[0] = {"item_id": responses[0]["item_id"], "response": 1}
        r = c.post("/api/exam/submit", json={"exam_id": exam_id, "responses": responses, "verdicts": []})
        body = r.json()
        assert r.status_code == 200 and body["score"] == 98 and body["total"] == 100
        assert len(body["wrong_quiz_ids"]) == 1
        assert c.post("/api/exam/submit", json={"exam_id": exam_id, "responses": [], "verdicts": []}).status_code == 409
        assert c.get(f"/api/exam/{exam_id}").json()["finished"] is True
    from app.config import get_settings

    get_settings.cache_clear()
