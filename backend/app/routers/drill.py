# backend/app/routers/drill.py
import json
from fastapi import APIRouter, Depends, Form, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access
from ..core.deps import require_role
from ..database import get_db
from ..models import TrainingGroup, TrainingItem, User
from ..services.ai import ocr_image
from ..services.drill_rule import extract_drill_items

router = APIRouter(prefix="/api/drill", tags=["drill"])

from datetime import date as date_type


class GroupItemIn(BaseModel):
    kind: str = "drill_item"
    primary: str = ""
    secondary: str = ""
    block_title: str = ""
    example: str = ""
    keywords: list[str] = []
    source_page: int | None = None


class GroupCreateReq(BaseModel):
    source: str = "custom"
    subject: str = ""
    title: str = ""
    kind: str = "outline"
    document_id: int | None = None
    start_page: int | None = None
    end_page: int | None = None
    mastery_interval_days: int = 15
    interval_max_days: int = 60
    sort_order: int = 0
    items: list[GroupItemIn] = []


@router.post("/groups")
def create_group(req: GroupCreateReq, user: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    g = TrainingGroup(owner_id=user.id, subject=req.subject, title=req.title,
                      source=req.source, kind=req.kind, document_id=req.document_id,
                      start_page=req.start_page, end_page=req.end_page,
                      mastery_interval_days=req.mastery_interval_days,
                      interval_max_days=req.interval_max_days, sort_order=req.sort_order)
    db.add(g); db.flush()
    for it in req.items:
        db.add(TrainingItem(group_id=g.id, kind=it.kind, primary=it.primary,
                            secondary=it.secondary, block_title=it.block_title,
                            example=it.example, keywords=json.dumps(it.keywords, ensure_ascii=False),
                            source_page=it.source_page))
    db.flush()

    from ..services.drill_rule import generate_group_content
    items_payload = [{"primary": it.primary, "secondary": it.secondary} for it in req.items]
    content = generate_group_content(db, req.subject, req.kind, items_payload)
    g.intro = json.dumps(content["intro"], ensure_ascii=False)
    g.group_rule = json.dumps(content["group_rule"], ensure_ascii=False)
    # common_mistakes 按 primary 匹配回填到条目
    mistakes = content["common_mistakes"]
    for payload in items_payload:
        if payload["primary"] in mistakes:
            item_row = db.query(TrainingItem).filter_by(group_id=g.id, primary=payload["primary"]).first()
            if item_row:
                item_row.common_mistake = json.dumps(mistakes[payload["primary"]], ensure_ascii=False)
    # 发布前 AI 预检（提示式，不阻断）
    from ..services.drill_review import review_group_items
    g.ai_review = json.dumps(review_group_items(db, req.subject, req.kind, items_payload), ensure_ascii=False)
    db.commit()
    return {"group_id": g.id}


@router.post("/groups/{group_id}/audit")
def audit_group(group_id: int, action: str = Form(...),
                _auth: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    g = db.get(TrainingGroup, group_id)
    if not g:
        return {"ok": False, "error": "not found"}
    g.audit_status = "approved" if action == "通过" else "rejected"
    db.commit()
    return {"id": g.id, "audit_status": g.audit_status}


@router.post("/groups/{group_id}/reactivate")
def reactivate_group(group_id: int, _auth: User = Depends(require_role("parent", "admin")),
                     db: Session = Depends(get_db)):
    from ..models import TrainingItemMastery
    g = db.get(TrainingGroup, group_id)
    if not g:
        return {"ok": False, "error": "not found"}
    item_ids = [r[0] for r in db.query(TrainingItem.id).filter_by(group_id=group_id).all()]
    for m in db.query(TrainingItemMastery).filter(TrainingItemMastery.item_id.in_(item_ids)).all():
        m.interval = 1; m.lapse = 0; m.last_hinted = False; m.next_review_at = None
    db.commit()
    return {"ok": True}


class TaskCreateReq(BaseModel):
    group_id: int
    user_id: int
    date: date_type
    include_due: bool = False


@router.post("/tasks")
def create_task(req: TaskCreateReq, user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    from ..models import Task, TrainingItemMastery
    from ..services.drill_content import build_task_content, build_quiz, MAX_ITEMS
    from datetime import datetime
    ensure_user_access(user, req.user_id, db)
    g = db.get(TrainingGroup, req.group_id)
    if not g or g.audit_status != "approved":
        return {"error": "group not approved"}
    items = db.query(TrainingItem).filter_by(group_id=g.id).order_by(TrainingItem.id).all()
    if not items:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="无条目")
    items = items[:MAX_ITEMS]
    review_items = []
    if req.include_due:
        now = datetime.utcnow()
        due_ids = {m.item_id for m in db.query(TrainingItemMastery).filter(
            TrainingItemMastery.user_id == req.user_id,
            TrainingItemMastery.next_review_at.isnot(None),
            TrainingItemMastery.next_review_at <= now).all()}
        review_items = [it for it in items if it.id in due_ids]
    existing = db.query(Task).filter_by(user_id=req.user_id, subject=g.subject,
                                        date=req.date, task_type="drill").first()
    if existing:
        return {"task_id": existing.id}
    quiz = build_quiz(items)
    content = build_task_content(g, items, review_items, quiz)
    t = Task(user_id=req.user_id, subject=g.subject, date=req.date, task_type="drill",
             title=g.title, content=content, points=20, content_status="published")
    db.add(t); db.commit(); db.refresh(t)
    return {"task_id": t.id}


@router.post("/photo-groups")
async def photo_groups(subject: str = Form(...), file: UploadFile = File(...),
                       user: User = Depends(require_role("parent", "admin")),
                       db: Session = Depends(get_db)):
    """拍照出题：家长拍错题照片 → OCR → 提取识记条目 → 建组（pending 待审）。"""
    from fastapi import HTTPException
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="请上传图片")
    try:
        ocr_text = ocr_image(db, data, instruction="识别这张错题图片中的题目文字、孩子答案和老师批注，原样输出。")
    except Exception:
        ocr_text = ""
    if not (ocr_text or "").strip():
        raise HTTPException(status_code=400, detail="未能识别图片，请换更清晰的照片")
    extracted = extract_drill_items(db, ocr_text)
    items = extracted.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="未能从错题提炼出知识点，请换清晰照片或手动录入")
    kind = (extracted.get("kind") or "outline").strip()
    title = (extracted.get("title") or "").strip() or "拍照错题专项"

    g = TrainingGroup(owner_id=user.id, subject=subject, title=title,
                      source="custom", kind=kind)
    db.add(g); db.flush()
    for it in items:
        db.add(TrainingItem(group_id=g.id, kind=it.get("kind") or "drill_item",
                            primary=it.get("primary") or "",
                            secondary=it.get("secondary") or "",
                            example=it.get("example") or "",
                            keywords=json.dumps(it.get("keywords") or [], ensure_ascii=False)))
    db.flush()

    from ..services.drill_rule import generate_group_content
    items_payload = [{"primary": it.get("primary", ""), "secondary": it.get("secondary", "")} for it in items]
    content = generate_group_content(db, subject, kind, items_payload)
    g.intro = json.dumps(content["intro"], ensure_ascii=False)
    g.group_rule = json.dumps(content["group_rule"], ensure_ascii=False)
    mistakes = content["common_mistakes"]
    for payload in items_payload:
        if payload["primary"] in mistakes:
            row = db.query(TrainingItem).filter_by(group_id=g.id, primary=payload["primary"]).first()
            if row:
                row.common_mistake = json.dumps(mistakes[payload["primary"]], ensure_ascii=False)
    from ..services.drill_review import review_group_items
    g.ai_review = json.dumps(review_group_items(db, subject, kind, items_payload), ensure_ascii=False)
    db.commit()
    return {"group_id": g.id, "items_count": len(items), "kind": kind}
