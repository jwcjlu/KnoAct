"""知识点复习队列（SRS）：家长管理队列，孩子领取到期项并完成复习。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access, require_learning_user
from ..core.deps import require_role
from ..database import get_db
from ..models import KnowledgePoint, KnowledgeReviewItem, Lesson, User
from ..services import knowledge_review as svc
from ..services.bucket_guard import resolve_bucket_id

router = APIRouter(prefix="/api/knowledge-review", tags=["knowledge-review"])


def _raise(e: svc.KnowledgeReviewError):
    raise HTTPException(status_code=e.status, detail={"error": e.code})


@router.get("/queue")
def queue(
    user_id: int = Query(...),
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """家长端：孩子当前学年桶内的复习队列（不含已移除）+ 到期统计。"""
    ensure_user_access(user, user_id, db)
    bid = resolve_bucket_id(db, user_id, None)
    items: list[dict] = []
    due_today = due_this_week = 0
    if bid is not None:
        now = datetime.utcnow()
        end_today = datetime(now.year, now.month, now.day) + timedelta(days=1)
        end_week = now + timedelta(days=7)
        rows = (
            db.query(KnowledgeReviewItem, KnowledgePoint)
            .join(KnowledgePoint, KnowledgeReviewItem.knowledge_point_id == KnowledgePoint.id)
            .filter(
                KnowledgeReviewItem.user_id == user_id,
                KnowledgeReviewItem.bucket_id == bid,
                KnowledgeReviewItem.status != "removed",
            )
            .order_by(KnowledgeReviewItem.next_review_at, KnowledgeReviewItem.id)
            .all()
        )
        for it, kp in rows:
            lesson = db.get(Lesson, kp.lesson_id) if kp.lesson_id else None
            nxt = it.next_review_at
            if it.status == "active" and nxt is not None:
                if nxt < end_today:
                    due_today += 1
                if nxt <= end_week:
                    due_this_week += 1
            items.append({
                "item_id": it.id,
                "knowledge_point_id": kp.id,
                "subject": kp.subject,
                "title": (kp.content or "")[:40],
                "content": kp.content or "",
                "lesson_title": lesson.title if lesson else "",
                "status": it.status,
                "interval_index": it.interval_index,
                "next_review_at": nxt.isoformat() if nxt else None,
                "last_result": it.last_result or "",
                "enroll_source": it.enroll_source,
            })
    return {"items": items, "due_today": due_today, "due_this_week": due_this_week}


def _parent_item_action(fn, item_id: int, user: User, db: Session):
    item = db.get(KnowledgeReviewItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"error": "item_not_found"})
    ensure_user_access(user, item.user_id, db)
    try:
        row = fn(db, item.user_id, item_id)
    except svc.KnowledgeReviewError as e:
        _raise(e)
    return {"ok": True, "item_id": row.id, "status": row.status}

@router.post("/item/{item_id}/pause")
def pause(item_id: int, user: User = Depends(require_role("parent", "admin")),
          db: Session = Depends(get_db)):
    return _parent_item_action(svc.pause_item, item_id, user, db)


@router.post("/item/{item_id}/resume")
def resume(item_id: int, user: User = Depends(require_role("parent", "admin")),
           db: Session = Depends(get_db)):
    return _parent_item_action(svc.resume_item, item_id, user, db)


@router.post("/item/{item_id}/remove")
def remove(item_id: int, user: User = Depends(require_role("parent", "admin")),
           db: Session = Depends(get_db)):
    return _parent_item_action(svc.remove_item, item_id, user, db)


@router.get("/due")
def due(
    user_id: int = Query(...),
    subject: str | None = Query(None),
    user: User = Depends(require_learning_user),
    db: Session = Depends(get_db),
):
    ensure_user_access(user, user_id, db)
    items = svc.select_due_items(db, user_id, subject)
    out = [svc.serialize_due_item(db, user_id, it) for it in items]
    db.commit()  # 持久化现场生成的题目
    return {"items": out}


class CompleteReq(BaseModel):
    user_id: int
    item_id: int
    result: str
    question_id: int | None = None
    student_answer: str | None = None
    duration_ms: int | None = None


@router.post("/complete")
def complete(req: CompleteReq, user: User = Depends(require_learning_user),
             db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    try:
        return svc.complete_item(
            db, req.user_id, req.item_id, req.result,
            question_id=req.question_id, student_answer=req.student_answer,
            duration_ms=req.duration_ms,
        )
    except svc.KnowledgeReviewError as e:
        _raise(e)
