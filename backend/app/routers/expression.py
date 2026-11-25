"""孩子讲一遍（表达练习）：家长能看到孩子自己的解释。

刻意不做判定、不写掌握度——见 docs/superpowers/specs/2026-11-25-feynman-teach-ai-design.md。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.access import require_learning_user, resolve_target_user_id
from ..database import get_db
from ..models import (
    KnowledgeMastery, KnowledgePoint, TrainingGroup, TrainingItem, User,
)
from ..services.bucket_guard import resolve_bucket_id

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
