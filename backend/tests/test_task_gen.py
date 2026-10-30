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
                       next_review_at=datetime.utcnow() - timedelta(days=1), user_id=uid))
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


def test_gen_knowledge_content_has_question_fields():
    db = SessionLocal()
    uid, l1_id = _setup(db)
    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="knowledge").first()
    assert t is not None
    content = json.loads(t.content)
    assert len(content) >= 1
    p = content[0]
    # fake provider 下 question 为空字符串，但字段必须存在
    assert "question" in p and "answer" in p and "keywords" in p
    assert "id" in p and "content" in p
    db.close()


def test_dictation_picks_new_and_due_words():
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 第1课：白鹭、矗立 两个生词
    # 再建第2课，含 2 个生词，其中一个到期
    doc = db.query(PdfDocument).first()
    l2 = Lesson(document_id=doc.id, subject="语文", title="第2课", start_page=3, end_page=4,
                extract_status="done", audit_status="approved")
    db.add(l2); db.flush()
    db.add(WordBank(lesson_id=l2.id, subject="语文", word="旧词A", extra=""))
    wb_b = WordBank(lesson_id=l2.id, subject="语文", word="旧词B", extra="")
    db.add(wb_b); db.flush()
    db.add(WordMastery(word_bank_id=wb_b.id, is_weak=True,
                       next_review_at=datetime.utcnow() - timedelta(days=1), user_id=uid))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    assert t is not None
    words = json.loads(t.content)
    got = {w["word"] for w in words}
    # 新（当前进度课=第1课）应含白鹭、矗立；旧（到期）应含旧词B
    assert "白鹭" in got and "矗立" in got
    assert "旧词B" in got
    # 到期旧词只有1个，凑不满2个 → 不硬补，总数为 2(新) + 1(旧) = 3
    assert len(words) == 3
    db.close()


def test_dictation_isolates_due_words_across_users():
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 孩子A：第1课（白鹭、矗立）
    # 孩子B：一个第2课生词，带一条到期 WordMastery（属于B）
    other = User(name="别的孩子", role="child")
    db.add(other); db.flush()
    doc = db.query(PdfDocument).first()
    l2 = Lesson(document_id=doc.id, subject="语文", title="第2课", start_page=3, end_page=4,
                extract_status="done", audit_status="approved")
    db.add(l2); db.flush()
    wb_b = WordBank(lesson_id=l2.id, subject="语文", word="B的旧词", extra="")
    db.add(wb_b); db.flush()
    db.add(WordMastery(word_bank_id=wb_b.id, is_weak=True,
                       next_review_at=datetime.utcnow() - timedelta(days=1), user_id=other.id))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    assert t is not None
    got = {w["word"] for w in json.loads(t.content)}
    # A 的听写只含本课新词，绝不能混入 B 的到期旧词
    assert got == {"白鹭", "矗立"}
    db.close()
