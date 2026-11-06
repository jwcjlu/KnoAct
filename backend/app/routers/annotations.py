"""沉浸式阅读标注：划线/下划线/笔记/生词释义，标注内联在正文旁。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import ensure_lesson_document_access, ensure_user_access
from ..core.deps import get_current_user
from ..database import get_db
from ..models import Annotation, User
from ..services.ai import get_provider

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


@router.get("")
def list_annotations(
    lesson_id: int,
    user_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject_id = user_id if user_id is not None else user.id
    ensure_user_access(user, subject_id, db)
    viewer = db.get(User, subject_id)
    if viewer is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    ensure_lesson_document_access(viewer, lesson_id, db)
    rows = db.query(Annotation).filter_by(lesson_id=lesson_id).order_by(Annotation.id).all()
    return [
        {
            "id": a.id,
            "lesson_id": a.lesson_id,
            "kind": a.kind,
            "quote": a.quote,
            "note": a.note,
            "color": a.color,
            "page_number": a.page_number,
            "rects": a.rects,
        }
        for a in rows
    ]


class AnnotationReq(BaseModel):
    lesson_id: int
    kind: str = "highlight"          # highlight | underline | note | glossary
    quote: str
    note: str = ""
    color: str = "yellow"
    page_number: int = 1
    rects: str = ""                  # JSON 文本 [[x0,y0,x1,y1],...] 归一化坐标
    user_id: int | None = None


@router.post("")
def add_annotation(
    req: AnnotationReq,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject_id = req.user_id if req.user_id is not None else user.id
    ensure_user_access(user, subject_id, db)
    viewer = db.get(User, subject_id)
    if viewer is None or viewer.role != "child":
        raise HTTPException(status_code=400, detail="标注需归属孩子账号")
    ensure_lesson_document_access(viewer, req.lesson_id, db)
    a = Annotation(
        lesson_id=req.lesson_id,
        user_id=viewer.id,
        kind=req.kind,
        quote=req.quote,
        note=req.note,
        color=req.color,
        page_number=req.page_number,
        rects=req.rects,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return {
        "id": a.id,
        "kind": a.kind,
        "quote": a.quote,
        "note": a.note,
        "color": a.color,
        "page_number": a.page_number,
        "rects": a.rects,
    }


@router.delete("/{annotation_id}")
def delete_annotation(
    annotation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = db.get(Annotation, annotation_id)
    if a:
        ensure_user_access(user, a.user_id, db)
        viewer = db.get(User, a.user_id)
        if viewer:
            ensure_lesson_document_access(viewer, a.lesson_id, db)
        db.delete(a)
        db.commit()
        return {"ok": True}
    return {"ok": False, "error": "not found"}


class GlossaryReq(BaseModel):
    lesson_id: int
    quote: str
    page_number: int = 1
    rects: str = ""
    user_id: int | None = None


@router.post("/glossary")
def glossary(
    req: GlossaryReq,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """选中词/词组 → AI 现查释义，落库为 kind='glossary' 标注。"""
    subject_id = req.user_id if req.user_id is not None else user.id
    ensure_user_access(user, subject_id, db)
    viewer = db.get(User, subject_id)
    if viewer is None or viewer.role != "child":
        raise HTTPException(status_code=400, detail="标注需归属孩子账号")
    ensure_lesson_document_access(viewer, req.lesson_id, db)
    provider = get_provider(db, child_id=viewer.id)
    try:
        meaning = provider.generate(
            prompt=f"请解释教材中的这个词：「{req.quote}」。用小学生能懂的话说明它的意思，50 字以内。",
            system="你是小学生的学习助手，解释生词要简洁、准确。",
        ).strip()
    except Exception:
        # TODO: AI 释义失败时返回占位假释义，需改为真实兜底（词典查词）或提示用户
        meaning = f"「{req.quote}」的释义（示例）"
    a = Annotation(
        lesson_id=req.lesson_id,
        user_id=viewer.id,
        kind="glossary",
        quote=req.quote,
        note=meaning,
        color="green",
        page_number=req.page_number,
        rects=req.rects,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return {
        "id": a.id,
        "kind": a.kind,
        "quote": a.quote,
        "note": a.note,
        "page_number": a.page_number,
        "rects": a.rects,
    }
