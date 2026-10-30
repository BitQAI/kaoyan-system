from app import config, db


def _first_card(conn):
    return conn.execute(
        "SELECT c.card_id, p.subject_id FROM card c JOIN point p ON p.id = c.point_id "
        "LIMIT 1").fetchone()


def test_audio_hit(client, conn, tmp_path, monkeypatch):
    row = _first_card(conn)
    target = tmp_path / row["subject_id"]
    target.mkdir()
    (target / f'{row["card_id"]}.mp3').write_bytes(b"ID3" + b"\x00" * 2048)
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)

    res = client.get(f'/api/audio/{row["card_id"]}')
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"
    assert res.headers["cache-control"].startswith("private")
    assert res.content.startswith(b"ID3")


def test_audio_missing_file(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    assert client.get("/api/audio/c8120001-1").status_code == 404


def test_audio_unknown_card(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    assert client.get("/api/audio/c9999999-9").status_code == 404


def test_audio_rejects_path_traversal(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    assert client.get("/api/audio/c..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_audio_requires_auth(client):
    saved = client.headers.get("Authorization")
    client.headers.pop("Authorization", None)
    try:
        assert client.get("/api/audio/c8120001-1").status_code == 401
    finally:
        client.headers["Authorization"] = saved


def test_audio_clip_hit(client, conn, tmp_path, monkeypatch):
    row = _first_card(conn)
    target = tmp_path / row["subject_id"]
    target.mkdir()
    (target / f'{row["card_id"]}-word.mp3').write_bytes(b"ID3clip")
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)

    res = client.get(f'/api/audio/{row["card_id"]}', params={"clip": "word"})
    assert res.status_code == 200
    assert res.content == b"ID3clip"


def test_audio_clip_missing(client, conn, tmp_path, monkeypatch):
    row = _first_card(conn)
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    res = client.get(f'/api/audio/{row["card_id"]}', params={"clip": "sentence"})
    assert res.status_code == 404


def test_audio_clip_invalid(client, conn, tmp_path, monkeypatch):
    row = _first_card(conn)
    target = tmp_path / row["subject_id"]
    target.mkdir()
    (target / "secret.mp3").write_bytes(b"ID3secret")
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    for bad in ("../../etc/passwd", "..%2F..%2Fsecret", "full"):
        res = client.get(f'/api/audio/{row["card_id"]}', params={"clip": bad})
        assert res.status_code == 404, bad


def test_audio_clip_keeps_default(client, conn, tmp_path, monkeypatch):
    row = _first_card(conn)
    target = tmp_path / row["subject_id"]
    target.mkdir()
    (target / f'{row["card_id"]}.mp3').write_bytes(b"ID3full")
    (target / f'{row["card_id"]}-word.mp3').write_bytes(b"ID3word")
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)

    res = client.get(f'/api/audio/{row["card_id"]}')
    assert res.content == b"ID3full"


def test_audio_dir_defaults_under_data():
    assert config.AUDIO_DIR.name == "audio"
