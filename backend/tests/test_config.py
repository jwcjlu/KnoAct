from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.config_router import router as config_router


def _client():
    app = FastAPI()
    app.include_router(config_router)
    return TestClient(app)


def test_set_and_get_config(setup_db):
    c = _client()
    resp = c.post("/api/config", json={"key": "ai_provider", "value": "deepseek"})
    assert resp.status_code == 200
    resp = c.get("/api/config")
    assert resp.json().get("ai_provider") == "deepseek"


def test_config_overwrite(setup_db):
    c = _client()
    c.post("/api/config", json={"key": "k", "value": "1"})
    c.post("/api/config", json={"key": "k", "value": "2"})
    assert c.get("/api/config").json()["k"] == "2"
