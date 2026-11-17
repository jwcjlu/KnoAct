from app.models import User, AnswerRecord
from app.services.answer_record import record_answer


def test_answer_record_fields(setup_db, db):
    child = User(name="晨晨", role="child")
    db.add(child); db.commit()
    r = record_answer(db, user_id=child.id, subject="英语", module="dictation",
                      question="apple", student_answer="apple", correct_answer="apple",
                      is_correct=True, difficulty="easy", duration_ms=3200,
                      source_type="word_bank", source_id=7)
    db.commit()
    got = db.query(AnswerRecord).filter_by(user_id=child.id).one()
    assert got.subject == "英语"
    assert got.module == "dictation"
    assert got.is_correct is True
    assert got.duration_ms == 3200
    assert got.source_type == "word_bank"
    assert got.source_id == 7
    assert got.created_at is not None
