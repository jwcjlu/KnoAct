"""学习首页快照：聚合首页所需真实字段，避免前端多次请求。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.access import require_learning_user, resolve_target_user_id
from ..database import get_db
from ..models import User, Lesson, WordBank, WordMastery, Point, LearningProgress

router = APIRouter(prefix="/api/home", tags=["home"])


def _lesson_progress(db: Session, subject: str, prog: LearningProgress | None) -> dict:
    """把 LearningProgress.current_lesson_id（lessons.id）映射为课程序号。
    口径：总课数 = 该学科全部 lesson 数量；当前课 = current_lesson_id 在排序中的序号。"""
    lessons = db.query(Lesson).filter_by(subject=subject).order_by(Lesson.id).all()
    total = len(lessons)
    ids = [l.id for l in lessons]
    current = 1
    current_lesson_id = lessons[0].id if lessons else None
    if prog and prog.current_lesson_id in ids:
        current_lesson_id = prog.current_lesson_id
        current = ids.index(prog.current_lesson_id) + 1
    mastered = max(current - 1, 0)
    return {"current": current, "total": total, "mastered": mastered,
            "current_lesson_id": current_lesson_id}


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
    prog = db.query(LearningProgress).filter_by(user_id=user_id, subject=subject).first()

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
        "lesson_progress": _lesson_progress(db, subject, prog),
        "pending_review": _pending_review(db),
        "dict_word_count": dict_word_count,
        "week_stats": None,  # TODO: 未实现——后端暂无学习时长/打卡数据源，前端首页周报图无数据
    }
