from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.goals import router as goals_router
from conftest import make_user


def _client():
    app = FastAPI()
    app.include_router(goals_router)
    return TestClient(app)


def _seed_user():
    from app.database import SessionLocal
    s = SessionLocal()
    uid = make_user(s).id
    s.commit(); s.close()
    return uid


def test_create_goal(setup_db):
    uid = _seed_user()
    resp = _client().post("/api/goals", json={"user_id": uid, "content": "掌握第3单元生词"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_goal_assessment(setup_db):
    from app.models import Goal
    from app.database import SessionLocal
    s = SessionLocal()
    g = Goal(user_id=make_user(s).id, content="掌握第3单元生词", status="pending")
    s.add(g); s.commit(); gid = g.id; s.close()
    resp = _client().post(f"/api/goals/{gid}/assess", json={"correct": 4, "total": 5})
    assert resp.status_code == 200
    assert resp.json()["achieved"] is True
