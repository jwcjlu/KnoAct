# backend/tests/test_knowledge_review.py
from datetime import datetime, timedelta

from app.models import KnowledgeMastery, KnowledgePoint, KnowledgeReviewItem, LearningProgress
from app.services.bucket_service import ensure_bucket
from app.services.knowledge_review import enroll_due_to_progress, try_enroll
from app.services.scheduler import INTERVALS
from conftest import make_document, make_lesson, make_user


def _kp_on_lesson(db, lesson, content="知识点"):
    kp = KnowledgePoint(
        subject=lesson.subject, category="字词", content=content, lesson_id=lesson.id
    )
    db.add(kp)
    db.flush()
    return kp


def _progress(db, user_id, document_id, subject, current_lesson_id):
    p = LearningProgress(
        user_id=user_id,
        document_id=document_id,
        subject=subject,
        current_lesson_id=current_lesson_id,
    )
    db.add(p)
    db.flush()
    return p


def _mastery(db, user_id, knowledge_point_id, bucket_id, *, mastery=0.95, mastered=True):
    m = KnowledgeMastery(
        user_id=user_id,
        knowledge_point_id=knowledge_point_id,
        bucket_id=bucket_id,
        mastery=mastery,
        mastered=mastered,
    )
    db.add(m)
    db.flush()
    return m


def test_knowledge_review_item_columns():
    cols = {c.name for c in KnowledgeReviewItem.__table__.columns}
    for name in (
        "id", "user_id", "knowledge_point_id", "bucket_id",
        "enrolled_by", "enroll_source", "enrolled_at",
        "status", "interval_index", "next_review_at",
        "last_result", "updated_at",
    ):
        assert name in cols, f"缺列 {name}"


def test_knowledge_review_item_unique_user_kp_bucket():
    # 至少有一对 (user_id, knowledge_point_id, bucket_id) 唯一约束
    assert any(
        set(c.name for c in u.columns) >= {"user_id", "knowledge_point_id", "bucket_id"}
        for u in KnowledgeReviewItem.__table__.constraints
        if u.__class__.__name__ == "UniqueConstraint"
    )


def test_try_enroll_requires_mastery_and_progress(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson_a = make_lesson(db, subject="语文", title="第1课", document=doc)
    kp = _kp_on_lesson(db, lesson_a)
    _progress(db, user.id, doc.id, "语文", lesson_a.id)
    ensure_bucket(db, user.id)
    assert try_enroll(db, user.id, kp.id) is None


def test_try_enroll_skips_ahead_of_progress(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson_a = make_lesson(db, subject="语文", title="第1课", document=doc)
    lesson_b = make_lesson(db, subject="语文", title="第2课", document=doc)
    kp_b = _kp_on_lesson(db, lesson_b)
    _progress(db, user.id, doc.id, "语文", lesson_a.id)
    bid = ensure_bucket(db, user.id).id
    _mastery(db, user.id, kp_b.id, bid)
    assert try_enroll(db, user.id, kp_b.id) is None


def test_try_enroll_success_when_mastered_in_scope(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson_a = make_lesson(db, subject="语文", title="第1课", document=doc)
    lesson_b = make_lesson(db, subject="语文", title="第2课", document=doc)
    kp_a = _kp_on_lesson(db, lesson_a)
    _progress(db, user.id, doc.id, "语文", lesson_b.id)
    bid = ensure_bucket(db, user.id).id
    _mastery(db, user.id, kp_a.id, bid)
    before = datetime.utcnow()
    row = try_enroll(db, user.id, kp_a.id, enrolled_by=user.id, source="mastery")
    after = datetime.utcnow()
    assert row is not None
    assert row.status == "active"
    assert row.interval_index == 0
    assert row.bucket_id == bid
    assert row.enroll_source == "mastery"
    expected = before + timedelta(days=INTERVALS[0])
    assert row.next_review_at >= expected - timedelta(seconds=2)
    assert row.next_review_at <= after + timedelta(days=INTERVALS[0]) + timedelta(seconds=2)


def test_try_enroll_returns_none_when_already_active(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson = make_lesson(db, subject="语文", title="第1课", document=doc)
    kp = _kp_on_lesson(db, lesson)
    _progress(db, user.id, doc.id, "语文", lesson.id)
    bid = ensure_bucket(db, user.id).id
    _mastery(db, user.id, kp.id, bid)
    first = try_enroll(db, user.id, kp.id)
    assert first is not None
    assert try_enroll(db, user.id, kp.id) is None


def test_progress_forward_enrolls_mastered_in_new_range(db):
    user = make_user(db)
    parent = make_user(db)
    doc = make_document(db, subject="语文")
    lesson_a = make_lesson(db, subject="语文", title="第1课", document=doc)
    lesson_b = make_lesson(db, subject="语文", title="第2课", document=doc)
    kp_b = _kp_on_lesson(db, lesson_b)
    _progress(db, user.id, doc.id, "语文", lesson_b.id)
    bid = ensure_bucket(db, user.id).id
    _mastery(db, user.id, kp_b.id, bid)
    n = enroll_due_to_progress(
        db,
        user.id,
        doc.id,
        "语文",
        old_lesson_id=lesson_a.id,
        new_lesson_id=lesson_b.id,
        enrolled_by=parent.id,
    )
    assert n == 1
    row = (
        db.query(KnowledgeReviewItem)
        .filter_by(user_id=user.id, knowledge_point_id=kp_b.id, bucket_id=bid)
        .first()
    )
    assert row is not None
    assert row.status == "active"
    assert row.enroll_source == "progress_adjust"
    assert row.enrolled_by == parent.id


def test_progress_backward_does_not_remove(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson_a = make_lesson(db, subject="语文", title="第1课", document=doc)
    lesson_b = make_lesson(db, subject="语文", title="第2课", document=doc)
    kp_a = _kp_on_lesson(db, lesson_a)
    _progress(db, user.id, doc.id, "语文", lesson_a.id)
    bid = ensure_bucket(db, user.id).id
    _mastery(db, user.id, kp_a.id, bid)
    row = try_enroll(db, user.id, kp_a.id, source="mastery")
    assert row is not None
    n = enroll_due_to_progress(
        db,
        user.id,
        doc.id,
        "语文",
        old_lesson_id=lesson_b.id,
        new_lesson_id=lesson_a.id,
        enrolled_by=user.id,
    )
    assert n == 0
    still = (
        db.query(KnowledgeReviewItem)
        .filter_by(user_id=user.id, knowledge_point_id=kp_a.id, bucket_id=bid)
        .first()
    )
    assert still is not None
    assert still.status == "active"
