"""基础知识（知识点）管理：列表、添加、删除。供家长端维护 + 复习出题。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import KnowledgePoint
from ..services.cleanup import detach_points

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("")
def list_knowledge(subject: str = "", db: Session = Depends(get_db)):
    q = db.query(KnowledgePoint)
    if subject:
        q = q.filter_by(subject=subject)
    rows = q.order_by(KnowledgePoint.id).all()
    return [
        {"id": p.id, "subject": p.subject, "category": p.category, "content": p.content}
        for p in rows
    ]


class KnowledgeReq(BaseModel):
    subject: str
    category: str
    content: str
    lesson_id: int | None = None


@router.post("")
def add_knowledge(req: KnowledgeReq, db: Session = Depends(get_db)):
    p = KnowledgePoint(subject=req.subject, category=req.category, content=req.content, lesson_id=req.lesson_id)
    db.add(p); db.commit(); db.refresh(p)
    return {"id": p.id, "subject": p.subject, "category": p.category, "content": p.content}


@router.delete("/{point_id}")
def delete_knowledge(point_id: int, db: Session = Depends(get_db)):
    p = db.get(KnowledgePoint, point_id)
    if p:
        detach_points(db, [p.id])
        db.delete(p); db.commit()
        return {"ok": True}
    return {"ok": False, "error": "not found"}
