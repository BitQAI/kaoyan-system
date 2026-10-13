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
