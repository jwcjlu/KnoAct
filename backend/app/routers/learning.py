from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Lesson, WordBank, Point
from ..models import KnowledgePoint, Mistake
from ..services.scheduler import select_words
from ..services.ai import get_provider

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

@router.get("/api/review/questions")
def review_questions(subject: str, db: Session = Depends(get_db)):
    points = db.query(KnowledgePoint).filter_by(subject=subject).all()
    provider = get_provider(db)
    if not points:
        return []
    questions = []
    for p in points[:5]:
        try:
            q = provider.generate(
                prompt=f"针对知识点「{p.content}」出一道判断正误题，格式：题目||答案",
                system="你是出题老师，只输出题目和答案，用||分隔。",
            )
            stem, ans = q.split("||") if "||" in q else (q, "")
        except Exception:
            stem, ans = f"「{p.content}」的判断对错题（示例）", "对"
        questions.append({"question": stem, "answer": ans, "point_id": p.id})
    return questions

class ReviewSubmitReq(BaseModel):
    user_id: int
    question: str
    your_answer: str
    correct_answer: str
    source_type: str = "review"

@router.post("/api/review/submit")
def review_submit(req: ReviewSubmitReq, db: Session = Depends(get_db)):
    if req.your_answer.strip() != req.correct_answer.strip():
        db.add(Mistake(
            user_id=req.user_id, source_type=req.source_type,
            question=req.question, your_answer=req.your_answer, correct_answer=req.correct_answer,
        ))
        db.commit()
    return {"ok": True}
