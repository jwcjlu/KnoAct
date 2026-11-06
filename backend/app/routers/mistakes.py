"""错题本 + 薄弱环节报告。"""
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access, require_learning_user, resolve_target_user_id
from ..database import get_db
from ..models import Mistake, User
from ..services.bucket_guard import resolve_bucket_id, assert_writable

router = APIRouter(prefix="/api/mistakes", tags=["mistakes"])

REMOVE_AFTER = 3  # 连续答对 3 次自动移出错题本


@router.get("")
def list_mistakes(user_id: int = Depends(resolve_target_user_id),
                  _auth: User = Depends(require_learning_user),
                  subject: str = "", bucket_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Mistake).filter_by(user_id=user_id)
    bid = resolve_bucket_id(db, user_id, bucket_id)
    if bid is not None:
        q = q.filter_by(bucket_id=bid)
    if subject and subject != "全部":
        q = q.filter(Mistake.source_type.in_(_subject_sources(subject)))
    rows = q.order_by(Mistake.id.desc()).all()
    return [
        {
            "id": m.id, "source_type": m.source_type, "question": m.question,
            "your_answer": m.your_answer, "correct_answer": m.correct_answer,
            "mistake_count": m.mistake_count, "consecutive_correct": m.consecutive_correct,
        }
        for m in rows
    ]


def _subject_sources(subject: str) -> list[str]:
    """按学科过滤错题来源：语文=dictation/reading，英语=dictation/listening。"""
    if subject == "语文":
        return ["dictation", "reading"]
    if subject == "英语":
        return ["dictation", "listening"]
    return []


@router.post("/{mistake_id}/correct")
def mark_correct(mistake_id: int, user: User = Depends(require_learning_user),
                 db: Session = Depends(get_db)):
    """答对一次：有词/知识点关联时用掌握度判定移出，否则走旧计数逻辑。"""
    m = db.get(Mistake, mistake_id)
    if not m:
        return {"removed": False, "error": "not found"}
    ensure_user_access(user, m.user_id, db)
    try:
        assert_writable(db, m.user_id, m.bucket_id)
    except PermissionError:
        return {"removed": False, "error": "历史学年只读"}
    from ..services.mastery import record_attempt, GATE

    removed = False
    if m.word_bank_id:
        mastery = record_attempt(db, m.user_id, "word", m.word_bank_id, True,
                                 bucket_id=m.bucket_id)
        removed = mastery >= GATE
    elif m.knowledge_point_id:
        mastery = record_attempt(db, m.user_id, "knowledge", m.knowledge_point_id, True,
                                 bucket_id=m.bucket_id)
        removed = mastery >= GATE
    else:
        m.consecutive_correct += 1
        removed = m.consecutive_correct >= REMOVE_AFTER

    if removed:
        db.delete(m)
    db.commit()
    return {"removed": removed, "consecutive_correct": 0 if removed else m.consecutive_correct}


@router.post("/{mistake_id}/wrong")
def mark_wrong(mistake_id: int, user: User = Depends(require_learning_user),
               db: Session = Depends(get_db)):
    """再答错：有词/知识点关联时驱动掌握度下降，否则走旧计数。"""
    m = db.get(Mistake, mistake_id)
    if not m:
        return {"error": "not found"}
    ensure_user_access(user, m.user_id, db)
    try:
        assert_writable(db, m.user_id, m.bucket_id)
    except PermissionError:
        return {"error": "历史学年只读", "removed": False}
    from ..services.mastery import record_attempt

    if m.word_bank_id:
        record_attempt(db, m.user_id, "word", m.word_bank_id, False,
                       bucket_id=m.bucket_id)
    elif m.knowledge_point_id:
        record_attempt(db, m.user_id, "knowledge", m.knowledge_point_id, False,
                       bucket_id=m.bucket_id)
    # 错题本自身的计数字段，无论走哪个分支都要更新
    m.mistake_count += 1
    m.consecutive_correct = 0
    db.commit()
    return {"mistake_count": m.mistake_count}


@router.get("/report")
def weakness_report(user_id: int = Depends(resolve_target_user_id),
                    _auth: User = Depends(require_learning_user),
                    bucket_id: int | None = None, db: Session = Depends(get_db)):
    """近 30 天按题型汇总错误频率，供家长端薄弱报告。"""
    q = db.query(Mistake).filter_by(user_id=user_id)
    bid = resolve_bucket_id(db, user_id, bucket_id)
    if bid is not None:
        q = q.filter_by(bucket_id=bid)
    mistakes = q.all()
    counter = Counter(m.source_type for m in mistakes)
    # 题型中文名
    names = {"dictation": "听写", "review": "复习", "listening": "听力", "reading": "阅读", "goal": "考核"}
    rows = [
        {"name": names.get(k, k), "count": v}
        for k, v in counter.most_common()
    ]
    return {"total": len(mistakes), "rows": rows}
