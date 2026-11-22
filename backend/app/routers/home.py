"""学习首页快照：聚合首页所需真实字段，避免前端多次请求。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.access import require_learning_user, resolve_target_user_id
from ..database import get_db
from ..models import (
    User, Lesson, WordBank, WordMastery, Point, LearningProgress, PdfDocument,
)

router = APIRouter(prefix="/api/home", tags=["home"])


def _lesson_progress(db: Session, subject: str, user_id: int) -> dict:
    """返回当前学习进度（按教材口径）。

    一个学科可能绑了多本教材，进度各自独立；这里取「有进度的那本」，
    没有则取绑定教材里该科的第一本。这样家长在后台给某本书设了进度，
    首页就能反映出来。
    """
    from ..models import UserDocument
    from ..services.learning_progress import get_progress, lesson_index

    bound_ids = [r[0] for r in
                 db.query(UserDocument.document_id).filter_by(user_id=user_id).all()]

    rows = (db.query(LearningProgress)
            .filter_by(user_id=user_id, subject=subject).all())
    # 优先用带 document_id 的记录；没有就用该科的老记录（document_id 为 NULL）
    prog = next((r for r in rows if r.document_id is not None), None)
    if prog is None and rows:
        prog = rows[0]

    lesson = None
    if prog is not None and prog.current_lesson_id:
        lesson = db.get(Lesson, prog.current_lesson_id)
    if lesson is None:
        # 没进度（或进度指向的课已删）：取绑定教材里该科的第一课
        q = db.query(Lesson).filter(Lesson.subject == subject)
        if bound_ids:
            q = q.filter(Lesson.document_id.in_(bound_ids))
        lesson = q.order_by(Lesson.id).first()

    current, total = lesson_index(db, lesson)
    return {
        "current": current or 1,
        "total": total,
        "mastered": max((current or 1) - 1, 0),
        "current_lesson_id": lesson.id if lesson else None,
        "document_id": lesson.document_id if lesson else None,
        "document_name": (db.get(PdfDocument, lesson.document_id).filename
                          if lesson and lesson.document_id else ""),
    }


def _pending_review(db: Session) -> dict:
    """待复习词条数（WordMastery.is_weak），按词所属课的 subject 分组。"""
    weak_word_ids = [r[0] for r in db.query(WordMastery.word_bank_id).filter_by(is_weak=True).all()]
    result = {}
    if weak_word_ids:
        rows = (
            db.query(Lesson.subject, WordBank.id)
            .join(WordBank, WordBank.lesson_id == Lesson.id)
            .filter(WordBank.id.in_(weak_word_ids))
            .all()
        )
        for subject, _ in rows:
            result[subject] = result.get(subject, 0) + 1
    return result


@router.get("/snapshot")
def snapshot(subject: str = "语文",
             _auth: User = Depends(require_learning_user),
             user_id: int = Depends(resolve_target_user_id),
             db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    points = sum(p.delta for p in db.query(Point).filter_by(user_id=user_id).all())

    # 听写词条数：已审核课的词条总数（与 /api/dictation/words 取词范围一致）
    approved_ids = [l.id for l in db.query(Lesson).filter_by(audit_status="approved").all()]
    dict_word_count = (
        db.query(WordBank).filter(WordBank.lesson_id.in_(approved_ids)).count()
        if approved_ids else 0
    )

    return {
        "user_name": user.name if user else "",
        "points": points,
        "subject": subject,
        "lesson_progress": _lesson_progress(db, subject, user_id),
        "pending_review": _pending_review(db),
        "dict_word_count": dict_word_count,
        "week_stats": None,  # TODO: 未实现——后端暂无学习时长/打卡数据源，前端首页周报图无数据
    }
