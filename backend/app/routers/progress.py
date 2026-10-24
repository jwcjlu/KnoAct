from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import LearningProgress

router = APIRouter(prefix="/api/progress", tags=["progress"])

THRESHOLD = 0.6  # 默认 60%，可后续从 model_config 读

class AdvanceReq(BaseModel):
    user_id: int
    correct: int
    total: int

class AdjustReq(BaseModel):
    user_id: int
    lesson_id: int

@router.post("/advance")
def advance(req: AdvanceReq, db: Session = Depends(get_db)):
    rate = req.correct / req.total if req.total else 0
    passed = rate >= THRESHOLD
    if passed:
        prog = db.query(LearningProgress).filter_by(user_id=req.user_id).first()
        if not prog:
            prog = LearningProgress(user_id=req.user_id, current_lesson_id=None)
            db.add(prog)
        prog.current_lesson_id = (prog.current_lesson_id or 0) + 1
        db.commit()
    return {"passed": passed, "rate": rate}

@router.post("/adjust")
def adjust(req: AdjustReq, db: Session = Depends(get_db)):
    prog = db.query(LearningProgress).filter_by(user_id=req.user_id).first()
    if not prog:
        prog = LearningProgress(user_id=req.user_id, current_lesson_id=req.lesson_id)
        db.add(prog)
    else:
        prog.current_lesson_id = req.lesson_id
    db.commit()
    return {"user_id": req.user_id, "current_lesson_id": prog.current_lesson_id}
