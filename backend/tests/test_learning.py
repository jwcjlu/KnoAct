from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.learning import router as learning_router


def _client():
    app = FastAPI()
    app.include_router(learning_router)
    return TestClient(app)


def test_dictation_pick_words(setup_db):
    from app.models import Lesson, WordBank
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(Lesson(document_id=1, subject="语文", title="第1课", start_page=1, end_page=3, audit_status="approved"))
    s.flush()
    lid = s.query(Lesson).first().id
    s.add(WordBank(lesson_id=lid, subject="语文", word="徘徊", extra="pái huái"))
    s.add(WordBank(lesson_id=lid, subject="语文", word="矗立", extra="chù lì"))
    s.commit(); s.close()
    resp = _client().get("/api/dictation/words?user_id=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_dictation_grade(setup_db):
    c = _client()
    resp = c.post("/api/dictation/grade", json={"word": "徘徊", "answer": "徘徊"})
    assert resp.json()["correct"] is True
    resp = c.post("/api/dictation/grade", json={"word": "徘徊", "answer": "排回"})
    assert resp.json()["correct"] is False


def test_dictation_complete_awards_points(setup_db):
    from app.models import User
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(User(name="晨晨", role="child")); s.commit(); s.close()
    resp = _client().post("/api/dictation/complete", json={"user_id": 1, "correct": 5, "wrong": 1})
    assert resp.status_code == 200
    assert resp.json()["points_awarded"] > 0


def test_review_generate_questions(setup_db):
    from app.models import KnowledgePoint
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(KnowledgePoint(subject="英语", category="语法", content="动词第三人称单数加 s"))
    s.commit(); s.close()
    resp = _client().get("/api/review/questions?subject=英语")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_review_wrong_to_mistake(setup_db):
    resp = _client().post("/api/review/submit", json={"user_id": 1, "question": "go 的第三人称单数", "your_answer": "gos", "correct_answer": "goes", "source_type": "review"})
    assert resp.status_code == 200
    from app.models import Mistake
    from app.database import SessionLocal
    s = SessionLocal()
    assert s.query(Mistake).count() >= 1
    s.close()


def test_listening_material(setup_db):
    resp = _client().get("/api/listening/material?user_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data and "questions" in data


def test_reading_material(setup_db):
    from app.models import Text
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(Text(lesson_id=1, content="白鹭是一首精巧的诗。"))
    s.commit(); s.close()
    resp = _client().get("/api/reading/material?lesson_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data and "questions" in data
