"""练习册导入：上传 PDF、查进度、重试失败页、补答案、课时列表。"""
import json
import os
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access, require_learning_user
from ..core.deps import require_role
from ..database import get_db
from ..models import PdfDocument, PdfPage, PracticeImportJob, Question, QuestionBank, User
from ..services.model_config import resolve as resolve_model
from ..services.pdf_split import render_pages
from ..services.practice_import import run_import_job

router = APIRouter(tags=["practice-import"])

_MAX_BYTES = 120 * 1024 * 1024
PRACTICE_SOURCE = "practice_pdf"


class PracticeBookReq(BaseModel):
    title: str
    subject: str = "数学"
    grade: int | None = None


class PatchQuestionReq(BaseModel):
    answer: str | None = None
    question: str | None = None
    analysis: str | None = None


def _require_own_bank(bank_id: int, user: User, db: Session) -> QuestionBank:
    bank = db.get(QuestionBank, bank_id)
    if bank is None:
        raise HTTPException(status_code=404, detail={"error": "bank_not_found"})
    if user.role != "admin" and bank.user_id != user.id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    return bank


def _vision_ready(db: Session) -> bool:
    """OCR 需要 OpenAI 兼容（有 base_url）且非 fake 的 llm 档。"""
    try:
        r = resolve_model(db, "llm")
    except Exception:
        return False
    return r.provider != "fake" and bool(r.api_key) and bool(r.base_url)


