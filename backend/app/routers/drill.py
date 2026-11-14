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
    kind: str = ""  # 空 = 按学科推断；显式传则覆盖
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
    from ..models import PdfDocument
    from ..services.drill_rule import infer_kind
    subject = (req.subject or "").strip()
    document_id = req.document_id
    # 讲义：subject 强制继承 PDF 的学科，不允许错配
    if req.source == "handout" and document_id is not None:
        from fastapi import HTTPException
        doc = db.get(PdfDocument, document_id)
        if not doc or doc.content_kind != "handout":
            raise HTTPException(status_code=400, detail="讲义不存在")
        subject = doc.subject
    kind = infer_kind(subject, req.kind)
    g = TrainingGroup(owner_id=user.id, subject=subject, title=req.title,
                      source=req.source, kind=kind, document_id=document_id,
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
    content = generate_group_content(db, subject, kind, items_payload)
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
    g.ai_review = json.dumps(review_group_items(db, subject, kind, items_payload), ensure_ascii=False)
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


@router.get("/groups")
def list_groups(user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    """列出当前家长建的专项组（含条目数、ai_review 解析）。admin 看全部，家长看自己的。"""
    from sqlalchemy import func
    q = db.query(TrainingGroup)
    if user.role != "admin":
        q = q.filter(TrainingGroup.owner_id == user.id)
    groups = q.order_by(TrainingGroup.id.desc()).all()
    counts = dict(db.query(TrainingItem.group_id, func.count(TrainingItem.id))
                  .group_by(TrainingItem.group_id).all())
    out = []
    for g in groups:
        ai_review = []
        try:
            ai_review = json.loads(g.ai_review or "[]")
        except (ValueError, TypeError):
            ai_review = []
        out.append({
            "id": g.id, "subject": g.subject, "title": g.title,
            "source": g.source, "kind": g.kind,
            "audit_status": g.audit_status,
            "mastery_interval_days": g.mastery_interval_days,
            "item_count": int(counts.get(g.id, 0)),
            "ai_review": ai_review if isinstance(ai_review, list) else [],
        })
    return out


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


@router.post("/pdf-groups")
async def pdf_groups(subject: str = Form(...), handout_kind: str = Form("outline"),
                     file: UploadFile = File(...),
                     user: User = Depends(require_role("parent", "admin")),
                     db: Session = Depends(get_db)):
    """上传讲义 PDF → OCR 逐页识别 → 提取识记条目 → 建组（source=handout, pending 待审）。"""
    import os
    from fastapi import HTTPException
    from ..models import PdfDocument, PdfPage
    from ..services.pdf_split import render_pages, _ocr_page
    from ..services.drill_rule import extract_items_from_pages

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="请上传 PDF")
    os.makedirs("uploads", exist_ok=True)
    doc = PdfDocument(filename=file.filename, subject=subject, storage_path="",
                      content_kind="handout", handout_kind=handout_kind)
    db.add(doc); db.commit(); db.refresh(doc)

    safe_name = os.path.basename(file.filename or "upload.pdf")
    path = f"uploads/{doc.id}_{safe_name}"
    with open(path, "wb") as f:
        f.write(data)
    doc.storage_path = path
    db.commit()

    pages = render_pages(doc.id, path, f"uploads/{doc.id}_pages")
    for p in pages:
        db.add(PdfPage(document_id=doc.id, page_number=p["page_number"], image_path=p["image_path"]))
    db.commit()

    # 逐页 OCR（带页码）
    ocr_pages = []
    for p in pages:
        text = _ocr_page(path, p["page_number"] - 1, db, "识别这张讲义页面中的全部文字，原样输出。")
        ocr_pages.append({"page_number": p["page_number"], "text": text})

    items = extract_items_from_pages(db, handout_kind, ocr_pages)
    if not items:
        raise HTTPException(status_code=400, detail="未能从讲义识别出知识点，请换清晰 PDF 或手动录入")

    g = TrainingGroup(owner_id=user.id, subject=subject, title=doc.filename or "讲义专项",
                      source="handout", kind=handout_kind, document_id=doc.id)
    db.add(g); db.flush()
    for it in items:
        db.add(TrainingItem(group_id=g.id, kind="drill_item",
                            primary=it.get("primary") or "",
                            secondary=it.get("secondary") or "",
                            source_page=it.get("source_page") or None))
    db.flush()

    from ..services.drill_rule import generate_group_content
    items_payload = [{"primary": it.get("primary", ""), "secondary": it.get("secondary", "")} for it in items]
    content = generate_group_content(db, subject, handout_kind, items_payload)
    g.intro = json.dumps(content["intro"], ensure_ascii=False)
    g.group_rule = json.dumps(content["group_rule"], ensure_ascii=False)
    from ..services.drill_review import review_group_items
    g.ai_review = json.dumps(review_group_items(db, subject, handout_kind, items_payload), ensure_ascii=False)
    db.commit()
    return {"group_id": g.id, "items_count": len(items), "kind": handout_kind, "document_id": doc.id}
