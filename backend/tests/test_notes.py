from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.notes import router as notes_router
from conftest import make_account, make_lesson, bound_child_headers


def _client():
    app = FastAPI()
    app.include_router(notes_router)
    return TestClient(app)


def _seed_bound_child_and_lesson():
    """孩子 + 课 + 绑定教材，返回 (lesson_id, uid, headers)。"""
    from app.database import SessionLocal
    from app.models import UserDocument
    s = SessionLocal()
    p = make_account(s, "p_nt", "parent")
    uid = make_account(s, "k_nt", "child", parent=p).id
    lesson = make_lesson(s)
    s.add(UserDocument(user_id=uid, document_id=lesson.document_id))
    s.commit()
    lid = lesson.id
    s.close()
    return lid, uid, bound_child_headers(uid)


def test_add_note(setup_db):
    lid, uid, h = _seed_bound_child_and_lesson()
    resp = _client().post(
        "/api/notes",
        json={
            "lesson_id": lid,
            "author_role": "child",
            "content": "白鹭很常见反而被忽略",
            "anchor_text": "被人忘却了它的美",
        },
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "白鹭很常见反而被忽略"


def test_list_notes_by_lesson(setup_db):
    lid, uid, h = _seed_bound_child_and_lesson()
    c = _client()
    c.post(
        "/api/notes",
        json={"lesson_id": lid, "author_role": "child", "content": "笔记A"},
        headers=h,
    )
    resp = c.get(f"/api/notes?lesson_id={lid}&user_id={uid}", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_ask_ai_returns_answer(setup_db):
    lid, uid, h = _seed_bound_child_and_lesson()
    resp = _client().post(
        "/api/ask",
        json={
            "lesson_id": lid,
            "question": "这段话是什么意思？",
            "context": "白鹭是一首精巧的诗",
        },
        headers=h,
    )
    assert resp.status_code == 200
    assert "answer" in resp.json()
