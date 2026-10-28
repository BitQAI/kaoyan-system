from app import search


def test_trigram_chinese_substring(conn):
    got = search.search(conn, "生命活动")
    assert got["points"]
    assert got["cards"]


def test_results_grouped(conn):
    got = search.search(conn, "光合作用")
    assert set(got) == {"points", "cards"}
    for item in got["points"]:
        assert {"id", "title", "point", "priority"} <= set(item)


def test_short_query_falls_back_to_like(conn):
    got = search.search(conn, "细胞")
    assert got["points"], "两字查询应回落到 LIKE"


def test_subject_filter(conn):
    got = search.search(conn, "植物", sid="315")
    assert all(p["subject_id"] == "315" for p in got["points"])


def test_empty_query(conn):
    assert search.search(conn, "  ") == {"points": [], "cards": []}


def test_limit_clamped(conn):
    got = search.search(conn, "植物", limit=500)
    assert len(got["points"]) <= 50
