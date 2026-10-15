"""端到端：真实 content.json + 全 API 流（无网络）。"""
import json
import pathlib
import shutil

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
REAL_CONTENT = ROOT / "content" / "content.json"


@pytest.mark.skipif(not REAL_CONTENT.exists(), reason="需先生成 content.json")
def test_real_content_passes_validation():
    from scripts.validate_content import check

    content = json.loads(REAL_CONTENT.read_text(encoding="utf-8"))
    errors = check(content, content_dir=ROOT / "content")
    assert errors == [], errors[:10]
    subjects = {s["id"]: s for s in content["subjects"]}
    assert set(subjects) == {"101", "204", "315", "812"}
    for sid in ("812", "315", "101", "204"):
        assert subjects[sid]["has_content"] is True
        assert len(subjects[sid]["chapters"]) > 0
        assert sum(c["weight_center"] for c in subjects[sid]["chapters"]) > 0
    # 204 无音频（复习型科目）：不应有章级听单
    assert all(not (c.get("listen") or []) for c in subjects["204"]["chapters"])


@pytest.mark.skipif(not REAL_CONTENT.exists(), reason="需先生成 content.json")
def test_full_api_flow_with_real_content(tmp_path, monkeypatch):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    shutil.copy(REAL_CONTENT, content_dir / "content.json")
    monkeypatch.setenv("KY_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("KY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("KY_CONTENT_DIR", str(content_dir))
    from app import auth

    monkeypatch.setenv("KY_PASSWORD_HASH", auth.hash_password("pw"))
    monkeypatch.setenv("KY_SESSION_SECRET", "s")
    from app.config import get_settings

    get_settings.cache_clear()
    from app import content as content_mod

    content_mod.reset_cache()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        assert c.post("/api/login", json={"password": "pw"}).status_code == 200
        data = c.get("/api/content").json()
        assert data["version"]
        plan = c.get("/api/plan/today").json()
        assert plan["days_left"] > 0
        # 做一道 812-04 的题：答错 → 入错题本
        quiz = c.get("/api/quiz/run", params={"mode": "chapter", "chapter": "812-04"}).json()["items"][0]
        wrong_choice = (quiz["answer"] + 1) % len(quiz["options"])
        r = c.post("/api/quiz/attempt", json={"quiz_id": quiz["id"], "chosen": wrong_choice}).json()
        assert r["correct"] is False
        assert any(q["id"] == quiz["id"] for q in c.get("/api/quiz/wrong").json()["items"])
        # 连对两次出本
        for _ in range(2):
            c.post("/api/quiz/attempt", json={"quiz_id": quiz["id"], "chosen": quiz["answer"]})
        assert all(q["id"] != quiz["id"] for q in c.get("/api/quiz/wrong").json()["items"])
        # 背题卡评分 → 卡级调度（V4：与考点状态解耦）
        card = next(cd for s in data["subjects"] if s["id"] == "812"
                    for ch in s["chapters"] for cd in ch["cards"])
        r = c.post("/api/card_review", json={"card_id": card["id"], "rating": "good"}).json()
        assert r["ok"] and r["next"]["again"] == 1
        from app import db as _db

        con = _db.connect()
        assert con.execute("SELECT stage FROM card_reviews WHERE card_id=?",
                           (card["id"],)).fetchone()["stage"] == 1
        con.close()
        # 单元评分 → 考点进度（进度环数据来源）
        pt = next(p for s in data["subjects"] if s["id"] == "812"
                  for ch in s["chapters"] for p in ch["points"] if p.get("units"))
        c.post("/api/unit_review", json={"point_id": pt["id"], "rating": "good", "all": True})
        # 播放位置
        clip = next(a["src"] for s in data["subjects"] if s["id"] == "812"
                    for ch in s["chapters"] for p in ch["points"] for a in p["audio"])
        clip_id = clip.replace("audio/", "").replace(".mp3", "")
        c.post("/api/audio_pos", json={"clip_id": clip_id, "position_sec": 12.5, "plays_delta": 1})
        pos = c.get("/api/audio_pos").json()[clip_id]
        assert pos["position_sec"] == 12.5 and pos["plays"] == 1
        # 进度环加权值 > 0
        ring = {r["id"]: r for r in c.get("/api/stats").json()["ring"]}
        assert ring["812"]["weighted"] > 0
    get_settings.cache_clear()
    content_mod.reset_cache()
