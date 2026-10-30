from app import importer


def test_counts_match_source(db_file):
    from app import db
    conn = db.connect(db_file)
    got = importer.counts(conn)
    want = importer.expected_counts()
    conn.close()
    assert got == want


def test_import_is_idempotent(db_file):
    from app import db
    conn = db.connect(db_file)
    first = importer.counts(conn)
    importer.import_all(conn)
    second = importer.counts(conn)
    conn.close()
    assert first == second


def test_relation_names_filled(conn):
    row = conn.execute(
        "SELECT name FROM relation WHERE point_id='8120001' AND kind='related' "
        "ORDER BY idx LIMIT 1").fetchone()
    assert row is not None
    assert row["name"]


def test_all_cards_have_answer_points(conn):
    missing = conn.execute(
        "SELECT COUNT(*) FROM card WHERE answer_points IN ('', '[]')").fetchone()[0]
    assert missing == 0


def test_evidence_levels(conn):
    rows = dict(conn.execute(
        "SELECT evidence_level, COUNT(*) FROM point GROUP BY evidence_level").fetchall())
    assert rows == {"verified": 456, "inferred": 82}


def test_card_payload_imports(tmp_path):
    import json
    from app import db
    conn = db.connect(tmp_path / "payload.db")
    db.create_tables(conn)
    importer._insert_cards(conn, {"id": "2041001", "cards": [{
        "card_id": "c2041001-1", "kind": "词汇", "card_type": "记忆",
        "question": "q", "answer": "a", "analysis": "x" * 40,
        "answer_points": ["a", "b"], "unit_refs": [1],
        "payload": {"word": "momentum"},
    }]})
    row = conn.execute(
        "SELECT payload FROM card WHERE card_id='c2041001-1'").fetchone()
    conn.close()
    assert json.loads(row["payload"]) == {"word": "momentum"}


def test_card_payload_defaults_empty(tmp_path):
    import json
    from app import db
    conn = db.connect(tmp_path / "payload_empty.db")
    db.create_tables(conn)
    importer._insert_cards(conn, {"id": "2041001", "cards": [{
        "card_id": "c2041001-2", "kind": "词汇", "card_type": "记忆",
        "question": "q", "answer": "a", "analysis": "x" * 40,
        "answer_points": ["a", "b"], "unit_refs": [1],
    }]})
    row = conn.execute(
        "SELECT payload FROM card WHERE card_id='c2041001-2'").fetchone()
    conn.close()
    assert json.loads(row["payload"]) == {}
