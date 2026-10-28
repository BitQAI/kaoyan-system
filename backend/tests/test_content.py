def test_health(client):
    body = client.get("/api/health").json()
    assert body["points"] == 538
    assert "ai_configured" in body


def test_manifest(client):
    body = client.get("/api/manifest").json()
    assert [s["id"] for s in body["subjects"]] == ["812", "315", "101", "204"]
    assert len(body["points"]) == 538
    assert sum(len(s["chapters"]) for s in body["subjects"]) == 74


def test_chapters_and_points(client):
    chs = client.get("/api/subjects/812/chapters").json()["items"]
    assert chs and chs[0]["weight_basis"] in {"官方", "推算", "人工估计"}
    pts = client.get(f"/api/chapters/{chs[0]['id']}/points").json()["items"]
    assert pts and "title" in pts[0]


def test_point_detail_shape(client):
    p = client.get("/api/points/8120001").json()
    assert p["id"] == "8120001"
    assert p["units"] and p["cards"] and p["media"]
    assert set(p["relations"]) == {"prerequisite", "related", "confusable"}
    assert p["exam_evidence"]["level"] in {"verified", "inferred", "pending"}
    assert p["listen"]["script"]


def test_point_detail_sanitizes_svg(client, conn):
    conn.execute(
        "UPDATE media SET svg = ? WHERE point_id = '8120001'",
        ('<svg viewBox="0 0 10 10" onload="alert(1)">'
         '<script>alert(2)</script>'
         '<foreignObject><body xmlns="http://www.w3.org/1999/xhtml">x</body>'
         '</foreignObject><rect width="5" height="5"/></svg>',))
    conn.commit()
    svg = client.get("/api/points/8120001").json()["media"][0]["svg"]
    assert "<script" not in svg
    assert "onload" not in svg
    assert "foreignObject" not in svg
    assert "<rect" in svg


def test_source_resolves_full_paragraph(client):
    body = client.get("/api/points/8120001/source").json()
    assert body["note"] == ""
    assert len(body["text"]) > 20


def test_syllabus_point_falls_back(client):
    row = client.get("/api/manifest").json()["points"]
    pid = next(p["id"] for p in row if p["subject_id"] == "812")
    body = client.get(f"/api/points/{pid}/source").json()
    assert "note" in body


def test_missing_point_404(client):
    assert client.get("/api/points/nope").status_code == 404
