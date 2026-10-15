import pathlib

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "content_small.json"


def _boot(tmp_path, monkeypatch):
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("KY_DATA_DIR", str(tmp_path))
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "content.json").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("KY_CONTENT_DIR", str(content_dir))
    from app import auth

    monkeypatch.setenv("KY_PASSWORD_HASH", auth.hash_password("pw"))
    monkeypatch.setenv("KY_SESSION_SECRET", "s")
    from app.config import get_settings

    get_settings.cache_clear()
    from app import content as content_mod

    content_mod.reset_cache()


def _teardown():
    from app.config import get_settings

    get_settings.cache_clear()


def test_attempt_multi_and_blank_shapes(tmp_path, monkeypatch):
    """新题型 API：multi 全对才得分；blank 归一化匹配。"""
    import json as _json

    _boot(tmp_path, monkeypatch)
    # 向测试 content 注入 multi / blank 两题
    cpath = tmp_path / "content" / "content.json"
    data = _json.loads(cpath.read_text(encoding="utf-8"))
    ch = data["subjects"][0]["chapters"][0]
    ch["quiz"].extend([
        {"id": "q81201m1", "chapter": "812-01", "point_id": "812-01-01", "type": "multi",
         "stem": "关于细胞壁，正确的有？", "options": ["含纤维素", "含血红蛋白", "支持保护", "仅细菌有"],
         "answer": [0, 2], "explain": "纤维素+支持保护正确。"},
        {"id": "q81201b1", "chapter": "812-01", "point_id": "812-01-01", "type": "blank",
         "stem": "水势组成式 Ψw=Ψs+Ψp+____，填入第三项。",
         "blanks": [{"accept": ["Ψm", "Ψ_m", "衬质势"]}], "explain": "衬质势 Ψm。"},
    ])
    cpath.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
    from app import content as content_mod

    content_mod.reset_cache()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        r = c.post("/api/quiz/attempt", json={"quiz_id": "q81201m1", "response": [2, 0]})
        assert r.json()["correct"] is True
        r = c.post("/api/quiz/attempt", json={"quiz_id": "q81201m1", "response": [0]})
        assert r.json()["correct"] is False
        r = c.post("/api/quiz/attempt", json={"quiz_id": "q81201b1", "response": ["Ψ_m"]})
        assert r.json()["correct"] is True
        r = c.post("/api/quiz/attempt", json={"quiz_id": "q81201b1", "response": ["Ksp"]})
        assert r.json()["correct"] is False
    _teardown()


def test_attempt_wrong_then_resolve(tmp_path, monkeypatch):
    _boot(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        # 答错 → 入错题本
        r = c.post("/api/quiz/attempt", json={"quiz_id": "q8120101", "chosen": 0})
        assert r.json()["correct"] is False
        assert "血红蛋白" in r.json()["explain"]
        wrong = c.get("/api/quiz/wrong").json()["items"]
        assert len(wrong) == 1 and wrong[0]["id"] == "q8120101"
        # 连对两次 → 出本
        assert c.post("/api/quiz/attempt", json={"quiz_id": "q8120101", "chosen": 3}).json()["correct"] is True
        assert len(c.get("/api/quiz/wrong").json()["items"]) == 1  # 1 次正确未出本
        c.post("/api/quiz/attempt", json={"quiz_id": "q8120101", "chosen": 3})
        assert c.get("/api/quiz/wrong").json()["items"] == []
    _teardown()


def test_quiz_run_modes(tmp_path, monkeypatch):
    _boot(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        items = c.get("/api/quiz/run", params={"mode": "chapter", "chapter": "812-01"}).json()["items"]
        assert [q["id"] for q in items] == ["q8120101"]
        c.post("/api/quiz/attempt", json={"quiz_id": "q8120101", "chosen": 0})
        assert len(c.get("/api/quiz/run", params={"mode": "wrong"}).json()["items"]) == 1
        c.post("/api/favorite", json={"type": "quiz", "ref_id": "q8120101", "action": "add"})
        assert len(c.get("/api/quiz/run", params={"mode": "favorites"}).json()["items"]) == 1
    _teardown()


def test_quiz_run_mix_interleaves_subjects(tmp_path, monkeypatch):
    """mix：跨科交错——相邻题目尽量来自不同科目。"""
    import json as _json

    _boot(tmp_path, monkeypatch)
    cpath = tmp_path / "content" / "content.json"
    data = _json.loads(cpath.read_text(encoding="utf-8"))
    data["subjects"][1] = {"id": "204", "name": "英语（二）", "has_content": True, "chapters": [
        {"id": "204-01", "name": "完形", "tier": 2, "weight_center": 5, "points": [],
         "quiz": [{"id": "q2040101", "chapter": "204-01", "stem": "完形 1",
                   "options": ["A", "B", "C", "D"], "answer": 0, "explain": ""}]}]}
    ch = data["subjects"][0]["chapters"][0]
    ch["quiz"].append({"id": "q8120102", "chapter": "812-01", "point_id": "812-01-01",
                       "stem": "细胞壁功能", "options": ["A", "B", "C", "D"], "answer": 1, "explain": ""})
    cpath.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
    from app import content as content_mod

    content_mod.reset_cache()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        items = c.get("/api/quiz/run", params={"mode": "mix", "n": 3}).json()["items"]
        assert len(items) == 3
        subs = [q["id"][1:4] for q in items]
        assert subs[0] != subs[1], f"相邻同科，未交错: {subs}"
        assert set(subs) == {"812", "204"}
    _teardown()


def test_quiz_run_point_mode(tmp_path, monkeypatch):
    """point：只出该考点的题。"""
    _boot(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        items = c.get("/api/quiz/run",
                      params={"mode": "point", "point_id": "812-01-01"}).json()["items"]
        assert [q["id"] for q in items] == ["q8120101"]
        assert c.get("/api/quiz/run",
                     params={"mode": "point", "point_id": "nope"}).json()["items"] == []
    _teardown()


def test_card_review_updates_point_state(tmp_path, monkeypatch):
    _boot(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        c.post("/api/cards/review", json={"card_id": "c8120101", "verdict": "know"})
        assert c.get("/api/progress").json()["states"]["812-01-02"] == "known"
        c.post("/api/cards/review", json={"card_id": "c8120101", "verdict": "fuzzy"})
        assert c.get("/api/progress").json()["states"]["812-01-02"] == "half"
        c.post("/api/cards/review", json={"card_id": "c8120101", "verdict": "no"})
        assert c.get("/api/progress").json()["states"]["812-01-02"] == "review"
    _teardown()
