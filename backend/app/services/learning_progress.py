"""学习进度的统一读写：按「孩子 + 教材」定位，兼容无 document_id 的老记录。

原来 LearningProgress 是 (user_id, subject) 唯一，一个学科只有一条进度，
同时学两本语文教材时会互相覆盖。现在改为 (user_id, document_id)，
这里把「取/建/推进」都收在一处，避免各处 filter_by 写错。
"""
from sqlalchemy.orm import Session

from ..models import LearningProgress, Lesson


def get_progress(db: Session, user_id: int, document_id: int | None,
                 subject: str | None = None) -> LearningProgress | None:
    """取某孩子在某本教材上的进度。

    `document_id` 为 None 时退化为「按学科取第一条」——兼容老数据与
    「不知道该属于哪本书」的调用方。
    """
    q = db.query(LearningProgress).filter_by(user_id=user_id)
    if document_id is not None:
        row = q.filter_by(document_id=document_id).first()
        if row is not None:
            return row
        # 还没有这本书的记录：如果有该学科的老记录（document_id 为空），复用它
        if subject:
            return q.filter(LearningProgress.document_id.is_(None),
                            LearningProgress.subject == subject).first()
        return None
    if subject:
        return q.filter_by(subject=subject).first()
    return q.first()


def ensure_progress(db: Session, user_id: int, document_id: int | None,
                    subject: str) -> LearningProgress:
    """取或新建（不 commit）。"""
    row = get_progress(db, user_id, document_id, subject)
    if row is not None:
        # 老记录首次被「认领」到某本书时，补上 document_id
        if document_id is not None and row.document_id is None:
            row.document_id = document_id
            row.subject = subject
        return row
    row = LearningProgress(user_id=user_id, document_id=document_id,
                           subject=subject, current_lesson_id=None)
    db.add(row)
    db.flush()
    return row


def advance_lesson(db: Session, user_id: int, document_id: int | None,
                   subject: str) -> LearningProgress:
    """推进到该教材的下一课（不 commit）。"""
    row = ensure_progress(db, user_id, document_id, subject)
    q = db.query(Lesson).filter(Lesson.subject == subject)
    if document_id is not None:
        q = q.filter(Lesson.document_id == document_id)
    lessons = q.order_by(Lesson.id).all()
    old_lesson_id = row.current_lesson_id
    if lessons:
        ids = [l.id for l in lessons]
        cur = row.current_lesson_id
        if cur in ids:
            idx = ids.index(cur)
            row.current_lesson_id = ids[idx + 1] if idx + 1 < len(ids) else ids[-1]
        else:
            row.current_lesson_id = ids[0]
    from .knowledge_review import enroll_due_to_progress

    enroll_due_to_progress(
        db,
        user_id,
        document_id,
        subject,
        old_lesson_id=old_lesson_id,
        new_lesson_id=row.current_lesson_id,
        enrolled_by=None,
    )
    return row


def lesson_index(db: Session, lesson: Lesson | None) -> tuple[int, int]:
    """返回 (当前课序号, 该书该科总课数)，1-based。"""
    if lesson is None:
        return 0, 0
    lessons = (db.query(Lesson)
               .filter(Lesson.subject == lesson.subject,
                       Lesson.document_id == lesson.document_id)
               .order_by(Lesson.id).all())
    ids = [l.id for l in lessons]
    if lesson.id not in ids:
        return 0, len(ids)
    return ids.index(lesson.id) + 1, len(ids)
