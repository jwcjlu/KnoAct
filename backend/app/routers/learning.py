from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Lesson, WordBank, Point
from ..services.scheduler import select_words

router = APIRouter(tags=["learning"])

@router.get("/api/dictation/words")
def dictation_words(user_id: int, db: Session = Depends(get_db)):
    approved = db.query(Lesson).filter_by(audit_status="approved").all()
    ids = [l.id for l in approved]
    words = db.query(WordBank).filter(WordBank.lesson_id.in_(ids)).all() if ids else []
    rows = [{"id": w.id, "word": w.word, "extra": w.extra, "mistake_count": 0, "next_review_at": None} for w in words]
    picked = select_words(rows, limit=len(rows))
    return [{"id": r["id"], "word": r["word"], "extra": r["extra"]} for r in picked]

class GradeReq(BaseModel):
    word: str
    answer: str

@router.post("/api/dictation/grade")
def dictation_grade(req: GradeReq, db: Session = Depends(get_db)):
    correct = req.answer.strip() == req.word
    return {"correct": correct}

class CompleteReq(BaseModel):
    user_id: int
    correct: int
    wrong: int

@router.post("/api/dictation/complete")
def dictation_complete(req: CompleteReq, db: Session = Depends(get_db)):
    awarded = max(req.correct * 2, 10)
    db.add(Point(user_id=req.user_id, delta=awarded, reason="听写打卡"))
    db.commit()
    return {"points_awarded": awarded}
