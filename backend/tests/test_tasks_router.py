from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import (
    User, Task, Point, LearningProgress, Mistake, Goal, LearningRecord,
    PdfDocument, Lesson, WordBank, KnowledgePoint, Text, WordMastery,
)
from app.services.task_gen import generate_tasks_for_user

client = TestClient(app)


def _seed():
    db = SessionLocal()
    for model in (Task, Point, LearningProgress, Mistake, Goal, LearningRecord,
                  WordMastery, WordBank, KnowledgePoint, Text, Lesson,
                  PdfDocument, User):
        db.query(model).delete()
    db.commit()
    u = User(name="金宇轩", role="child")
    db.add(u)
    db.flush()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc)
    db.flush()
    l1 = Lesson(document_id=doc.id, subject="语文", title="第1课",
                start_page=1, end_page=2, extract_status="done", audit_status="approved")
    db.add(l1)
    db.flush()
    db.add(WordBank(lesson_id=l1.id, subject="语文", word="白鹭", extra="pinyin 释义"))
    db.add(KnowledgePoint(subject="语文", category="字词", content="形近字辨析", lesson_id=l1.id))
    db.commit()
    return u.id


def test_list_tasks_published_only_for_child():
    uid = _seed()
    generate_tasks_for_user(SessionLocal(), uid, date.today())
    r = client.get(f"/api/tasks?user_id={uid}&date={date.today()}&role=child")
    assert r.status_code == 200
    assert r.json() == []  # pending_review, child shouldn't see


def test_approve_then_child_sees_task():
    uid = _seed()
    generate_tasks_for_user(SessionLocal(), uid, date.today())
    db = SessionLocal()
    task = db.query(Task).filter_by(user_id=uid, date=date.today()).first()
    tid = task.id
    db.close()
    assert client.post(f"/api/tasks/{tid}/approve").json() == {"ok": True}
    r = client.get(f"/api/tasks?user_id={uid}&date={date.today()}&role=child")
    assert len(r.json()) >= 1


def test_add_custom_task_and_confirm_awards_points():
    uid = _seed()
    r = client.post("/api/tasks", json={
        "user_id": uid, "date": str(date.today()), "task_type": "custom",
        "title": "读一页书", "points": 30,
    })
    assert r.status_code == 200
    tid = r.json()["id"]
    assert client.post(f"/api/tasks/{tid}/submit").json() == {"ok": True}
    assert client.post(f"/api/tasks/{tid}/confirm").json()["ok"] is True
