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


def login(client, email, role):
    users = client.get("/api/auth/demo-users").get_json()
    user = next(u for u in users if u["email"] == email)
    resp = client.post("/api/auth/login", json={"user_id": user["id"], "role": role})
    assert resp.status_code == 200, resp.get_json()
    token = resp.get_json()["token"]
    return token, user["id"]


def auth_headers(token):
    return {"Authorization": "Bearer {}".format(token)}
