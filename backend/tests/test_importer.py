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
