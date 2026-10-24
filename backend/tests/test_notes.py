from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.notes import router as notes_router


def _client():
    app = FastAPI()
    app.include_router(notes_router)
    return TestClient(app)


def test_add_note(setup_db):
    from app.models import Lesson
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(Lesson(document_id=1, subject="语文", title="第1课", start_page=1, end_page=3))
    s.commit(); s.close()
    resp = _client().post("/api/notes", json={"lesson_id": 1, "author_role": "child", "content": "白鹭很常见反而被忽略", "anchor_text": "被人忘却了它的美"})
    assert resp.status_code == 200
    assert resp.json()["content"] == "白鹭很常见反而被忽略"


def test_list_notes_by_lesson(setup_db):
    c = _client()
    c.post("/api/notes", json={"lesson_id": 1, "author_role": "child", "content": "笔记A"})
    resp = c.get("/api/notes?lesson_id=1")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_ask_ai_returns_answer(setup_db):
    resp = _client().post("/api/ask", json={"lesson_id": 1, "question": "这段话是什么意思？", "context": "白鹭是一首精巧的诗"})
    assert resp.status_code == 200
    assert "answer" in resp.json()
