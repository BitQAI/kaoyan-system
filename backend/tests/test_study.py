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


def _seed_word_db(path):
    from app import db
    conn = db.connect(path)
    db.create_tables(conn)
    conn.execute(
        "INSERT INTO chapter (id, subject_id, name, module, tier, weight_center, "
        "weight_basis, entry_count, sort) VALUES "
        "('204-10','204','核心词汇','词汇',2,30,'b',1,0)")
    conn.execute(
        "INSERT INTO point (id, subject_id, chapter_id, ord, point, title, explain, exam, "
        "keywords, priority, tags, exam_types, spoken, listen_script, tts_enabled, "
        "evidence_level, evidence_basis, evidence_sources) VALUES "
        "('2041001','204','204-10',0,'p','t','e','x','[]','○','[]','[]','','',0,"
        "'pending','','[]')")
    conn.executemany(
        "INSERT INTO card (card_id, point_id, ord, kind, card_type, question, answer, "
        "options, answer_points, analysis, unit_refs, payload) VALUES "
        "(?,?,?,'词汇','记忆','q','a','[]','[\"a\"]','x','[]',?)",
        [("c2041001-1", "2041001", 0, '{"word": "momentum"}'),
         ("c2041001-2", "2041001", 1, '{}')])
    conn.commit()
    return conn


def test_listen_queue_returns_payload(tmp_path):
    from app import service
    conn = _seed_word_db(tmp_path / "listen.db")
    items = service.custom_listen(conn, subjects=["204"], limit=5)["items"]
    conn.close()
    by_id = {i["card_id"]: i for i in items}
    assert by_id["c2041001-1"]["payload"] == {"word": "momentum"}
    assert by_id["c2041001-2"]["payload"] == {}


def test_queue_returns_payload(tmp_path):
    from app import service
    conn = _seed_word_db(tmp_path / "queue.db")
    items = service.custom_cards(conn, subjects=["204"], limit=5)["items"]
    conn.close()
    by_id = {i["card_id"]: i for i in items}
    assert by_id["c2041001-1"]["payload"] == {"word": "momentum"}
    assert by_id["c2041001-2"]["payload"] == {}