@router.post("/api/banks/practice-book")
def create_practice_book(
    req: PracticeBookReq,
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """新建一个练习册卷（source=practice_pdf）。"""
    bank = QuestionBank(
        user_id=user.id,
        title=req.title.strip(),
        subject=req.subject,
        grade=req.grade,
        source=PRACTICE_SOURCE,
    )
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return {"id": bank.id, "title": bank.title}


@router.post("/api/banks/{bank_id}/import-practice-pdf")
def import_practice_pdf(
    bank_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    answer_start_page: str = Form(""),
    answer_end_page: str = Form(""),
    question_start_page: str = Form(""),
    question_end_page: str = Form(""),
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    bank = _require_own_bank(bank_id, user, db)

    def _int(s: str) -> int | None:
        s = (s or "").strip()
        return int(s) if s.isdigit() else None

    a_start, a_end = _int(answer_start_page), _int(answer_end_page)
    if not a_start or not a_end:
        raise HTTPException(
            status_code=400, detail="必须填写答案页起止页（扫描版无法自动识别）"
        )

    if not _vision_ready(db):
        raise HTTPException(
            status_code=400,
            detail="未配置可用的视觉模型：需要 OpenAI 兼容 / 中转站的 llm 档才能 OCR"
            "（deepseek、glm 这类内置 base_url 的 provider 无法用于 OCR）",
        )

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="只支持 PDF")
    data = file.file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="PDF 超过 120MB")

    os.makedirs("uploads/practice", exist_ok=True)
    safe = f"practice_{uuid.uuid4().hex}{ext}"
    path = f"uploads/practice/{safe}"
    with open(path, "wb") as f:
        f.write(data)

    doc = PdfDocument(
        filename=os.path.basename(file.filename or safe),
        subject=bank.subject or "数学",
        storage_path=path,
        grade=bank.grade,
        content_kind="practice",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    pages = render_pages(doc.id, path, f"uploads/{doc.id}_pages")
    for p in pages:
        db.add(
            PdfPage(
                document_id=doc.id,
                page_number=p["page_number"],
                image_path=p["image_path"],
            )
        )
    db.commit()

    total = len(pages)
    if a_start < 1 or a_end > total or a_start > a_end:
        raise HTTPException(
            status_code=400, detail=f"答案页范围非法：文档共 {total} 页"
        )

    q_start = _int(question_start_page) or 1
    q_end = _int(question_end_page) or (a_start - 1)

    job = PracticeImportJob(
        user_id=user.id,
        bank_id=bank.id,
        document_id=doc.id,
        total_pages=total,
        question_start_page=q_start,
        question_end_page=q_end,
        answer_start_page=a_start,
        answer_end_page=a_end,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background.add_task(run_import_job, job.id)
    return {"job_id": job.id, "document_id": doc.id, "total_pages": total}


@router.get("/api/practice-import/jobs/{job_id}")
def get_job(
    job_id: int,
    user: User = Depends(require_learning_user),
    db: Session = Depends(get_db),
):
    job = db.get(PracticeImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found"})
    ensure_user_access(user, job.user_id, db)
    return {
        "id": job.id,
        "status": job.status,
        "total_pages": job.total_pages,
        "done_pages": job.done_pages,
        "question_count": job.question_count,
        "aligned_count": job.aligned_count,
        "published_count": job.published_count,
        "failed_pages": json.loads(job.failed_pages or "[]"),
        "error": job.error,
    }


@router.post("/api/practice-import/jobs/{job_id}/retry")
def retry_job(
    job_id: int,
    background: BackgroundTasks,
    user: User = Depends(require_learning_user),
    db: Session = Depends(get_db),
):
    """只重跑上次失败的页（成功页不重跑，省 OCR 费用）。"""
    job = db.get(PracticeImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found"})
    ensure_user_access(user, job.user_id, db)

    try:
        pages = json.loads(job.failed_pages or "[]")
    except (ValueError, TypeError):
        pages = []
    if not pages:
        return {"ok": False, "message": "没有失败页需要重试"}

    job.status = "pending"
    job.error = ""
    db.commit()
    background.add_task(run_import_job, job.id, list(pages))
    return {"ok": True, "retry_pages": pages}


@router.get("/api/practice-import/missing-answers")
def missing_answers(
    bank_id: int = Query(...),
    user: User = Depends(require_learning_user),
    db: Session = Depends(get_db),
):
    bank = _require_own_bank(bank_id, user, db)
    rows = (
        db.query(Question)
        .filter(
            Question.bank_id == bank.id,
            Question.status == "pending",
            Question.answer == "",
        )
        .order_by(Question.lesson_no, Question.question_no)
        .all()
    )
    return {
        "items": [
            {
                "id": q.id,
                "lesson_no": q.lesson_no,
                "lesson_title": q.lesson_title,
                "question_no": q.question_no,
                "question": q.question,
            }
            for q in rows
        ]
    }


@router.patch("/api/practice-import/questions/{question_id}")
def patch_question(
    question_id: int,
    req: PatchQuestionReq,
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail={"error": "question_not_found"})
    bank = db.get(QuestionBank, q.bank_id) if q.bank_id else None
    if bank is None or (user.role != "admin" and bank.user_id != user.id):
        raise HTTPException(status_code=403, detail={"error": "forbidden"})

    if req.question is not None:
        q.question = req.question
    if req.analysis is not None:
        q.analysis = req.analysis
    if req.answer is not None:
        q.answer = req.answer.strip()
        if q.qtype in ("fill_blank", "cloze") and q.answer:
            parts = [p for p in q.answer.replace("，", ",").split(",") if p.strip()]
            q.answer_json = json.dumps(
                {"blanks": [p.strip() for p in parts]}, ensure_ascii=False
            )
        if q.answer:
            q.status = "published"
    db.commit()
    return {"id": q.id, "status": q.status}


@router.get("/api/practice-import/lessons")
def lessons(
    bank_id: int = Query(...),
    user: User = Depends(require_learning_user),
    db: Session = Depends(get_db),
):
    bank = _require_own_bank(bank_id, user, db)
    rows = (
        db.query(
            Question.lesson_no,
            func.max(Question.lesson_title),
            func.count(Question.id),
        )
        .filter(
            Question.bank_id == bank.id,
            Question.status == "published",
            Question.lesson_no.isnot(None),
        )
        .group_by(Question.lesson_no)
        .order_by(Question.lesson_no)
        .all()
    )
    return {
        "lessons": [
            {"lesson_no": no, "title": title or "", "count": cnt}
            for no, title, cnt in rows
        ]
    }
