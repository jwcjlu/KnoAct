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


def enroll_due_to_progress(
    db: Session,
    user_id: int,
    document_id: int | None,
    subject: str,
    *,
    old_lesson_id: int | None,
    new_lesson_id: int | None,
    enrolled_by=None,
) -> int:
    """进度前推时，为新纳入进度范围的已掌握知识点补入复习队列（不后退撤队）。"""
    if new_lesson_id is None:
        return 0
    q = db.query(Lesson).filter(Lesson.subject == subject)
    if document_id is not None:
        q = q.filter(Lesson.document_id == document_id)
    lessons = q.order_by(Lesson.id).all()
    ids = [l.id for l in lessons]
    if new_lesson_id not in ids:
        return 0
    new_idx = ids.index(new_lesson_id)
    old_idx = ids.index(old_lesson_id) if old_lesson_id in ids else -1
    if new_idx < old_idx:
        return 0
    if old_lesson_id is None or old_lesson_id not in ids:
        lesson_ids = ids[: new_idx + 1]
    else:
        lesson_ids = ids[old_idx + 1 : new_idx + 1]
    if not lesson_ids:
        return 0
    kps = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.lesson_id.in_(lesson_ids))
        .all()
    )
    n = 0
    for kp in kps:
        if try_enroll(
            db,
            user_id,
            kp.id,
            enrolled_by=enrolled_by,
            source="progress_adjust",
        ):
            n += 1
    return n


def apply_review_result(db: Session, item: KnowledgeReviewItem, result: str) -> KnowledgeReviewItem:
    """根据三档自评更新 SRS 间隔（remember / fuzzy / forgot）。"""
    from .scheduler import INTERVALS

    now = datetime.utcnow()
    if item.last_result and item.updated_at and item.updated_at.date() == now.date():
        return item
    i = item.interval_index or 0
    if result == "remember":
        i = min(i + 1, len(INTERVALS) - 1)
        item.next_review_at = now + timedelta(days=INTERVALS[i])
    elif result == "fuzzy":
        item.next_review_at = now + timedelta(days=INTERVALS[i])
    else:
        i = 0
        item.next_review_at = now + timedelta(days=INTERVALS[0])
    item.interval_index = i
    item.last_result = result
    item.updated_at = now
    db.flush()
    return item
