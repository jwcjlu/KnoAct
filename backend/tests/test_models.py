from app import models  # noqa: F401  ensure all models registered on Base.metadata


def test_create_all_tables():
    from app.database import Base
    tables = set(Base.metadata.tables.keys())
    expected = {
        "users", "pdf_documents", "pdf_pages", "lessons", "textbooks",
        "learning_progress", "word_banks", "knowledge_points", "texts", "notes",
        "word_mastery", "mistakes", "learning_records", "points", "goals", "rewards", "model_config",
    }
    assert expected.issubset(tables)


def test_word_bank_roundtrip(db):
    from app.models import Lesson, WordBank
    lesson = Lesson(document_id=1, subject="语文", title="第1课", start_page=1, end_page=3)
    db.add(lesson)
    db.flush()
    db.add(WordBank(lesson_id=lesson.id, subject="语文", word="徘徊", extra="pái huái"))
    db.commit()
    got = db.query(WordBank).filter_by(word="徘徊").first()
    assert got.extra == "pái huái"
