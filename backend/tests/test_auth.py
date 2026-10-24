from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.auth import router as auth_router


def _client():
    app = FastAPI()
    app.include_router(auth_router)
    return TestClient(app)


def test_auth_login_returns_role(setup_db):
    from app.models import User
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(User(name="晨晨", role="child")); s.commit(); s.close()
    resp = _client().post("/api/auth/login", json={"name": "晨晨"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "child"


def test_auth_login_creates_new_user(setup_db):
    resp = _client().post("/api/auth/login", json={"name": "新孩子"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "child"
