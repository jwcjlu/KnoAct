import json
import shutil

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import require_role
from ..database import get_db
from ..models import KnowledgePointPool, TrainingPlan, User

router = APIRouter(prefix="/api", tags=["knowledge-pool"])


def _own(db: Session, user: User, model, obj_id: int):
    obj = db.get(model, obj_id)
    if obj is None:
        return None
    if user.role != "admin" and obj.owner_id != user.id:
        return False
    return obj


def _point_dict(p: KnowledgePointPool) -> dict:
    return {"id": p.id, "subject": p.subject, "category": p.category,
            "content": p.content, "extra": p.extra, "source": p.source,
            "document_id": p.document_id}


class PointIn(BaseModel):
    subject: str = ""
    category: str = ""
    content: str = ""
    extra: str = "{}"


@router.get("/knowledge-pool")
def list_points(subject: str = "", category: str = "",
                user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    q = db.query(KnowledgePointPool)
    if user.role != "admin":
        q = q.filter(KnowledgePointPool.owner_id == user.id)
    if subject:
        q = q.filter(KnowledgePointPool.subject == subject)
    if category:
        q = q.filter(KnowledgePointPool.category == category)
    return [_point_dict(p) for p in q.order_by(KnowledgePointPool.id.desc()).all()]


@router.post("/knowledge-pool")
def create_point(req: PointIn, user: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    p = KnowledgePointPool(owner_id=user.id, subject=req.subject, category=req.category,
                           content=req.content, extra=req.extra, source="manual")
    db.add(p); db.commit(); db.refresh(p)
    return _point_dict(p)


@router.put("/knowledge-pool/{point_id}")
def update_point(point_id: int, req: PointIn,
                 user: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    p = _own(db, user, KnowledgePointPool, point_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    p.subject = req.subject or p.subject
    p.category = req.category or p.category
    p.content = req.content or p.content
    p.extra = req.extra if req.extra != "{}" else p.extra
    db.commit()
    return _point_dict(p)


@router.delete("/knowledge-pool/{point_id}")
def delete_point(point_id: int, user: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    p = _own(db, user, KnowledgePointPool, point_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    db.delete(p); db.commit()
    return {"ok": True}


@router.post("/knowledge-pool/from-pdf")
async def from_pdf(subject: str = Form(...), handout_kind: str = Form("outline"),
                   file: UploadFile = File(...),
                   user: User = Depends(require_role("parent", "admin")),
                   db: Session = Depends(get_db)):
    """上传讲义 PDF → OCR → 提取知识点 → 写知识点库（不建训练）。"""
    import os
    from ..models import PdfDocument
    from ..services.pdf_split import render_pages, _ocr_page
    from ..services.drill_rule import extract_items_from_pages

    data = await file.read()
    if not data:
        return {"error": "请上传 PDF"}
    os.makedirs("uploads", exist_ok=True)
    doc = PdfDocument(filename=file.filename, subject=subject, storage_path="",
                      content_kind="handout", handout_kind=handout_kind)
    db.add(doc); db.commit(); db.refresh(doc)
    safe_name = os.path.basename(file.filename or "upload.pdf")
    path = f"uploads/{doc.id}_{safe_name}"
    out_dir = f"uploads/{doc.id}_pages"
    with open(path, "wb") as f:
        f.write(data)
    doc.storage_path = path
    db.commit()

    try:
        pages = render_pages(doc.id, path, out_dir)
        ocr_pages = []
        for p in pages:
            text = _ocr_page(path, p["page_number"] - 1, db, "识别这张讲义页面中的全部文字，原样输出。")
            ocr_pages.append({"page_number": p["page_number"], "text": text})

        items = extract_items_from_pages(db, handout_kind, ocr_pages)
        created = 0
        for it in items:
            extra = {"释义": it.get("secondary") or ""}
            db.add(KnowledgePointPool(
                owner_id=user.id, subject=subject, category=handout_kind,
                content=it.get("primary") or "", source="pdf",
                document_id=doc.id,
                extra=json.dumps(extra, ensure_ascii=False)))
            created += 1
        db.commit()
        return {"document_id": doc.id, "count": created}
    finally:
        # 纯中间产物：无 reader 页面引用，清理渲染页目录与源 PDF，避免磁盘无限增长
        shutil.rmtree(out_dir, ignore_errors=True)
        try:
            os.remove(path)
        except OSError:
            pass


class PlanIn(BaseModel):
    subject: str = ""
    title: str = ""
    point_ids: list[int] = []


@router.get("/plans")
def list_plans(user: User = Depends(require_role("parent", "admin")),
               db: Session = Depends(get_db)):
    q = db.query(TrainingPlan)
    if user.role != "admin":
        q = q.filter(TrainingPlan.owner_id == user.id)
    return [{"id": p.id, "subject": p.subject, "title": p.title,
             "point_ids": json.loads(p.point_ids or "[]"),
             "group_id": p.group_id, "status": p.status} for p in q.order_by(TrainingPlan.id.desc()).all()]


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, user: User = Depends(require_role("parent", "admin")),
             db: Session = Depends(get_db)):
    p = _own(db, user, TrainingPlan, plan_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    ids = json.loads(p.point_ids or "[]")
    points = db.query(KnowledgePointPool).filter(KnowledgePointPool.id.in_(ids)).all() if ids else []
    return {"id": p.id, "subject": p.subject, "title": p.title,
            "point_ids": ids, "group_id": p.group_id, "status": p.status,
            "points": [_point_dict(x) for x in points]}


@router.post("/plans")
def create_plan(req: PlanIn, user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    p = TrainingPlan(owner_id=user.id, subject=req.subject, title=req.title,
                     point_ids=json.dumps(req.point_ids))
    db.add(p); db.commit(); db.refresh(p)
    return {"id": p.id}


@router.put("/plans/{plan_id}")
def update_plan(plan_id: int, req: PlanIn,
                user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    p = _own(db, user, TrainingPlan, plan_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    p.subject = req.subject or p.subject
    p.title = req.title or p.title
    if req.point_ids:
        p.point_ids = json.dumps(req.point_ids)
    from datetime import datetime
    p.updated_at = datetime.utcnow()
    db.commit()
    return {"id": p.id, "point_ids": json.loads(p.point_ids or "[]")}


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    p = _own(db, user, TrainingPlan, plan_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    db.delete(p); db.commit()
    return {"ok": True}


@router.post("/plans/{plan_id}/publish")
def publish_plan(plan_id: int, user: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    from ..services.plan_publish import publish_plan as _publish
    p = _own(db, user, TrainingPlan, plan_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    try:
        group, count = _publish(db, p)
    except ValueError as e:
        return {"error": str(e)}
    return {"group_id": group.id, "item_count": count}
