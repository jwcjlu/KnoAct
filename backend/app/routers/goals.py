from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Goal

router = APIRouter(prefix="/api/goals", tags=["goals"])

class GoalReq(BaseModel):
    user_id: int
    content: str

class AssessReq(BaseModel):
    correct: int
    total: int

@router.post("")
def create_goal(req: GoalReq, db: Session = Depends(get_db)):
    g = Goal(user_id=req.user_id, content=req.content, status="pending")
    db.add(g); db.commit(); db.refresh(g)
    return {"id": g.id, "content": g.content, "status": g.status}

@router.get("")
def list_goals(user_id: int, db: Session = Depends(get_db)):
    goals = db.query(Goal).filter_by(user_id=user_id).order_by(Goal.id.desc()).all()
    return [
        {"id": g.id, "content": g.content, "status": g.status, "achieved_at": g.achieved_at}
        for g in goals
    ]

@router.post("/{goal_id}/assess")
def assess(goal_id: int, req: AssessReq, db: Session = Depends(get_db)):
    rate = req.correct / req.total if req.total else 0
    achieved = rate >= 0.6
    g = db.get(Goal, goal_id)
    if g and achieved:
        g.status = "done"
        g.achieved_at = datetime.utcnow()
        db.commit()
    return {"achieved": achieved, "rate": rate}
