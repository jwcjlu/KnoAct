from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from conftest import auth_headers, make_account

client = TestClient(app)


def _parent_headers():
    db = SessionLocal()
    p = make_account(db, "bank_parent", "parent")
    headers = auth_headers(p)
    db.close()
    return headers


def test_create_bank(client, setup_db):
    h = _parent_headers()
    r = client.post("/api/banks", json={"title": "三年级数学期末卷", "subject": "数学", "grade": 3}, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] > 0


def test_list_banks(client, setup_db):
    h = _parent_headers()
    client.post("/api/banks", json={"title": "卷A", "subject": "数学"}, headers=h)
    r = client.get("/api/banks", headers=h)
    assert r.status_code == 200
    assert len(r.json()) >= 1
