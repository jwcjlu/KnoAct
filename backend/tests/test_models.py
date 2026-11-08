from app import models  # noqa: F401  ensure all models registered on Base.metadata
from conftest import make_lesson, make_user
from app.models import Question, QuestionBank, ReadingPassage
from sqlalchemy import inspect


def test_question_new_columns():
    cols = {c.name for c in inspect(Question).columns}
    for name in ("answer_json", "options", "analysis", "difficulty", "tags",
                 "qtype_category", "bank_id"):
        assert name in cols, f"Question 缺列 {name}"


def test_question_lesson_id_nullable():
    assert Question.__table__.c.lesson_id.nullable is True


def test_question_bank_table():
    cols = {c.name for c in inspect(QuestionBank).columns}
    for name in ("user_id", "title", "subject", "grade", "tags", "source", "status"):
        assert name in cols


def test_create_all_tables():
    from app.database import Base
    tables = set(Base.metadata.tables.keys())
    expected = {
        "users", "pdf_documents", "pdf_pages", "lessons", "textbooks",
        "learning_progress", "word_banks", "knowledge_points", "texts", "notes",
        "word_mastery", "mistakes", "learning_records", "points", "goals", "rewards",         "model_config",
        "reading_passages",
    }
    assert expected.issubset(tables)


def test_word_bank_roundtrip(db):
    from app.models import WordBank
    lesson = make_lesson(db)
    db.add(WordBank(lesson_id=lesson.id, subject="语文", word="徘徊", extra="pái huái"))
    db.commit()
    got = db.query(WordBank).filter_by(word="徘徊").first()
    assert got.extra == "pái huái"


def test_question_has_new_fields():
    from app.database import SessionLocal
    from app.models import Question
    db = SessionLocal()
    q = Question(lesson_id=make_lesson(db).id, qtype="knowledge", question="测试题",
                 subject="语文", status="pending", extra='{"keywords":["a"]}', task_type="knowledge")
    db.add(q); db.flush()
    assert q.subject == "语文"
    assert q.status == "pending"
    assert q.extra == '{"keywords":["a"]}'
    assert q.task_type == "knowledge"
    db.close()


def test_reading_passage_table():
    cols = {c.name for c in inspect(ReadingPassage).columns}
    for name in ("user_id", "bank_id", "subject", "title", "content", "grade", "status", "created_at"):
        assert name in cols, f"ReadingPassage 缺列 {name}"
    assert ReadingPassage.__table__.c.bank_id.nullable is True
    assert ReadingPassage.__table__.c.grade.nullable is True


def test_question_passage_id_nullable():
    assert "passage_id" in {c.name for c in inspect(Question).columns}
    assert Question.__table__.c.passage_id.nullable is True


def test_reading_passage_roundtrip(db):
    parent = make_user(db, name="rp_parent", role="parent")
    p = ReadingPassage(
        user_id=parent.id, subject="语文", title="春天", content="春天来了。",
        status="pending",
    )
    db.add(p)
    db.flush()
    q = Question(
        passage_id=p.id, qtype="short_answer", qtype_category="subjective",
        question="写了什么季节？", answer="春天", status="pending",
    )
    db.add(q)
    db.commit()
    got = db.get(ReadingPassage, p.id)
    assert got.content == "春天来了。"
    assert db.get(Question, q.id).passage_id == p.id
