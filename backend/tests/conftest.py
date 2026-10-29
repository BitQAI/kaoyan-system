import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import auth, config, db, importer  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def db_file(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("data") / "test.db"
    conn = db.connect(path)
    db.create_tables(conn)
    importer.import_all(conn)
    conn.close()
    return path


@pytest.fixture(scope="session")
def credentials(db_file):
    conn = db.connect(db_file)
    created = auth.ensure_credentials(conn)
    conn.close()
    assert created, "首次初始化应返回明文账号密码"
    return created


@pytest.fixture()
def conn(db_file, credentials):
    c = db.connect(db_file)
    yield c
    c.close()


@pytest.fixture()
def client(db_file, credentials, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", db_file)
    c = TestClient(app)
    res = c.post("/api/auth/login", json={
        "username": credentials["user"], "password": credentials["password"]})
    assert res.status_code == 200, res.text
    c.headers.update({"Authorization": f"Bearer {res.json()['token']}"})
    return c


@pytest.fixture()
def anon_client(db_file, monkeypatch):
    """未登录的客户端，用来验证鉴权。"""
    monkeypatch.setattr(config, "DB_PATH", db_file)
    return TestClient(app)
