def test_favorite_toggle_and_list(client):
    res = client.post("/api/favorites", json={"kind": "point", "ref_id": "8120001"})
    assert res.status_code == 200
    assert "8120001" in res.json()["ids"]["point"]

    items = client.get("/api/favorites", params={"kind": "point"}).json()["items"]
    assert any(i["ref_id"] == "8120001" for i in items)

    client.post("/api/favorites", json={"kind": "point", "ref_id": "8120001", "on": False})
    items = client.get("/api/favorites", params={"kind": "point"}).json()["items"]
    assert not any(i["ref_id"] == "8120001" for i in items)


def test_favorite_card(client):
    card_id = client.post("/api/queue/custom", json={"mode": "memo", "limit": 1}) \
        .json()["items"][0]["card_id"]
    client.post("/api/favorites", json={"kind": "card", "ref_id": card_id})
    items = client.get("/api/favorites", params={"kind": "card"}).json()["items"]
    assert any(i["ref_id"] == card_id and i["question"] for i in items)
    client.post("/api/favorites", json={"kind": "card", "ref_id": card_id, "on": False})


def test_favorite_rejects_bad_kind(client):
    assert client.post("/api/favorites",
                       json={"kind": "nope", "ref_id": "x"}).status_code == 400


def test_weak_book_collects_fuzzy_and_forgot(client):
    cards = client.post("/api/queue/custom", json={"mode": "memo", "limit": 3}).json()["items"]
    client.post("/api/progress/card", json={"card_id": cards[0]["card_id"], "result": "忘了"})
    client.post("/api/progress/card", json={"card_id": cards[1]["card_id"], "result": "吃力"})
    client.post("/api/progress/card", json={"card_id": cards[2]["card_id"], "result": "秒答"})

    got = client.get("/api/review/weak").json()
    ids = [i["card_id"] for i in got["items"]]
    assert cards[0]["card_id"] in ids and cards[1]["card_id"] in ids
    assert cards[2]["card_id"] not in ids
    assert ids.index(cards[0]["card_id"]) < ids.index(cards[1]["card_id"]), "忘了排在吃力前面"
    assert got["counts"]["forgot"] >= 1 and got["counts"]["fuzzy"] >= 1


def test_queue_orders_by_chapter_weight(client):
    got = client.post("/api/queue/custom", json={
        "mode": "memo", "subjects": ["812"], "limit": 5}).json()
    chapters = {c["id"]: c for c in client.get("/api/subjects/812/chapters").json()["items"]}
    first = chapters[got["items"][0]["chapter_id"]]
    assert first["weight_center"] >= 10, "大分章应排前面"
