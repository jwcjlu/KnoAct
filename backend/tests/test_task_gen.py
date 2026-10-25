import json
from datetime import datetime, date, timedelta
from app.database import SessionLocal, Base, engine
from app.models import User, PdfDocument, Lesson, WordBank, KnowledgePoint, WordMastery, Text
from app.services.task_gen import generate_tasks_for_user, _current_lesson


def _setup(db):
    db.query(WordMastery).delete()
    db.query(WordBank).delete()
    db.query(KnowledgePoint).delete()
    db.query(Text).delete()
    db.query(Lesson).delete()
    db.query(PdfDocument).delete()
    db.query(User).delete()
    db.commit()
    u = User(name="测试孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l1 = Lesson(document_id=doc.id, subject="语文", title="第1课", start_page=1, end_page=2,
                extract_status="done", audit_status="approved")
    db.add(l1); db.flush()
    for w in ["白鹭", "矗立"]:
        db.add(WordBank(lesson_id=l1.id, subject="语文", word=w, extra="pinyin 释义"))
    db.add(KnowledgePoint(subject="语文", category="字词", content="形近字辨析", lesson_id=l1.id))
    db.add(Text(lesson_id=l1.id, content="白鹭是一首精巧的诗。"))
    db.commit()
    return u.id, l1.id


def test_current_lesson_matches_subject():
    db = SessionLocal()
    uid, l1 = _setup(db)
    lesson = _current_lesson(db, "语文", uid)
    assert lesson is not None and lesson.subject == "语文"
    db.close()


def test_generate_tasks_for_user_creates_three_types():
    db = SessionLocal()
    uid, l1 = _setup(db)
    generate_tasks_for_user(db, uid, date.today())
    from app.models import Task
    rows = db.query(Task).filter_by(user_id=uid, date=date.today()).all()
    types = {r.task_type for r in rows}
    assert "dictation" in types
    assert "knowledge" in types
    db.close()
