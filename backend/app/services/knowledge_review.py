"""知识点复习队列：按学习进度与掌握度准入。"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models import KnowledgeMastery, KnowledgePoint, KnowledgeReviewItem, Lesson


def in_progress_scope(db: Session, user_id: int, kp: KnowledgePoint) -> bool:
    if not kp.lesson_id:
        return False
    lesson = db.get(Lesson, kp.lesson_id)
    if not lesson:
        return False
    from .learning_progress import get_progress

    prog = get_progress(db, user_id, lesson.document_id, lesson.subject)
    if not prog or not prog.current_lesson_id:
        return False
    lessons = (
        db.query(Lesson)
        .filter_by(document_id=lesson.document_id, subject=lesson.subject)
        .order_by(Lesson.id)
        .all()
    )
    ids = [l.id for l in lessons]
    if lesson.id not in ids or prog.current_lesson_id not in ids:
        return False
    return ids.index(lesson.id) <= ids.index(prog.current_lesson_id)


def try_enroll(
    db: Session,
    user_id: int,
    knowledge_point_id: int,
    *,
    enrolled_by=None,
    source="mastery",
):
    from .bucket_guard import resolve_bucket_id
    from .mastery import GATE
    from .scheduler import INTERVALS

    bid = resolve_bucket_id(db, user_id, None)
    if bid is None:
        return None
    kp = db.get(KnowledgePoint, knowledge_point_id)
    if not kp or not in_progress_scope(db, user_id, kp):
        return None
    m = (
        db.query(KnowledgeMastery)
        .filter_by(user_id=user_id, knowledge_point_id=knowledge_point_id, bucket_id=bid)
        .first()
    )
    if not m or not (m.mastered or m.mastery >= GATE):
        return None
    row = (
        db.query(KnowledgeReviewItem)
        .filter_by(user_id=user_id, knowledge_point_id=knowledge_point_id, bucket_id=bid)
        .first()
    )
    if row and row.status in ("active", "paused"):
        return None
    now = datetime.utcnow()
    if row is None:
        row = KnowledgeReviewItem(
            user_id=user_id, knowledge_point_id=knowledge_point_id, bucket_id=bid
        )
        db.add(row)
    row.status = "active"
    row.interval_index = 0
    row.next_review_at = now + timedelta(days=INTERVALS[0])
    row.enrolled_by = enrolled_by
    row.enroll_source = source
    row.enrolled_at = now
    row.updated_at = now
    db.flush()
    return row
