"""做题明细查询：家长/管理员查某孩子某天的逐题作答。"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access
from ..core.deps import require_role
from ..database import get_db
from ..models import AnswerRecord, User

router = APIRouter(prefix="/api/answer-records", tags=["answer-records"])

# 东八区（Asia/Shanghai）相对 UTC 的偏移：当天 0 点 = UTC 前一日 16:00
_CHINA_UTC_OFFSET = timedelta(hours=8)


@router.get("")
def list_answer_records(
    user_id: int,
    target_date: date | None = None,
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    child = db.get(User, user_id)
    if child is None or child.role != "child":
        raise HTTPException(status_code=404, detail="孩子不存在")
    ensure_user_access(user, user_id, db)
    d = target_date or datetime.utcnow().date()
    day_start_utc = datetime(d.year, d.month, d.day) - _CHINA_UTC_OFFSET
    day_end_utc = day_start_utc + timedelta(days=1)
    rows = (
        db.query(AnswerRecord)
        .filter(AnswerRecord.user_id == user_id,
                AnswerRecord.created_at >= day_start_utc,
                AnswerRecord.created_at < day_end_utc)
        .order_by(AnswerRecord.created_at)
        .all()
    )
    records = [
        {
            "id": r.id, "subject": r.subject, "module": r.module,
            "question": r.question, "student_answer": r.student_answer,
            "correct_answer": r.correct_answer, "is_correct": r.is_correct,
            "difficulty": r.difficulty, "duration_ms": r.duration_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return {"total": len(records), "records": records}
