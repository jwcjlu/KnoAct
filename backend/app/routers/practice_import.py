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
from ..core.work_modes import answer_kind_of, input_ui_of
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
    include_daily_task: bool = False


class PatchQuestionReq(BaseModel):
    answer: str | None = None
    question: str | None = None
    analysis: str | None = None


def _image_url(path: str) -> str:
    """题目图片的访问地址（/uploads 已静态挂载；空路径返回空串）。"""
    p = (path or "").strip().replace("\\", "/")
    if not p:
        return ""
    return "/" + p.lstrip("/")


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


def _derive_page_range(
    *, question_start_page, question_end_page,
    answer_start_page, answer_end_page, total_pages: int,
) -> tuple[int, int]:
    """派生题面页范围。

    答案页可选：不填答案页时题面页到最后一页为止。
    ⚠️ 绝不能写成 `(answer_start_page or 1) - 1` —— 答案页为 None 时会得到 0 页。
    提供了答案页则收窄到答案页之前，少跑几次视觉调用。
    """
    q_start = int(question_start_page or 1)
    if q_start < 1:
        q_start = 1
    q_end = question_end_page
    if not q_end and answer_start_page:
        q_end = int(answer_start_page) - 1
    q_end = int(q_end or total_pages or q_start)
    if q_end < q_start:
        q_end = q_start
    return q_start, q_end


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
        tags=json.dumps(
            {"include_daily_task": bool(req.include_daily_task)}, ensure_ascii=False
        ),
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

    from ..core.subjects import is_implemented

    if not is_implemented(bank.subject):
        raise HTTPException(
            status_code=400,
            detail=f"{bank.subject or '该'}学科练习册解析器尚未实现（当前仅支持数学）",
        )

    def _int(s: str) -> int | None:
        s = (s or "").strip()
        return int(s) if s.isdigit() else None

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
    a_start, a_end = _int(answer_start_page), _int(answer_end_page)
    if a_start is not None and a_end is not None:
        if a_start < 1 or a_end > total:
            raise HTTPException(status_code=400, detail="答案页范围不合法")
        if a_start > a_end:
            raise HTTPException(status_code=400, detail="答案页起止顺序不对")

    q_start, q_end = _derive_page_range(
        question_start_page=_int(question_start_page),
        question_end_page=_int(question_end_page),
        answer_start_page=a_start,
        answer_end_page=a_end,
        total_pages=total,
    )

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


def _job_payload(job) -> dict:
    """统一的进度负载（含题面页范围，前端据此显示「第 N/M 页」）。"""
    q_start, q_end = _derive_page_range(
        question_start_page=job.question_start_page,
        question_end_page=job.question_end_page,
        answer_start_page=job.answer_start_page,
        answer_end_page=job.answer_end_page,
        total_pages=job.total_pages,
    )
    return {
        "id": job.id,
        "status": job.status,
        "total_pages": job.total_pages,
        "question_pages": max(0, q_end - q_start + 1),
        "done_pages": job.done_pages,
        "question_count": job.question_count,
        "aligned_count": job.aligned_count,
        "published_count": job.published_count,
        "failed_pages": json.loads(job.failed_pages or "[]"),
        "error": job.error,
    }


@router.get("/api/practice-import/jobs/latest")
def latest_job(
    bank_id: int = Query(...),
    user: User = Depends(require_learning_user),
    db: Session = Depends(get_db),
):
    """该卷最近一次导入任务（进页面时自动带出进度）。"""
    _require_own_bank(bank_id, user, db)
    job = (
        db.query(PracticeImportJob)
        .filter(PracticeImportJob.bank_id == bank_id)
        .order_by(PracticeImportJob.id.desc())
        .first()
    )
    if job is None:
        return {"job": None}
    return {"job": _job_payload(job)}


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
    return _job_payload(job)


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
            (Question.answer == "") | (Question.answer.is_(None)),
            Question.is_example.is_(False),     # 示例行不是待做题
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
                "image_url": _image_url(q.image_path),
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


class BankDailyReq(BaseModel):
    include_daily_task: bool


@router.patch("/api/practice-import/bank-daily")
def set_bank_daily(
    req: BankDailyReq,
    bank_id: int = Query(...),
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """把该练习册卷加入/移出「每日任务」抽题范围。"""
    bank = _require_own_bank(bank_id, user, db)
    try:
        tags = json.loads(bank.tags or "{}")
    except (ValueError, TypeError):
        tags = {}
    if not isinstance(tags, dict):
        tags = {}
    tags["include_daily_task"] = bool(req.include_daily_task)
    bank.tags = json.dumps(tags, ensure_ascii=False)
    db.commit()
    return {"ok": True, "include_daily_task": tags["include_daily_task"]}


@router.get("/api/practice-import/questions")
def list_practice_questions(
    bank_id: int = Query(...),
    lesson_no: int | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """浏览已导入的题目（家长端核对用）。可按课时过滤。"""
    bank = _require_own_bank(bank_id, user, db)
    q = db.query(Question).filter(Question.bank_id == bank.id)
    if lesson_no is not None:
        q = q.filter(Question.lesson_no == lesson_no)
    total = q.count()
    rows = (
        q.order_by(Question.lesson_no, Question.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "lesson_no": r.lesson_no,
                "lesson_title": r.lesson_title,
                "question": r.question,
                "answer": r.answer,
                "qtype": r.qtype,
                "status": r.status,
                "image_url": _image_url(r.image_path),
                "work_mode": r.work_mode or "",
                "answer_kind": answer_kind_of(r.work_mode or ""),
                "input_ui": input_ui_of(r.work_mode or ""),
                "group_id": r.group_id,
                "seq_in_group": r.seq_in_group,
                "is_example": r.is_example,
            }
            for r in rows
        ],
    }


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


class PageTypeReq(BaseModel):
    page_type: str


_PAGE_TYPES = ("practice", "toc", "answer_key", "cover", "blank")


@router.get("/api/practice-import/pages")
def list_pages(document_id: int, _auth: User = Depends(require_learning_user),
               db: Session = Depends(get_db)):
    """列出某文档已分析的页（供家长排查/修正页类型）。"""
    from ..models import PracticeImportPage

    rows = (db.query(PracticeImportPage)
            .filter_by(document_id=document_id)
            .order_by(PracticeImportPage.page_no).all())
    return {"pages": [{
        "page_no": r.page_no, "page_type": r.page_type,
        "group_count": r.group_count, "status": r.status,
    } for r in rows]}


@router.patch("/api/practice-import/pages/{page_no}")
def patch_page_type(page_no: int, req: PageTypeReq, document_id: int,
                    _auth: User = Depends(require_role("parent", "admin")),
                    db: Session = Depends(get_db)):
    """把某页的类型改掉（如 toc → practice），供之后重新解析该页。"""
    from ..models import PracticeImportPage

    if req.page_type not in _PAGE_TYPES:
        raise HTTPException(400, f"page_type 必须是 {_PAGE_TYPES} 之一")
    row = (db.query(PracticeImportPage)
           .filter_by(document_id=document_id, page_no=page_no).first())
    if row is None:
        raise HTTPException(404, "该页没有分析记录")
    row.page_type = req.page_type
    db.commit()
    return {"page_no": row.page_no, "page_type": row.page_type}
