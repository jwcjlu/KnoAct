"""基础知识（知识点）管理：列表、添加、删除。供家长端维护 + 复习出题。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, require_role
from ..database import get_db
from ..models import KnowledgePoint, Lesson, User, UserDocument
from ..services.cleanup import detach_points

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _parent_bound_document_ids(db: Session, parent_id: int) -> set[int]:
    kid_ids = [r[0] for r in db.query(User.id).filter_by(parent_id=parent_id, role="child").all()]
    if not kid_ids:
        return set()
    return {
        r[0]
        for r in db.query(UserDocument.document_id).filter(UserDocument.user_id.in_(kid_ids)).all()
    }


def _ensure_knowledge_scope(user: User, point: KnowledgePoint, db: Session) -> None:
    """家长只能操作其孩子已绑定教材下的知识点；无 lesson 的全局行仅 admin；admin 任意。"""
    if user.role == "admin":
        return
    if point.lesson_id is None:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    lesson = db.get(Lesson, point.lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="课程不存在")
    doc_ids = _parent_bound_document_ids(db, user.id)
    if lesson.document_id not in doc_ids:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})


def _resolve_knowledge_lesson_id(user: User, lesson_id: int | None, db: Session) -> int:
    """解析知识点归属课：家长未传 lesson_id 时取已绑定教材下 id 最小的一节课；admin 必须显式传 lesson_id。"""
    if user.role == "admin":
        if lesson_id is None:
            raise HTTPException(status_code=400, detail="请指定 lesson_id")
        lesson = db.get(Lesson, lesson_id)
        if lesson is None:
            raise HTTPException(status_code=404, detail="课程不存在")
        return lesson_id
    if user.role != "parent":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    doc_ids = _parent_bound_document_ids(db, user.id)
    if not doc_ids:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    if lesson_id is not None:
        lesson = db.get(Lesson, lesson_id)
        if lesson is None:
            raise HTTPException(status_code=404, detail="课程不存在")
        if lesson.document_id not in doc_ids:
            raise HTTPException(status_code=403, detail={"error": "forbidden"})
        return lesson_id
    lesson = (
        db.query(Lesson)
        .filter(Lesson.document_id.in_(doc_ids))
        .order_by(Lesson.id)
        .first()
    )
    if lesson is None:
        raise HTTPException(status_code=400, detail="暂无课程，请先绑定教材并完成拆课")
    return lesson.id


@router.get("")
def list_knowledge(subject: str = "", user: User = Depends(require_role("parent", "admin")),
                   db: Session = Depends(get_db)):
    q = db.query(KnowledgePoint)
    if subject:
        q = q.filter_by(subject=subject)
    if user.role == "parent":
        doc_ids = _parent_bound_document_ids(db, user.id)
        if not doc_ids:
            return []
        lesson_ids = [r[0] for r in db.query(Lesson.id).filter(Lesson.document_id.in_(doc_ids)).all()]
        q = q.filter(KnowledgePoint.lesson_id.in_(lesson_ids if lesson_ids else [-1]))
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
def add_knowledge(req: KnowledgeReq, _auth: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    lid = _resolve_knowledge_lesson_id(_auth, req.lesson_id, db)
    p = KnowledgePoint(subject=req.subject, category=req.category, content=req.content, lesson_id=lid)
    db.add(p); db.commit(); db.refresh(p)
    return {"id": p.id, "subject": p.subject, "category": p.category, "content": p.content}


@router.delete("/{point_id}")
def delete_knowledge(point_id: int, user: User = Depends(require_role("parent", "admin")),
                     db: Session = Depends(get_db)):
    p = db.get(KnowledgePoint, point_id)
    if p:
        _ensure_knowledge_scope(user, p, db)
        detach_points(db, [p.id])
        db.delete(p); db.commit()
        return {"ok": True}
    return {"ok": False, "error": "not found"}
