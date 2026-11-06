from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.knowledge import router as knowledge_router
from app.routers.goals import router as goals_router
from conftest import auth_headers, make_account, bound_child_headers


def test_knowledge_crud(setup_db):
    from app.database import SessionLocal
    from app.models import Lesson, PdfDocument
    s = SessionLocal()
    admin = make_account(s, "adm_kg", "admin")
    doc = PdfDocument(filename="x.pdf", subject="语文", storage_path="")
    s.add(doc)
    s.flush()
    lesson = Lesson(
        document_id=doc.id,
        subject="语文",
        title="第1课",
        start_page=1,
        end_page=2,
        audit_status="approved",
    )
    s.add(lesson)
    s.flush()
    lid = lesson.id
    s.commit()
    ha = auth_headers(admin)

    app = FastAPI()
    app.include_router(knowledge_router)
    c = TestClient(app)
    # add
    r = c.post(
        "/api/knowledge",
        json={
            "subject": "语文",
            "category": "字词",
            "content": "形近字：似 vs 拟",
            "lesson_id": lid,
        },
        headers=ha,
    )
    assert r.status_code == 200
    pid = r.json()["id"]
    # list
    r = c.get("/api/knowledge?subject=语文", headers=ha)
    assert len(r.json()) == 1
    # delete
    r = c.delete(f"/api/knowledge/{pid}", headers=ha)
    assert r.json()["ok"] is True
    assert c.get("/api/knowledge?subject=语文", headers=ha).json() == []


def test_goals_list(setup_db):
    from app.database import SessionLocal
    s = SessionLocal()
    p = make_account(s, "p_gl", "parent")
    uid = make_account(s, "k_gl", "child", parent=p).id
    s.commit(); s.close()
    app = FastAPI()
    app.include_router(goals_router)
    c = TestClient(app)
    h = bound_child_headers(uid)
    c.post("/api/goals", json={"user_id": uid, "content": "掌握第3单元生词"}, headers=h)
    c.post("/api/goals", json={"user_id": uid, "content": "拼音知识巩固"}, headers=h)
    r = c.get(f"/api/goals?user_id={uid}", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 2
    # 倒序：最新在前
    assert r.json()[0]["content"] == "拼音知识巩固"
