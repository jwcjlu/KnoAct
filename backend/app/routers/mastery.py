"""精通之路：掌握度总览与记录。"""
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import KnowledgeMastery, KnowledgePoint
from ..services.mastery import record_attempt as _record

router = APIRouter(prefix="/api/mastery", tags=["mastery"])


class RecordReq(BaseModel):
    user_id: int
    target_type: str   # 'knowledge' | 'word'
    target_id: int
    is_correct: bool


@router.get("/overview")
def overview(user_id: int, subject: str = "", db: Session = Depends(get_db)):
    q = (db.query(KnowledgeMastery, KnowledgePoint)
         .join(KnowledgePoint, KnowledgeMastery.knowledge_point_id == KnowledgePoint.id)
         .filter(KnowledgeMastery.user_id == user_id))
    if subject:
        q = q.filter(KnowledgePoint.subject == subject)
    rows = q.all()
    return [{
        "knowledge_point_id": kp.id,
        "title": kp.content,
        "category": kp.category,
        "mastery": km.mastery,
        "mastered": km.mastered,
        "due": km.next_review_at is not None and km.next_review_at <= datetime.utcnow(),
    } for km, kp in rows]


@router.post("/record")
def record(req: RecordReq, db: Session = Depends(get_db)):
    mastery = _record(db, req.user_id, req.target_type, req.target_id, req.is_correct)
    return {"mastery": mastery}
