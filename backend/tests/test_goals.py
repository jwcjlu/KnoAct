from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.goals import router as goals_router
from conftest import make_account, bound_child_headers


def _client():
    app = FastAPI()
    app.include_router(goals_router)
    return TestClient(app)


def _seed_user():
    from app.database import SessionLocal
    s = SessionLocal()
    p = make_account(s, "p_goal", "parent")
    u = make_account(s, "k_goal", "child", parent=p)
    s.commit()
    uid = u.id
    s.close()
    return uid


def test_create_goal(setup_db):
    uid = _seed_user()
    h = bound_child_headers(uid)
    resp = _client().post("/api/goals", json={"user_id": uid, "content": "掌握第3单元生词"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_goal_assessment(setup_db):
    from app.models import Goal
    from app.database import SessionLocal
    s = SessionLocal()
    p = make_account(s, "p_ga", "parent")
    uid = make_account(s, "k_ga", "child", parent=p).id
    g = Goal(user_id=uid, content="掌握第3单元生词", status="pending")
    s.add(g); s.commit(); gid = g.id; s.close()
    h = bound_child_headers(uid)
    resp = _client().post(f"/api/goals/{gid}/assess", json={"correct": 4, "total": 5}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["achieved"] is True
