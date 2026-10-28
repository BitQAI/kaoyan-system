import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db, importer  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def db_file(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("data") / "test.db"
    conn = db.connect(path)
    db.create_tables(conn)
    importer.import_all(conn)
    conn.close()
    return path


@pytest.fixture()
def conn(db_file):
    c = db.connect(db_file)
    yield c
    c.close()


@pytest.fixture()
def client(db_file, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", db_file)
    return TestClient(app)
