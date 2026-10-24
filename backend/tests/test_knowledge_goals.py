from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.knowledge import router as knowledge_router
from app.routers.goals import router as goals_router


def test_knowledge_crud(setup_db):
    app = FastAPI()
    app.include_router(knowledge_router)
    c = TestClient(app)
    # add
    r = c.post("/api/knowledge", json={"subject": "语文", "category": "字词", "content": "形近字：似 vs 拟"})
    assert r.status_code == 200
    pid = r.json()["id"]
    # list
    r = c.get("/api/knowledge?subject=语文")
    assert len(r.json()) == 1
    # delete
    r = c.delete(f"/api/knowledge/{pid}")
    assert r.json()["ok"] is True
    assert c.get("/api/knowledge?subject=语文").json() == []


def test_goals_list(setup_db):
    app = FastAPI()
    app.include_router(goals_router)
    c = TestClient(app)
    c.post("/api/goals", json={"user_id": 1, "content": "掌握第3单元生词"})
    c.post("/api/goals", json={"user_id": 1, "content": "拼音知识巩固"})
    r = c.get("/api/goals?user_id=1")
    assert r.status_code == 200
    assert len(r.json()) == 2
    # 倒序：最新在前
    assert r.json()[0]["content"] == "拼音知识巩固"
