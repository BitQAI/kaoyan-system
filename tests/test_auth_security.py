def test_login_rate_limit_locks_after_five(client):
    for _ in range(5):
        assert client.post("/api/login", json={"password": "bad"}).status_code == 401
    r = client.post("/api/login", json={"password": "bad"})
    assert r.status_code == 429
    assert "retry-after" in {k.lower() for k in r.headers}
    # 窗口期内正确密码也被锁
    assert client.post("/api/login", json={"password": "pw"}).status_code == 429


def test_cookie_secure_behind_https_proxy(client):
    r = client.post("/api/login", json={"password": "pw"},
                    headers={"X-Forwarded-Proto": "https"})
    assert r.status_code == 200
    assert "secure" in r.headers["set-cookie"].lower()


def test_cookie_not_secure_on_plain_http(client):
    r = client.post("/api/login", json={"password": "pw"})
    assert r.status_code == 200
    assert "secure" not in r.headers["set-cookie"].lower()
