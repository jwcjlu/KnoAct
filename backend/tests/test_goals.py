from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.goals import router as goals_router


def _client():
    app = FastAPI()
    app.include_router(goals_router)
    return TestClient(app)


def test_create_goal(setup_db):
    resp = _client().post("/api/goals", json={"user_id": 1, "content": "掌握第3单元生词"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_goal_assessment(setup_db):
    from app.models import Goal
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(Goal(user_id=1, content="掌握第3单元生词", status="pending")); s.commit(); s.close()
    resp = _client().post("/api/goals/1/assess", json={"correct": 4, "total": 5})
    assert resp.status_code == 200
    assert resp.json()["achieved"] is True
