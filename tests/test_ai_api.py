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


def _fake_stream_factory(events, fail_after=None):
    def fake(messages, session_id, settings, timeout=120):
        for i, e in enumerate(events):
            if fail_after is not None and i >= fail_after:
                raise RuntimeError("stream broke")
            yield e
        if fail_after is not None and fail_after >= len(events):
            raise RuntimeError("stream broke")
    return fake


def test_chat_streams_and_persists(tmp_path, monkeypatch):
    _boot(tmp_path, monkeypatch)
    from app.services import providers

    events = [{"type": "reasoning", "delta": "嗯"},
              {"type": "content", "delta": "光呼吸是"}, {"type": "content", "delta": "乙醇酸途径。"}]
    monkeypatch.setattr(providers, "stream_chat", _fake_stream_factory(events))
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        r = c.post("/api/ai/chat", json={"owner_type": "point", "owner_ref": "812-04-01",
                                         "message": "为什么说 C4 是二氧化碳泵？"})
        assert r.status_code == 200
        text = r.text
        assert '"type": "reasoning"' in text.replace("'", '"') or '"reasoning"' in text
        assert "乙醇酸途径。" in text and '"type": "done"' in text.replace("'", '"')
        threads = c.get("/api/ai/threads").json()["items"]
        assert len(threads) == 1 and threads[0]["owner_ref"] == "812-04-01"
        tid = threads[0]["id"]
        msgs = c.get(f"/api/ai/threads/{tid}/messages").json()["items"]
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert "乙醇酸途径" in msgs[1]["content"] and msgs[1]["reasoning"] == "嗯"
        # 同一锚点第二次提问 → 复用线程
        c.post("/api/ai/chat", json={"owner_type": "point", "owner_ref": "812-04-01", "message": "再讲讲"})
        assert len(c.get("/api/ai/threads").json()["items"]) == 1
    _teardown()


def test_chat_partial_save_on_error(tmp_path, monkeypatch):
    _boot(tmp_path, monkeypatch)
    from app.services import providers

    events = [{"type": "content", "delta": "前半段答案"}]
    monkeypatch.setattr(providers, "stream_chat", _fake_stream_factory(events, fail_after=1))
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw"})
        r = c.post("/api/ai/chat", json={"owner_type": "free", "owner_ref": None, "message": "问一句"})
        assert '"type": "error"' in r.text.replace("'", '"')
        threads = c.get("/api/ai/threads").json()["items"]
        msgs = c.get(f"/api/ai/threads/{threads[0]['id']}/messages").json()["items"]
        assert any(m["role"] == "assistant" and "前半段答案" in m["content"] for m in msgs)
    _teardown()
