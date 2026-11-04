from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Goal
from ..services.bucket_guard import resolve_bucket_id, assert_writable

router = APIRouter(prefix="/api/goals", tags=["goals"])

class GoalReq(BaseModel):
    user_id: int
    content: str

class AssessReq(BaseModel):
    correct: int
    total: int

@router.post("")
def create_goal(req: GoalReq, bucket_id: int | None = None, db: Session = Depends(get_db)):
    bid = resolve_bucket_id(db, req.user_id, bucket_id)
    g = Goal(user_id=req.user_id, bucket_id=bid, content=req.content, status="pending")
    db.add(g); db.commit(); db.refresh(g)
    return {"id": g.id, "content": g.content, "status": g.status}

@router.get("")
def list_goals(user_id: int, bucket_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Goal).filter_by(user_id=user_id)
    bid = resolve_bucket_id(db, user_id, bucket_id)
    if bid is not None:
        q = q.filter_by(bucket_id=bid)
    goals = q.order_by(Goal.id.desc()).all()
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
        try:
            assert_writable(db, g.user_id, g.bucket_id)
        except PermissionError:
            return {"achieved": False, "rate": rate, "error": "历史学年只读"}
        g.status = "done"
        g.achieved_at = datetime.utcnow()
        db.commit()
    return {"achieved": achieved, "rate": rate}
