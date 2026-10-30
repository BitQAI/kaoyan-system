from app import service


def _cards(client, mode="memo", limit=3):
    return client.post("/api/queue/custom", json={
        "mode": mode, "limit": limit}).json()["items"]


def test_note_empty_by_default(client):
    card_id = _cards(client)[0]["card_id"]
    got = client.get("/api/notes", params={"card_id": card_id}).json()
    assert got["content"] == ""
    assert got["updated_at"] is None


def test_note_save_and_overwrite(client):
    card_id = _cards(client)[0]["card_id"]
    body = "这个例句是倒装：Not until ... did he ...\n理解为「直到……才」。"
    res = client.put("/api/notes", json={"card_id": card_id, "content": f"  {body}  "})
    assert res.status_code == 200
    assert res.json()["content"] == body

    got = client.get("/api/notes", params={"card_id": card_id}).json()
    assert got["content"] == body

    client.put("/api/notes", json={"card_id": card_id, "content": "改过的笔记"})
    assert client.get("/api/notes", params={"card_id": card_id}).json()["content"] == "改过的笔记"
    client.put("/api/notes", json={"card_id": card_id, "content": ""})


def test_note_empty_content_deletes(client):
    card_id = _cards(client)[0]["card_id"]
    client.put("/api/notes", json={"card_id": card_id, "content": "暂存"})
    res = client.put("/api/notes", json={"card_id": card_id, "content": "   "})
    assert res.status_code == 200
    assert client.get("/api/notes", params={"card_id": card_id}).json()["content"] == ""


def test_note_rejects_too_long(client):
    card_id = _cards(client)[0]["card_id"]
    res = client.put("/api/notes", json={
        "card_id": card_id, "content": "字" * (service.NOTE_MAX_LEN + 1)})
    assert res.status_code == 400


def test_note_unknown_card_404(client):
    res = client.put("/api/notes", json={"card_id": "no-such-card", "content": "x"})
    assert res.status_code == 404


def test_queue_carries_note_in_both_modes(client):
    memo = _cards(client, "memo")[0]
    # 听、记首卡常是同一张；挑一张不同的卡，避免共用同一条笔记
    listen = next(c for c in _cards(client, "listen", limit=50)
                  if c["card_id"] != memo["card_id"])
    assert memo["note"] == "" and listen["note"] == ""

    client.put("/api/notes", json={"card_id": memo["card_id"], "content": "记模块的笔记"})
    client.put("/api/notes", json={"card_id": listen["card_id"], "content": "听模块的笔记"})

    memo2 = {c["card_id"]: c for c in _cards(client, "memo", limit=50)}
    listen2 = {c["card_id"]: c for c in _cards(client, "listen", limit=50)}
    assert memo2[memo["card_id"]]["note"] == "记模块的笔记"
    assert listen2[listen["card_id"]]["note"] == "听模块的笔记"

    client.put("/api/notes", json={"card_id": memo["card_id"], "content": ""})
    client.put("/api/notes", json={"card_id": listen["card_id"], "content": ""})
