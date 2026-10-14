"""细项（知识单元）进度：API 与考点状态汇总规则。"""
import json
import pathlib

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "content_small.json"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("KY_DATA_DIR", str(tmp_path))
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # 给第一个考点挂 3 个知识单元
    data["subjects"][0]["chapters"][0]["points"][0]["units"] = ["单元甲", "单元乙", "单元丙"]
    (content_dir / "content.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("KY_CONTENT_DIR", str(content_dir))
    from app import auth

    monkeypatch.setenv("KY_PASSWORD_HASH", auth.hash_password("pw"))
    monkeypatch.setenv("KY_SESSION_SECRET", "s")
    from app.config import get_settings

    get_settings.cache_clear()
    from app import content as content_mod

    content_mod.reset_cache()
    from contextlib import contextmanager

    from fastapi.testclient import TestClient

    from app.main import app

    @contextmanager
    def cm():
        with TestClient(app) as c:
            assert c.post("/api/login", json={"password": "pw"}).status_code == 200
            yield c

    return cm()


def test_unit_states_roundtrip_and_point_state(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as c:
        pid = "812-01-01"
        # 部分标记：第一条会 → 考点汇总为 half
        r = c.post("/api/unit_progress", json={"point_id": pid, "idx": 0, "state": "known"})
        assert r.json()["point_state"] == "half"
        # 全部标记会 → known
        c.post("/api/unit_progress", json={"point_id": pid, "idx": 1, "state": "known"})
        r = c.post("/api/unit_progress", json={"point_id": pid, "idx": 2, "state": "known"})
        assert r.json()["point_state"] == "known"
        # 有一条不会 → review
        r = c.post("/api/unit_progress", json={"point_id": pid, "idx": 1, "state": "review"})
        assert r.json()["point_state"] == "review"
        # 清空全部细项 → 考点回到 new
        for i in range(3):
            r = c.post("/api/unit_progress", json={"point_id": pid, "idx": i, "state": "new"})
        assert r.json()["point_state"] == "new"
        # GET 返回细项状态
        c.post("/api/unit_progress", json={"point_id": pid, "idx": 0, "state": "half"})
        d = c.get("/api/progress").json()
        assert d["unit_states"][f"{pid}#0"] == "half"


def test_unit_progress_isolated_per_point(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as c:
        c.post("/api/unit_progress", json={"point_id": "812-01-01", "idx": 0, "state": "known"})
        d = c.get("/api/progress").json()
        assert f"812-01-02#0" not in d["unit_states"]
        assert d["states"].get("812-01-02") is None
