import json
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


def test_chapters_stats_rate(tmp_path, monkeypatch):
    _boot(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        c.post("/api/quiz/attempt", json={"quiz_id": "q8120101", "chosen": 3})   # 对
        c.post("/api/quiz/attempt", json={"quiz_id": "q8120101", "chosen": 0})   # 错
        items = c.get("/api/stats/chapters", params={"subject": "812"}).json()["items"]
        row = next(x for x in items if x["chap_id"] == "812-01")
        assert row["n"] == 2 and row["correct"] == 1 and row["rate"] == 0.5
        # 无作答章节 rate 为 None
        row2 = next(x for x in items if x["chap_id"] == "812-04")
        assert row2["n"] == 0 and row2["rate"] is None
    _teardown()


def test_export_wrong_markdown_contains_core_fields(tmp_path, monkeypatch):
    _boot(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        c.post("/api/quiz/attempt", json={"quiz_id": "q8120101", "chosen": 0})   # 错
        md = c.get("/api/export/wrong").text
        assert "下列不属于细胞壁成分的是" in md
        assert "血红蛋白是动物蛋白" in md          # 解析
        assert "812-01" in md or "植物细胞" in md   # 章信息
    _teardown()


def test_export_progress_markdown(tmp_path, monkeypatch):
    _boot(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        c.post("/api/progress", json={"point_id": "812-04-01", "state": "known"})
        md = c.get("/api/export/progress").text
        assert "植物生理学" in md and "812-04" in md and "%" in md
    _teardown()
