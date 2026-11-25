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


def test_record_answer_persists_evidence_fields(db):
    from conftest import make_user

    child = make_user(db)
    row = record_answer(
        db,
        user_id=child.id,
        subject="语文",
        module="quiz",
        question="「月亮像一条小船」用了什么修辞？",
        student_answer="比喻",
        correct_answer="比喻",
        is_correct=True,
        source_type="quiz",
        source_id=None,
        evidence_text="弯弯的月亮像一条小船。",
        evidence_ok=True,
    )
    db.commit()

    saved = db.get(AnswerRecord, row.id)
    assert saved.evidence_text == "弯弯的月亮像一条小船。"
    assert saved.evidence_ok is True


def test_record_answer_evidence_defaults_to_empty(db):
    from conftest import make_user

    child = make_user(db)
    row = record_answer(
        db, user_id=child.id, subject="语文", module="quiz",
        question="q", student_answer="a", correct_answer="a", is_correct=True,
    )
    db.commit()

    saved = db.get(AnswerRecord, row.id)
    assert saved.evidence_text == ""
    assert saved.evidence_ok is None
