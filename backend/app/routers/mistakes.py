"""错题本 + 薄弱环节报告。"""
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Mistake

router = APIRouter(prefix="/api/mistakes", tags=["mistakes"])

REMOVE_AFTER = 3  # 连续答对 3 次自动移出错题本


@router.get("")
def list_mistakes(user_id: int, subject: str = "", db: Session = Depends(get_db)):
    q = db.query(Mistake).filter_by(user_id=user_id)
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
def mark_correct(mistake_id: int, db: Session = Depends(get_db)):
    """答对一次：consecutive_correct 累计，达到阈值自动移出（删除）。"""
    m = db.get(Mistake, mistake_id)
    if not m:
        return {"removed": False, "error": "not found"}
    m.consecutive_correct += 1
    removed = m.consecutive_correct >= REMOVE_AFTER
    if removed:
        db.delete(m)
    db.commit()
    return {"removed": removed, "consecutive_correct": 0 if removed else m.consecutive_correct}


@router.post("/{mistake_id}/wrong")
def mark_wrong(mistake_id: int, db: Session = Depends(get_db)):
    """再答错：重置连续正确计数，累计错误次数。"""
    m = db.get(Mistake, mistake_id)
    if not m:
        return {"error": "not found"}
    m.consecutive_correct = 0
    m.mistake_count += 1
    db.commit()
    return {"mistake_count": m.mistake_count}


@router.get("/report")
def weakness_report(user_id: int, db: Session = Depends(get_db)):
    """近 30 天按题型汇总错误频率，供家长端薄弱报告。"""
    mistakes = db.query(Mistake).filter_by(user_id=user_id).all()
    counter = Counter(m.source_type for m in mistakes)
    # 题型中文名
    names = {"dictation": "听写", "review": "复习", "listening": "听力", "reading": "阅读", "goal": "考核"}
    rows = [
        {"name": names.get(k, k), "count": v}
        for k, v in counter.most_common()
    ]
    return {"total": len(mistakes), "rows": rows}
