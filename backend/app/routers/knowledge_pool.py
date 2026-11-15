import json
import shutil

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.deps import require_role
from ..database import get_db
from ..models import KnowledgePointPool, TrainingPlan, KnowledgeFolder, User

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
            "document_id": p.document_id, "folder_id": p.folder_id,
            "tags": p.tags}


class PointIn(BaseModel):
    subject: str = ""
    category: str = ""
    content: str = ""
    extra: str = "{}"
    folder_id: int | None = None
    tags: list[str] = []


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
                           content=req.content, extra=req.extra, source="manual",
                           folder_id=req.folder_id,
                           tags=json.dumps(req.tags, ensure_ascii=False))
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
    if "folder_id" in req.model_fields_set:
        p.folder_id = req.folder_id
    if "tags" in req.model_fields_set:
        p.tags = json.dumps(req.tags, ensure_ascii=False)
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
    from ..models import TrainingItem
    if db.query(TrainingItem.id).filter_by(point_pool_id=point_id).first():
        return {"error": "该知识点已被训练方案发布使用，无法删除"}
    db.delete(p); db.commit()
    return {"ok": True}


class FolderIn(BaseModel):
    name: str = ""
    subject: str = ""
    parent_id: int | None = None


class MoveIn(BaseModel):
    folder_id: int | None = None


class TagsIn(BaseModel):
    tags: list[str] = []


def _folder_tree(db: Session, owner_id: int, subject: str = "") -> list[dict]:
    q = db.query(KnowledgeFolder).filter(KnowledgeFolder.owner_id == owner_id)
    if subject:
        q = q.filter(KnowledgeFolder.subject == subject)
    folders = q.order_by(KnowledgeFolder.id).all()
    count_map = dict(db.query(KnowledgePointPool.folder_id, func.count(KnowledgePointPool.id))
                     .filter(KnowledgePointPool.folder_id.isnot(None))
                     .group_by(KnowledgePointPool.folder_id).all())
    nodes = {f.id: {"id": f.id, "name": f.name, "subject": f.subject,
                    "parent_id": f.parent_id, "point_count": int(count_map.get(f.id, 0)),
                    "children": []} for f in folders}
    roots = []
    for f in folders:
        if f.parent_id and f.parent_id in nodes:
            nodes[f.parent_id]["children"].append(nodes[f.id])
        else:
            roots.append(nodes[f.id])
    return roots


@router.get("/knowledge-folders")
def list_folders(subject: str = "", user: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    if user.role == "admin":
        return []
    return _folder_tree(db, user.id, subject)


@router.post("/knowledge-folders")
def create_folder(req: FolderIn, user: User = Depends(require_role("parent", "admin")),
                  db: Session = Depends(get_db)):
    if not (req.name or "").strip():
        return {"error": "目录名不能为空"}
    if req.parent_id is not None:
        pf = db.get(KnowledgeFolder, req.parent_id)
        if pf is None:
            return {"error": "父目录不存在"}
        if user.role != "admin" and pf.owner_id != user.id:
            return {"error": "无权操作"}
    f = KnowledgeFolder(owner_id=user.id, name=req.name.strip(), subject=req.subject,
                        parent_id=req.parent_id)
    db.add(f); db.commit(); db.refresh(f)
    return {"id": f.id}


@router.put("/knowledge-folders/{folder_id}")
def update_folder(folder_id: int, req: FolderIn,
                  user: User = Depends(require_role("parent", "admin")),
                  db: Session = Depends(get_db)):
    f = _own(db, user, KnowledgeFolder, folder_id)
    if f is None:
        return {"error": "not found"}
    if f is False:
        return {"error": "无权操作"}
    if req.name.strip():
        f.name = req.name.strip()
    if req.parent_id is not None:
        pf = db.get(KnowledgeFolder, req.parent_id)
        if pf is None:
            return {"error": "父目录不存在"}
        if user.role != "admin" and pf.owner_id != user.id:
            return {"error": "无权操作"}
        f.parent_id = req.parent_id
    db.commit()
    return {"id": f.id}


@router.delete("/knowledge-folders/{folder_id}")
def delete_folder(folder_id: int, user: User = Depends(require_role("parent", "admin")),
                  db: Session = Depends(get_db)):
    f = _own(db, user, KnowledgeFolder, folder_id)
    if f is None:
        return {"error": "not found"}
    if f is False:
        return {"error": "无权操作"}
    has_child = db.query(KnowledgeFolder.id).filter_by(parent_id=folder_id).first()
    has_point = db.query(KnowledgePointPool.id).filter_by(folder_id=folder_id).first()
    if has_child or has_point:
        return {"error": "目录非空，请先移走子目录和知识点"}
    db.delete(f); db.commit()
    return {"ok": True}


@router.put("/knowledge-pool/{point_id}/move")
def move_point(point_id: int, req: MoveIn, user: User = Depends(require_role("parent", "admin")),
               db: Session = Depends(get_db)):
    p = _own(db, user, KnowledgePointPool, point_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    if req.folder_id is not None:
        tf = db.get(KnowledgeFolder, req.folder_id)
        if tf is None:
            return {"error": "目录不存在"}
        if user.role != "admin" and tf.owner_id != user.id:
            return {"error": "无权操作"}
    p.folder_id = req.folder_id
    db.commit()
    return {"id": p.id, "folder_id": p.folder_id}


@router.put("/knowledge-pool/{point_id}/tags")
def set_point_tags(point_id: int, req: TagsIn, user: User = Depends(require_role("parent", "admin")),
                   db: Session = Depends(get_db)):
    p = _own(db, user, KnowledgePointPool, point_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    p.tags = json.dumps(req.tags, ensure_ascii=False)
    db.commit()
    return {"id": p.id, "tags": p.tags}


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
        folder = None
        if items:
            folder_name = os.path.splitext(safe_name)[0] or "未命名讲义"
            folder = KnowledgeFolder(owner_id=user.id, name=folder_name, subject=subject, parent_id=None)
            db.add(folder); db.flush()
        created = 0
        for it in items:
            extra = {"释义": it.get("secondary") or "", "原句": it.get("example") or ""}
            db.add(KnowledgePointPool(
                owner_id=user.id, subject=subject, category=handout_kind,
                content=it.get("primary") or "", source="pdf",
                document_id=doc.id, folder_id=folder.id if folder else None,
                extra=json.dumps(extra, ensure_ascii=False)))
            created += 1
        db.commit()
        return {"document_id": doc.id, "count": created, "folder_id": folder.id if folder else None}
    finally:
        # 渲染页为纯中间产物（无 reader 页面引用），清理；源 PDF 保留，供 document_id 溯源
        shutil.rmtree(out_dir, ignore_errors=True)


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
    if ids:
        q = db.query(KnowledgePointPool).filter(KnowledgePointPool.id.in_(ids))
        if user.role != "admin":
            q = q.filter(KnowledgePointPool.owner_id == user.id)
        points = q.all()
    else:
        points = []
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
    from ..models import TrainingGroup, TrainingItem, TrainingItemMastery
    if p.group_id:
        gid = p.group_id
        item_ids = [r[0] for r in db.query(TrainingItem.id).filter_by(group_id=gid).all()]
        for iid in item_ids:
            db.query(TrainingItemMastery).filter_by(item_id=iid).delete()
        db.query(TrainingItem).filter_by(group_id=gid).delete()
        # 先解除 plan → group 的 FK 并 flush，再删 group，避免外键约束失败
        p.group_id = None
        db.flush()
        db.query(TrainingGroup).filter_by(id=gid).delete()
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
