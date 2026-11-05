from fastapi import FastAPI
from fastapi.testclient import TestClient
from conftest import auth_headers, make_account
from app.routers.config_router import router as config_router


def _client():
    app = FastAPI()
    app.include_router(config_router)
    return TestClient(app)


def test_set_and_get_config(setup_db, db):
    c = _client()
    h = auth_headers(make_account(db, "mama_one", "parent"))
    resp = c.post("/api/config", json={"key": "ai_provider", "value": "deepseek"}, headers=h)
    assert resp.status_code == 200
    resp = c.get("/api/config")
    assert resp.json().get("ai_provider") == "deepseek"


def test_config_overwrite(setup_db, db):
    c = _client()
    h = auth_headers(make_account(db, "root_one", "admin"))
    c.post("/api/config", json={"key": "k", "value": "1"}, headers=h)
    c.post("/api/config", json={"key": "k", "value": "2"}, headers=h)
    assert c.get("/api/config").json()["k"] == "2"


def test_set_config_requires_parent_or_admin(setup_db, db):
    c = _client()
    body = {"key": "k", "value": "1"}
    assert c.post("/api/config", json=body).status_code == 401
    kid = make_account(db, "kid_one", "child")
    assert c.post("/api/config", json=body, headers=auth_headers(kid)).status_code == 403
    assert c.get("/api/config").json() == {}
