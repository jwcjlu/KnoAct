import json

from pytest import approx

from app.database import SessionLocal
from app.models import User, KnowledgePoint, Lesson, PdfDocument, WordBank, KnowledgeMastery, WordMastery
from app.services.mastery import compute_mastery, grade_answer, is_mastered, GATE, record_attempt


def test_compute_mastery_empty_is_zero():
    assert compute_mastery([]) == 0.0


def test_compute_mastery_single_correct_is_capped_at_half():
    assert compute_mastery([True]) == 0.5


def test_compute_mastery_two_correct_capped_at_point_eight():
    assert compute_mastery([True, True]) == 0.8


def test_compute_mastery_recovers_after_mistakes():
    assert compute_mastery([False, True, True, True]) == approx(0.8)


def test_compute_mastery_three_plus_correct_reaches_gate():
    assert compute_mastery([True, True, True]) >= GATE


def test_grade_answer_choice_normalized():
    assert grade_answer("A", "A", "choice") is True
    assert grade_answer("a b", "ab", "choice") is True
    assert grade_answer("A", "B", "choice") is False


def test_grade_answer_short_exact_or_clearly_wrong():
    assert grade_answer("白鹭", "白鹭", "short") is True
    assert grade_answer("完全不同的答案", "白鹭", "short") is False


def _seed_kp():
    db = SessionLocal()
    for m in (KnowledgeMastery, WordMastery, WordBank, KnowledgePoint, Lesson, PdfDocument, User):
        db.query(m).delete()
    db.commit()
    u = User(name="孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="y.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l = Lesson(document_id=doc.id, subject="语文", title="第1课",
               start_page=1, end_page=1, extract_status="done", audit_status="approved")
    db.add(l); db.flush()
    kp = KnowledgePoint(subject="语文", category="字词", content="形近字辨析", lesson_id=l.id)
    db.add(kp); db.flush()
    wb = WordBank(lesson_id=l.id, subject="语文", word="白鹭", extra="pinyin")
    db.add(wb); db.flush()
    db.commit()
    return u.id, kp.id, wb.id


def test_record_attempt_knowledge_persists(setup_db):
    uid, kpid, wbid = _seed_kp()
    db = SessionLocal()
    m = record_attempt(db, uid, "knowledge", kpid, True)
    assert m == 0.5  # 首次答对封顶
    row = db.query(KnowledgeMastery).filter_by(user_id=uid, knowledge_point_id=kpid).first()
    assert row is not None
    assert row.mastery == 0.5
    assert row.mastered is False
    assert json.loads(row.attempts) == [True]
    db.close()


def test_record_attempt_word_reaches_gate_after_three(setup_db):
    uid, kpid, wbid = _seed_kp()
    db = SessionLocal()
    for _ in range(3):
        record_attempt(db, uid, "word", wbid, True)
    row = db.query(WordMastery).filter_by(user_id=uid, word_bank_id=wbid).first()
    assert row is not None
    assert row.mastery >= GATE
    assert len(json.loads(row.attempts)) == 3
    db.close()


def test_record_attempt_word_keeps_legacy_fields(setup_db):
    """词层要维护旧字段，供旧复习调度用。"""
    uid, kpid, wbid = _seed_kp()
    db = SessionLocal()
    record_attempt(db, uid, "word", wbid, True)
    record_attempt(db, uid, "word", wbid, False)
    row = db.query(WordMastery).filter_by(user_id=uid, word_bank_id=wbid).first()
    assert row.mistake_count == 1
    assert row.is_weak is True
    assert row.correct_count == 0  # 答错后清零
    db.close()
