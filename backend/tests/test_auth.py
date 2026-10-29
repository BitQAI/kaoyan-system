from app import auth


def test_requires_login(anon_client):
    assert anon_client.get("/api/manifest").status_code == 401
    assert anon_client.get("/api/health").status_code == 200


def test_wrong_password_rejected(anon_client, credentials):
    res = anon_client.post("/api/auth/login", json={
        "username": credentials["user"], "password": "wrong"})
    assert res.status_code == 401


def test_login_and_me(anon_client, credentials):
    res = anon_client.post("/api/auth/login", json={
        "username": credentials["user"], "password": credentials["password"],
        "remember": True})
    assert res.status_code == 200
    token = res.json()["token"]
    me = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["user"] == credentials["user"]


def test_bad_token_rejected(anon_client):
    res = anon_client.get("/api/manifest", headers={"Authorization": "Bearer nope"})
    assert res.status_code == 401


def test_token_expiry(conn):
    token = auth.issue_token(conn, "kaoyan", remember=False)
    assert auth.verify_token(conn, token)
    assert not auth.verify_token(conn, token + "x")


def test_change_password_invalidates_old_token(tmp_path):
    """改密会换私钥，旧令牌全部失效；用独立库跑，避免污染共享测试库。"""
    from app import db

    conn = db.connect(tmp_path / "auth.db")
    db.create_tables(conn)
    created = auth.ensure_credentials(conn)
    old = auth.issue_token(conn, created["user"], True)
    assert auth.change_password(conn, created["user"], created["password"], "newpass123")
    assert auth.verify_token(conn, old) is None
    assert auth.verify_password(conn, created["user"], "newpass123")
    conn.close()
