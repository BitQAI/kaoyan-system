def test_audio_pos_no_rewind_and_plays_accumulate(ac):
    assert ac.post("/api/audio_pos", json={"clip_id": "812-04-01", "position_sec": 120}).status_code == 200
    ac.post("/api/audio_pos", json={"clip_id": "812-04-01", "position_sec": 30})  # 回退不覆盖
    ac.post("/api/audio_pos", json={"clip_id": "812-04-01", "position_sec": 125, "plays_delta": 1})
    ac.post("/api/audio_pos", json={"clip_id": "812-04-01", "position_sec": 125, "plays_delta": 1})
    data = ac.get("/api/audio_pos").json()
    assert data["812-04-01"]["position_sec"] == 125
    assert data["812-04-01"]["plays"] == 2


def test_favorites_add_remove_idempotent(ac):
    body = {"type": "point", "ref_id": "812-04-01", "action": "add"}
    ac.post("/api/favorite", json=body)
    ac.post("/api/favorite", json=body)  # 幂等
    fav = ac.get("/api/favorites").json()
    assert fav["point"] == ["812-04-01"]
    ac.post("/api/favorite", json={**body, "action": "remove"})
    ac.post("/api/favorite", json={**body, "action": "remove"})  # 幂等
    assert ac.get("/api/favorites").json()["point"] == []


def test_favorite_type_whitelist(ac):
    assert ac.post("/api/favorite", json={"type": "bogus", "ref_id": "x", "action": "add"}).status_code == 422
