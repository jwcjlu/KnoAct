from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access, require_learning_user
from ..core.deps import require_role
from ..database import get_db
from ..models import LearningProgress, Lesson, PdfDocument, User, UserDocument
from ..services.learning_progress import (
    advance_lesson, ensure_progress, get_progress, lesson_index,
)

router = APIRouter(prefix="/api/progress", tags=["progress"])


class AdvanceReq(BaseModel):
    user_id: int
    correct: int
    total: int
    subject: str = "语文"
    document_id: int | None = None


class AdjustReq(BaseModel):
    user_id: int
    lesson_id: int
    subject: str = "语文"
    document_id: int | None = None


@router.post("/advance")
def advance(req: AdvanceReq, user: User = Depends(require_learning_user),
            db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    from ..models import ModelConfig

    row = db.query(ModelConfig).filter_by(key="assignment_pass_threshold").first()
    try:
        threshold = float(row.value) if row and row.value else 0.6
    except ValueError:
        threshold = 0.6
    rate = req.correct / req.total if req.total else 0
    passed = rate >= threshold
    if passed:
        doc_id = req.document_id
        if doc_id is None:
            # 没指定教材：用进度当前课所属的教材，再退回该科第一本绑定教材
            prog = get_progress(db, req.user_id, None, req.subject)
            if prog and prog.current_lesson_id:
                lesson = db.get(Lesson, prog.current_lesson_id)
                doc_id = lesson.document_id if lesson else None
            if doc_id is None:
                b = (db.query(UserDocument.document_id)
                     .filter_by(user_id=req.user_id).first())
                doc_id = b[0] if b else None
        advance_lesson(db, req.user_id, doc_id, req.subject)
        db.commit()
    return {"passed": passed, "rate": rate}


@router.post("/adjust")
def adjust(req: AdjustReq, user: User = Depends(require_learning_user),
           db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    lesson = db.get(Lesson, req.lesson_id)
    if lesson is None:
        raise HTTPException(404, "课不存在")
    doc_id = req.document_id if req.document_id is not None else lesson.document_id
    prog = ensure_progress(db, req.user_id, doc_id, lesson.subject)
    prog.current_lesson_id = lesson.id
    db.commit()
    return {
        "user_id": req.user_id,
        "subject": lesson.subject,
        "document_id": prog.document_id,
        "current_lesson_id": prog.current_lesson_id,
        "current": lesson_index(db, lesson)[0],
        "total": lesson_index(db, lesson)[1],
    }


@router.get("/overview")
def overview(
    user_id: int = Query(...),
    subject: str | None = Query(None),
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """家长端用：列出该孩子每本已绑定教材的当前课与总课数，供直接调整。"""
    ensure_user_access(user, user_id, db)
    bound = [r[0] for r in
             db.query(UserDocument.document_id).filter_by(user_id=user_id).all()]
    q = db.query(PdfDocument).filter(PdfDocument.id.in_(bound)) if bound else None
    docs = q.order_by(PdfDocument.id).all() if q is not None else []

    out = []
    for d in docs:
        if subject and d.subject != subject:
            continue
        lessons = (db.query(Lesson)
                   .filter_by(document_id=d.id, subject=d.subject)
                   .order_by(Lesson.id).all())
        if not lessons:
            continue
        prog = get_progress(db, user_id, d.id, d.subject)
        cur = None
        if prog and prog.current_lesson_id:
            cur = next((l for l in lessons if l.id == prog.current_lesson_id), None)
        cur = cur or lessons[0]
        idx, total = lesson_index(db, cur)
        out.append({
            "document_id": d.id,
            "document_name": d.filename,
            "subject": d.subject,
            "grade": d.grade,
            "edition": d.edition,
            "current": idx,
            "total": total,
            "current_lesson_id": cur.id,
            # 让家长端可以直接渲染下拉框
            "lessons": [{"id": l.id, "title": l.title,
                         "audit_status": l.audit_status} for l in lessons],
        })
    return {"items": out}
