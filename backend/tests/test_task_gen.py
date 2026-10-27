import json
from datetime import datetime, date, timedelta
from app.database import SessionLocal, Base, engine
from app.models import User, PdfDocument, Lesson, WordBank, KnowledgePoint, WordMastery, Text, Task
from app.services.task_gen import generate_tasks_for_user, _current_lesson


def _setup(db):
    db.query(WordMastery).delete()
    db.query(WordBank).delete()
    db.query(KnowledgePoint).delete()
    db.query(Text).delete()
    db.query(Lesson).delete()
    db.query(PdfDocument).delete()
    db.query(Task).delete()
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


def test_generate_tasks_creates_dictation_and_knowledge_and_is_idempotent():
    db = SessionLocal()
    uid, l1 = _setup(db)
    generate_tasks_for_user(db, uid, date.today())
    rows = db.query(Task).filter_by(user_id=uid, date=date.today()).all()
    types = {r.task_type for r in rows}
    assert "dictation" in types
    assert "knowledge" in types

    before = db.query(Task).filter_by(user_id=uid, date=date.today()).count()
    generate_tasks_for_user(db, uid, date.today())  # 第二次调用应幂等，不新增行
    after = db.query(Task).filter_by(user_id=uid, date=date.today()).count()
    assert after == before
    db.close()


def test_generate_tasks_creates_review_when_word_is_due():
    db = SessionLocal()
    uid, l1_id = _setup(db)
    # 挑一个本课生词，造一条到期待复习记录
    wb = db.query(WordBank).filter_by(lesson_id=l1_id).first()
    db.add(WordMastery(word_bank_id=wb.id, is_weak=True,
                       next_review_at=datetime.utcnow() - timedelta(days=1)))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    types = {r.task_type for r in db.query(Task).filter_by(user_id=uid, date=date.today()).all()}
    assert "review" in types
    db.close()


def _setup_english(db):
    db.query(WordMastery).delete()
    db.query(WordBank).delete()
    db.query(KnowledgePoint).delete()
    db.query(Text).delete()
    db.query(Lesson).delete()
    db.query(PdfDocument).delete()
    db.query(Task).delete()
    db.query(User).delete()
    db.commit()
    u = User(name="测试孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="英语.pdf", subject="英语", storage_path="")
    db.add(doc); db.flush()
    l1 = Lesson(document_id=doc.id, subject="英语", title="Unit 1", start_page=1, end_page=2,
                extract_status="done", audit_status="approved")
    db.add(l1); db.flush()
    for w in ["apple", "banana"]:
        db.add(WordBank(lesson_id=l1.id, subject="英语", word=w, extra="释义"))
    db.add(KnowledgePoint(subject="英语", category="词汇", content="颜色词", lesson_id=l1.id))
    db.commit()
    return u.id, l1.id


def test_generate_tasks_creates_listening_for_english():
    db = SessionLocal()
    uid, l1 = _setup_english(db)
    generate_tasks_for_user(db, uid, date.today())
    listening = db.query(Task).filter_by(
        user_id=uid, subject="英语", date=date.today(), task_type="listening").all()
    assert len(listening) == 1
    content = json.loads(listening[0].content)
    assert "dialogue" in content and "question" in content and "answer" in content
    db.close()


def test_generate_tasks_no_lesson_produces_no_tasks():
    db = SessionLocal()
    u = User(name="无课孩子", role="child")
    db.add(u); db.flush()
    uid = u.id
    db.commit()

    generate_tasks_for_user(db, uid, date.today())  # 两科均无课，不应抛异常
    assert db.query(Task).filter_by(user_id=uid, date=date.today()).count() == 0
    db.close()
