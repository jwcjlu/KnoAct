"""任务接口：列/审核/改/删/增/提交/上传/确认。"""
import os
from datetime import date

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Task, Point
from ..services.task_gen import generate_daily_tasks

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 5 * 1024 * 1024  # 5MB


class ApproveAllReq(BaseModel):
    user_id: int
    date: date


class EditReq(BaseModel):
    title: str = ""
    detail: str = ""
    content: str = ""


class AddReq(BaseModel):
    user_id: int
    date: date
    subject: str = "语文"
    task_type: str = "custom"
    title: str = ""
    detail: str = ""
    content: str = ""
    points: int = 20


def _to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "subject": t.subject,
        "task_type": t.task_type,
        "title": t.title,
        "detail": t.detail,
        "content": t.content,
        "points": t.points,
        "content_status": t.content_status,
        "submit_status": t.submit_status,
        "photo_path": t.photo_path,
    }


@router.get("")
def list_tasks(user_id: int, date: date, role: str = "child", db: Session = Depends(get_db)):
    q = db.query(Task).filter_by(user_id=user_id, date=date)
    if role == "child":
        q = q.filter_by(content_status="published")
    tasks = q.order_by(Task.id).all()
    return [_to_dict(t) for t in tasks]


@router.post("/generate")
def generate(d: date, db: Session = Depends(get_db)):
    generate_daily_tasks(db, d)
    return {"ok": True}


@router.post("/approve-all")
def approve_all(req: ApproveAllReq, db: Session = Depends(get_db)):
    db.query(Task).filter_by(user_id=req.user_id, date=req.date, content_status="pending_review").update(
        {"content_status": "published"}, synchronize_session=False
    )
    db.commit()
    return {"ok": True}


@router.post("/{task_id}/approve")
def approve(task_id: int, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    if t.content_status == "pending_review":
        t.content_status = "published"
        db.commit()
    return {"ok": True}


@router.put("/{task_id}")
def edit_task(task_id: int, req: EditReq, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    if req.title:
        t.title = req.title
    if req.detail:
        t.detail = req.detail
    if req.content:
        t.content = req.content
    db.commit()
    return {"ok": True}


@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.post("")
def add_task(req: AddReq, db: Session = Depends(get_db)):
    t = Task(
        user_id=req.user_id,
        date=req.date,
        subject=req.subject,
        task_type=req.task_type,
        title=req.title,
        detail=req.detail,
        content=req.content,
        points=req.points,
        content_status="published",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id}


@router.post("/{task_id}/submit")
def submit(task_id: int, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    if t.submit_status != "approved":
        t.submit_status = "submitted"
        db.commit()
    return {"ok": True}


@router.post("/{task_id}/upload-photo")
async def upload_photo(task_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        return {"ok": False, "error": "unsupported file type"}
    data = await file.read()
    if len(data) > MAX_BYTES:
        return {"ok": False, "error": "file too large"}
    os.makedirs("uploads/task_photos", exist_ok=True)
    path = f"uploads/task_photos/task_{task_id}{ext}"
    with open(path, "wb") as f:
        f.write(data)
    t.photo_path = path
    db.commit()
    return {"ok": True, "path": path}


@router.post("/{task_id}/confirm")
def confirm(task_id: int, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    if t.submit_status == "approved":
        return {"ok": True, "points": t.points, "already": True}
    if t.submit_status != "submitted":
        return {"ok": False, "error": "任务尚未提交，无法确认"}
    t.submit_status = "approved"
    db.add(Point(user_id=t.user_id, delta=t.points, reason=f"任务完成：{t.title}"))
    db.commit()
    return {"ok": True, "points": t.points}
