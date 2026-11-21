"""每日一练：当前课时偏好 + 今日抽题预览（计划二的最小可用部分）。"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access, require_learning_user
from ..core.deps import require_role
from ..database import get_db
from ..models import ChildConfig, Question, QuestionBank, User

router = APIRouter(tags=["practice"])


class PreferencesReq(BaseModel):
    user_id: int
    current_document: int | None = None
    current_lesson: int | None = None


def _set_child_config(db: Session, user_id: int, key: str, value: str) -> None:
    row = db.query(ChildConfig).filter_by(user_id=user_id, key=key).first()
    if row is None:
        db.add(ChildConfig(user_id=user_id, key=key, value=value))
    else:
        row.value = value


@router.put("/api/practice/preferences")
def put_preferences(
    req: PreferencesReq,
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """家长设定「当前练习册 / 当前课时」——每日任务按它抽题。"""
    child = db.get(User, req.user_id)
    if child is None or child.role != "child":
        raise HTTPException(status_code=404, detail={"error": "child_not_found"})
    if user.role != "admin" and child.parent_id != user.id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})

    if req.current_document is not None:
        bank = db.get(QuestionBank, req.current_document)
        if bank is None:
            raise HTTPException(status_code=404, detail={"error": "bank_not_found"})
        _set_child_config(db, req.user_id, "practice_current_document",
                          str(req.current_document))
    if req.current_lesson is not None:
        _set_child_config(db, req.user_id, "practice_current_lesson",
                          str(req.current_lesson))
    db.commit()
    return {"ok": True}


@router.get("/api/practice/preferences")
def get_preferences(
    user_id: int = Query(...),
    user: User = Depends(require_learning_user),
    db: Session = Depends(get_db),
):
    ensure_user_access(user, user_id, db)
    rows = {
        r.key: r.value
        for r in db.query(ChildConfig).filter_by(user_id=user_id).all()
        if r.key.startswith("practice_")
    }

    def _int(k):
        try:
            return int(rows.get(k) or 0) or None
        except (TypeError, ValueError):
            return None

    return {
        "current_document": _int("practice_current_document"),
        "current_lesson": _int("practice_current_lesson"),
    }


@router.get("/api/practice/preview")
def preview_today(
    user_id: int = Query(...),
    user: User = Depends(require_learning_user),
    db: Session = Depends(get_db),
):
    """预览今天会自动抽到哪几道题（家长核对布置效果用）。"""
    ensure_user_access(user, user_id, db)
    from datetime import date as _date

    from ..services.task_gen import _pick_practice_questions

    child = db.get(User, user_id)
    banks = (
        db.query(QuestionBank)
        .filter_by(user_id=child.parent_id, status="active")
        .all()
        if child and child.parent_id else []
    )
    picked_all: list[dict] = []
    for bank in banks:
        try:
            tags = json.loads(bank.tags or "{}")
        except (ValueError, TypeError):
            tags = {}
        if not tags.get("include_daily_task"):
            continue
        picked, lesson_no, lesson_title = _pick_practice_questions(
            db, bank, user_id, _date.today(), 3)
        for q in picked:
            picked_all.append({
                "id": q.id,
                "bank_title": bank.title,
                "lesson_no": lesson_no,
                "lesson_title": lesson_title,
                "question": q.question,
                "answer": q.answer,
            })
        break  # 目前每天一科一份练习
    return {"items": picked_all}
