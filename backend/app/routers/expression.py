"""孩子讲一遍（表达练习）：家长能看到孩子自己的解释。

刻意不做判定、不写掌握度——见 docs/superpowers/specs/2026-11-25-feynman-teach-ai-design.md。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import (
    ensure_user_access, require_learning_user, resolve_target_user_id,
)
from ..database import get_db
from ..models import (
    ExpressionNote, KnowledgeMastery, KnowledgePoint, TrainingGroup,
    TrainingItem, User,
)
from ..services.bucket_guard import assert_writable, resolve_bucket_id

router = APIRouter(prefix="/api/expression", tags=["expression"])

MIN_GRADE = 3


def _require_grade(user_id: int, db: Session) -> User:
    """目标孩子须 ≥3 年级；grade 为 None 视为 3（与 bucket_service 一致）。"""
    child = db.get(User, user_id)
    if child is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if (child.grade or MIN_GRADE) < MIN_GRADE:
        raise HTTPException(status_code=403, detail={"error": "grade_too_low"})
    return child


@router.get("/topics")
def list_topics(user_id: int = Depends(resolve_target_user_id),
                _auth: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    """可讲的主题：孩子有掌握度记录的知识点 + 家庭 group 下的 explore 条目。"""
    _require_grade(user_id, db)
    topics: list[dict] = []

    bid = resolve_bucket_id(db, user_id, None)
    if bid is not None:
        q = (db.query(KnowledgeMastery, KnowledgePoint)
             .join(KnowledgePoint, KnowledgeMastery.knowledge_point_id == KnowledgePoint.id)
             .filter(KnowledgeMastery.user_id == user_id,
                     KnowledgeMastery.bucket_id == bid))
        for _m, kp in q.order_by(KnowledgePoint.id).all():
            topics.append({"kind": "knowledge_point", "id": kp.id,
                           "title": (kp.content or "")[:255]})

    child = db.get(User, user_id)
    parent_id = child.parent_id if child else None
    if parent_id:
        group_ids = [r[0] for r in db.query(TrainingGroup.id).filter_by(owner_id=parent_id).all()]
        if group_ids:
            items = (db.query(TrainingItem)
                     .filter(TrainingItem.group_id.in_(group_ids),
                             TrainingItem.kind == "explore")
                     .order_by(TrainingItem.id).all())
            for it in items:
                topics.append({"kind": "training_item", "id": it.id,
                               "title": (it.primary or it.block_title or "")[:255]})

    return {"topics": topics}


MAX_TEXT_LEN = 5000


class NoteReq(BaseModel):
    user_id: int
    knowledge_point_id: int | None = None
    item_id: int | None = None
    text: str


def _validate_target(child: User, req: NoteReq, db: Session) -> str:
    """校验主题归属并返回 title 快照。"""
    if (req.knowledge_point_id is None) == (req.item_id is None):
        raise HTTPException(status_code=400, detail="必须且只能指定一个主题")

    if req.knowledge_point_id is not None:
        bid = resolve_bucket_id(db, child.id, None)
        q = db.query(KnowledgeMastery).filter_by(
            user_id=child.id, knowledge_point_id=req.knowledge_point_id)
        if bid is not None:
            q = q.filter(KnowledgeMastery.bucket_id == bid)
        if q.first() is None:
            raise HTTPException(status_code=403, detail={"error": "forbidden"})
        kp = db.query(KnowledgePoint).filter_by(id=req.knowledge_point_id).first()
        if kp is None:
            raise HTTPException(status_code=404, detail="知识点不存在")
        return (kp.content or "")[:255]

    item = (db.query(TrainingItem)
            .join(TrainingGroup, TrainingItem.group_id == TrainingGroup.id)
            .filter(TrainingItem.id == req.item_id,
                    TrainingGroup.owner_id == child.parent_id,
                    TrainingItem.kind == "explore")
            .first())
    if item is None:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    return (item.primary or item.block_title or "")[:255]


@router.post("/notes")
def create_note(req: NoteReq, user: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    # 只有孩子本人能写：家长代写会让这份记录失去意义
    if user.id != req.user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="内容不能为空")
    if len(text) > MAX_TEXT_LEN:
        raise HTTPException(status_code=400, detail=f"内容不能超过 {MAX_TEXT_LEN} 字")

    child = _require_grade(req.user_id, db)
    title = _validate_target(child, req, db)

    bid = resolve_bucket_id(db, req.user_id, None)
    note = ExpressionNote(
        user_id=req.user_id, bucket_id=bid,
        knowledge_point_id=req.knowledge_point_id, item_id=req.item_id,
        title=title, text=text,
    )
    db.add(note); db.commit(); db.refresh(note)
    return {"id": note.id, "created_at": note.created_at.isoformat()}


@router.get("/notes")
def list_notes(user_id: int = Depends(resolve_target_user_id),
               _auth: User = Depends(require_learning_user),
               limit: int = 50, db: Session = Depends(get_db)):
    """不按桶过滤：家长要能看孩子以前怎么讲的，这些内容无调度含义。"""
    _require_grade(user_id, db)
    rows = (db.query(ExpressionNote).filter_by(user_id=user_id)
            .order_by(ExpressionNote.created_at.desc())
            .limit(max(1, min(limit, 200))).all())
    return {"notes": [
        {"id": n.id, "title": n.title, "text": n.text,
         "created_at": n.created_at.isoformat()}
        for n in rows
    ]}


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, user: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    note = db.get(ExpressionNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    ensure_user_access(user, note.user_id, db)
    try:
        assert_writable(db, note.user_id, note.bucket_id)
    except PermissionError:
        raise HTTPException(status_code=400, detail="历史学年只读")
    db.delete(note); db.commit()
    return {"ok": True}
