from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import LearningProgress, Lesson

router = APIRouter(prefix="/api/progress", tags=["progress"])

class AdvanceReq(BaseModel):
    user_id: int
    correct: int
    total: int
    subject: str = "语文"

class AdjustReq(BaseModel):
    user_id: int
    lesson_id: int
    subject: str = "语文"

@router.post("/advance")
def advance(req: AdvanceReq, db: Session = Depends(get_db)):
    from ..models import ModelConfig
    row = db.query(ModelConfig).filter_by(key="assignment_pass_threshold").first()
    try:
        threshold = float(row.value) if row and row.value else 0.6
    except ValueError:
        threshold = 0.6
    rate = req.correct / req.total if req.total else 0
    passed = rate >= threshold
    if passed:
        # 按该学科 lesson 排序推进到「下一课」，而不是盲 +1（lesson id 跨学科不连续）
        lessons = db.query(Lesson).filter_by(subject=req.subject).order_by(Lesson.id).all()
        prog = db.query(LearningProgress).filter_by(user_id=req.user_id, subject=req.subject).first()
        if not prog:
            prog = LearningProgress(user_id=req.user_id, subject=req.subject, current_lesson_id=None)
            db.add(prog)
        if lessons:
            ids = [l.id for l in lessons]
            cur = prog.current_lesson_id
            if cur in ids:
                idx = ids.index(cur)
                nxt = ids[idx + 1] if idx + 1 < len(ids) else ids[-1]
            else:
                nxt = ids[0]
            prog.current_lesson_id = nxt
        db.commit()
    return {"passed": passed, "rate": rate}

@router.post("/adjust")
def adjust(req: AdjustReq, db: Session = Depends(get_db)):
    prog = db.query(LearningProgress).filter_by(user_id=req.user_id, subject=req.subject).first()
    if not prog:
        prog = LearningProgress(user_id=req.user_id, subject=req.subject, current_lesson_id=req.lesson_id)
        db.add(prog)
    else:
        prog.current_lesson_id = req.lesson_id
    db.commit()
    return {"user_id": req.user_id, "subject": req.subject, "current_lesson_id": prog.current_lesson_id}
