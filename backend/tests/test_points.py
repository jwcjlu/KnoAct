from fastapi.testclient import TestClient
from app.main import app
from conftest import bound_child_headers
from app.database import SessionLocal


client = TestClient(app)


def test_get_points_balance(setup_db):
    from app.models import Point, User
    from app.services.bucket_service import ensure_bucket
    s = SessionLocal()
    parent = User(name="p", role="parent")
    s.add(parent); s.flush()
    u = User(name="kid", role="child", parent_id=parent.id)
    s.add(u); s.flush()
    uid = u.id
    bid = ensure_bucket(s, uid).id
    s.add(Point(user_id=uid, bucket_id=bid, delta=100, reason="听写")); s.commit(); s.close()
    h = bound_child_headers(uid)
    resp = client.get(f"/api/points/balance?user_id={uid}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["balance"] == 100


def test_redeem_deducts_points(setup_db):
    from app.models import Point, User
    from app.services.bucket_service import ensure_bucket
    s = SessionLocal()
    parent = User(name="p", role="parent")
    s.add(parent); s.flush()
    u = User(name="kid", role="child", parent_id=parent.id)
    s.add(u); s.flush()
    uid = u.id
    bid = ensure_bucket(s, uid).id
    s.add(Point(user_id=uid, bucket_id=bid, delta=300, reason="听写")); s.commit(); s.close()
    h = bound_child_headers(uid)
    resp = client.post("/api/points/redeem", json={"user_id": uid, "device": "tablet", "minutes": 30}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    balance = client.get(f"/api/points/balance?user_id={uid}", headers=h).json()["balance"]
    assert balance == 0


def test_redeem_without_bucket_insufficient(setup_db):
    from app.models import Point, User
    s = SessionLocal()
    parent = User(name="p", role="parent")
    s.add(parent); s.flush()
    u = User(name="kid", role="child", parent_id=parent.id)
    s.add(u); s.flush()
    uid = u.id
    s.add(Point(user_id=uid, bucket_id=None, delta=300, reason="历史遗留")); s.commit(); s.close()
    h = bound_child_headers(uid)
    resp = client.post("/api/points/redeem", json={"user_id": uid, "device": "tablet", "minutes": 30}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["success"] is False
