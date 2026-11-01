"""沉浸式阅读标注：划线/下划线/笔记/生词释义，标注内联在正文旁。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Annotation, User
from ..services.ai import get_provider

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


def _owner_id(db: Session, user_id: int | None) -> int | None:
    """标注归属：优先请求里的有效用户，否则同 /api/ask 取第一个孩子（user_id 是外键，不能写 0）。"""
    if user_id and db.get(User, user_id):
        return user_id
    child = db.query(User).filter_by(role="child").first()
    return child.id if child else None


@router.get("")
def list_annotations(lesson_id: int, db: Session = Depends(get_db)):
    rows = db.query(Annotation).filter_by(lesson_id=lesson_id).order_by(Annotation.id).all()
    return [
        {"id": a.id, "lesson_id": a.lesson_id, "kind": a.kind, "quote": a.quote,
         "note": a.note, "color": a.color, "page_number": a.page_number, "rects": a.rects}
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
def add_annotation(req: AnnotationReq, db: Session = Depends(get_db)):
    owner = _owner_id(db, req.user_id)
    if owner is None:
        return {"error": "没有孩子账号，无法保存标注"}
    a = Annotation(lesson_id=req.lesson_id, user_id=owner, kind=req.kind, quote=req.quote,
                   note=req.note, color=req.color, page_number=req.page_number,
                   rects=req.rects)
    db.add(a); db.commit(); db.refresh(a)
    return {"id": a.id, "kind": a.kind, "quote": a.quote, "note": a.note,
            "color": a.color, "page_number": a.page_number, "rects": a.rects}


@router.delete("/{annotation_id}")
def delete_annotation(annotation_id: int, db: Session = Depends(get_db)):
    a = db.get(Annotation, annotation_id)
    if a:
        db.delete(a); db.commit()
        return {"ok": True}
    return {"ok": False, "error": "not found"}


class GlossaryReq(BaseModel):
    lesson_id: int
    quote: str
    page_number: int = 1
    rects: str = ""
    user_id: int | None = None


@router.post("/glossary")
def glossary(req: GlossaryReq, db: Session = Depends(get_db)):
    """选中词/词组 → AI 现查释义，落库为 kind='glossary' 标注。"""
    owner = _owner_id(db, req.user_id)
    if owner is None:
        return {"error": "没有孩子账号，无法保存标注"}
    provider = get_provider(db)
    try:
        meaning = provider.generate(
            prompt=f"请解释教材中的这个词：「{req.quote}」。用小学生能懂的话说明它的意思，50 字以内。",
            system="你是小学生的学习助手，解释生词要简洁、准确。",
        ).strip()
    except Exception:
        # TODO: AI 释义失败时返回占位假释义，需改为真实兜底（词典查词）或提示用户
        meaning = f"「{req.quote}」的释义（示例）"
    a = Annotation(lesson_id=req.lesson_id, user_id=owner, kind="glossary", quote=req.quote,
                   note=meaning, color="green", page_number=req.page_number,
                   rects=req.rects)
    db.add(a); db.commit(); db.refresh(a)
    return {"id": a.id, "kind": a.kind, "quote": a.quote, "note": a.note,
            "page_number": a.page_number, "rects": a.rects}
