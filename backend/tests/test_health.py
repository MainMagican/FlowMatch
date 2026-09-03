import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def client(monkeypatch):
    db_fd, db_path = tempfile.mkstemp()
    monkeypatch.setenv("FLOWMATCH_DB_PATH", db_path)
    import app.config as config
    config.DB_PATH = db_path
    import app.database as database
    database.DB_PATH = db_path
    from app.main import create_app
    flask_app = create_app()
    flask_app.testing = True
    with flask_app.test_client() as c:
        yield c
    os.close(db_fd)
    os.unlink(db_path)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
