from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.points import router as points_router


def _client():
    app = FastAPI()
    app.include_router(points_router)
    return TestClient(app)


def test_get_points_balance(setup_db):
    from app.models import Point
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(Point(user_id=1, delta=100, reason="听写")); s.commit(); s.close()
    resp = _client().get("/api/points/balance?user_id=1")
    assert resp.status_code == 200
    assert resp.json()["balance"] == 100


def test_redeem_deducts_points(setup_db):
    from app.models import Point
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(Point(user_id=1, delta=300, reason="听写")); s.commit(); s.close()
    c = _client()
    resp = c.post("/api/points/redeem", json={"user_id": 1, "device": "tablet", "minutes": 30})
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    balance = c.get("/api/points/balance?user_id=1").json()["balance"]
    assert balance == 0
