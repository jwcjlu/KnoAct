from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.points import router as points_router
from conftest import make_user


def _client():
    app = FastAPI()
    app.include_router(points_router)
    return TestClient(app)


def test_get_points_balance(setup_db):
    from app.models import Point
    from app.database import SessionLocal
    from app.services.bucket_service import ensure_bucket
    s = SessionLocal()
    uid = make_user(s).id
    bid = ensure_bucket(s, uid).id
    s.add(Point(user_id=uid, bucket_id=bid, delta=100, reason="听写")); s.commit(); s.close()
    resp = _client().get(f"/api/points/balance?user_id={uid}")
    assert resp.status_code == 200
    assert resp.json()["balance"] == 100


def test_redeem_deducts_points(setup_db):
    from app.models import Point
    from app.database import SessionLocal
    s = SessionLocal()
    uid = make_user(s).id
    s.add(Point(user_id=uid, delta=300, reason="听写")); s.commit(); s.close()
    c = _client()
    resp = c.post("/api/points/redeem", json={"user_id": uid, "device": "tablet", "minutes": 30})
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    balance = c.get(f"/api/points/balance?user_id={uid}").json()["balance"]
    assert balance == 0
