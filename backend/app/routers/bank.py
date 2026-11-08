"""独立题库/卷：建卷、列卷、拉题、做题判分。"""
import json
import os
from datetime import date as date_type

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.access import require_learning_user
from ..core.deps import get_current_user, require_role
from ..core.question_types import CATEGORY_OF_QTYPE
from ..database import get_db
from ..models import Mistake, Question, QuestionBank, User
from ..services.ai import ocr_image
from ..services.bucket_guard import resolve_bucket_id
from ..services.grade_question import grade_question, grade_subjective_with_ai
from ..services.ocr_import import structure_questions_from_text

_PHOTO_MAX_BYTES = 8 * 1024 * 1024
_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}

router = APIRouter(prefix="/api/banks", tags=["bank"])


class BankCreateReq(BaseModel):
    title: str
    subject: str = ""
    grade: int | None = None
    tags: dict = {}
    source: str = "manual"


class BankSubmitReq(BaseModel):
    bank_id: int | None = None
    answers: list[dict]   # [{question_id, selected_index|blanks|pairs|text}]


@router.post("")
def create_bank(req: BankCreateReq, user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    bank = QuestionBank(user_id=user.id, title=req.title.strip(), subject=req.subject,
                        grade=req.grade, tags=json.dumps(req.tags, ensure_ascii=False),
                        source=req.source)
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return {"id": bank.id, "title": bank.title}


@router.get("")
def list_banks(user: User = Depends(require_role("parent", "admin")),
               db: Session = Depends(get_db)):
    banks = db.query(QuestionBank).filter_by(user_id=user.id).order_by(QuestionBank.id.desc()).all()
    return [{"id": b.id, "title": b.title, "subject": b.subject, "grade": b.grade,
             "source": b.source, "status": b.status} for b in banks]


def _parent_id_for_practice(user: User) -> int | None:
    if user.role == "child":
        return user.parent_id
    if user.role in ("parent", "admin"):
        return user.id
    return None


@router.get("/practice")
def list_practice_banks(user: User = Depends(require_learning_user),
                        db: Session = Depends(get_db)):
    """孩子端练卷列表：绑定家长名下、含已发布题目的卷子。"""
    pid = _parent_id_for_practice(user)
    if pid is None:
        return []
    counts = dict(
        db.query(Question.bank_id, func.count(Question.id))
        .filter(Question.status == "published", Question.bank_id.isnot(None))
        .group_by(Question.bank_id)
        .all()
    )
    banks = (
        db.query(QuestionBank)
        .filter_by(user_id=pid, status="active")
        .order_by(QuestionBank.id.desc())
        .all()
    )
    return [
        {
            "id": b.id, "title": b.title, "subject": b.subject, "grade": b.grade,
            "question_count": int(counts.get(b.id, 0)),
        }
        for b in banks
        if counts.get(b.id, 0) > 0
    ]


def _format_student_answer(answer_row: dict, q: Question) -> str:
    if answer_row.get("text") is not None:
        return str(answer_row.get("text", ""))
    if answer_row.get("blanks") is not None:
        return "；".join(str(x) for x in (answer_row.get("blanks") or []))
    if answer_row.get("pairs") is not None:
        return json.dumps(answer_row.get("pairs"), ensure_ascii=False)
    sel = answer_row.get("selected_index")
    if sel is not None:
        opts = json.loads(q.options or "[]")
        if isinstance(sel, list):
            labels = []
            for i in sel:
                if isinstance(i, int) and 0 <= i < len(opts):
                    labels.append(str(opts[i].get("label", i)))
            return "、".join(labels) if labels else json.dumps(sel, ensure_ascii=False)
        if isinstance(sel, int) and 0 <= sel < len(opts):
            return str(opts[sel].get("label", sel))
        return str(sel)
    return ""


@router.get("/{bank_id}/questions")
def list_bank_questions(
    bank_id: int,
    ids: str = "",
    _auth: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Question).filter_by(bank_id=bank_id, status="published")
    if ids.strip():
        qids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        if qids:
            q = q.filter(Question.id.in_(qids))
    qs = q.order_by(Question.id).all()
    return [{
        "id": q.id, "qtype": q.qtype, "qtype_category": q.qtype_category,
        "question": q.question, "options": json.loads(q.options or "[]"),
        "answer": q.answer, "analysis": q.analysis, "difficulty": q.difficulty,
        "tags": json.loads(q.tags or "{}"),
    } for q in qs]


@router.post("/submit")
def submit_bank(req: BankSubmitReq, user: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    qids = [a.get("question_id") for a in req.answers]
    # 只判已发布的题，且给定 bank_id 时限定在该卷内；杜绝越权给草稿/他卷题目判分泄答案
    q = db.query(Question).filter(Question.id.in_(qids), Question.status == "published")
    if req.bank_id is not None:
        q = q.filter(Question.bank_id == req.bank_id)
    qs = q.all()
    by_id = {x.id: x for x in qs}
    results = []
    for a in req.answers:
        qid = a.get("question_id")
        qq = by_id.get(qid)
        if qq is None:
            results.append({"question_id": qid, "is_correct": False})
            continue
        answer_json = json.loads(qq.answer_json or "{}")
        student = {k: a.get(k) for k in ("selected_index", "blanks", "pairs", "text") if a.get(k) is not None}
        if qq.qtype_category == "subjective":
            r = grade_subjective_with_ai(db, answer_json, student)
        else:
            r = grade_question(qq.qtype_category, answer_json, student)
        results.append({"question_id": qq.id, "is_correct": r["is_correct"],
                        "correct_answer_text": r["correct_answer_text"], "detail": r["detail"]})
        if r["is_correct"] is False:
            bid = resolve_bucket_id(db, user.id, None)
            db.add(Mistake(
                user_id=user.id,
                source_type="bank",
                question=qq.question,
                your_answer=_format_student_answer(a, qq),
                correct_answer=r.get("correct_answer_text") or qq.answer,
                bucket_id=bid,
            ))
    score = sum(1 for r in results if r["is_correct"] is True)
    db.commit()
    return {"answers": results, "score": score, "total": len(results)}


@router.post("/{bank_id}/photo-import")
async def photo_import_bank(
    bank_id: int,
    file: UploadFile = File(...),
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """卷子拍照 → OCR → LLM 结构化 → 待审核题目批量入库。"""
    bank = db.get(QuestionBank, bank_id)
    if not bank or (user.role != "admin" and bank.user_id != user.id):
        raise HTTPException(status_code=404, detail="卷子不存在")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _PHOTO_EXT:
        raise HTTPException(status_code=400, detail="不支持的图片格式")
    data = await file.read()
    if len(data) > _PHOTO_MAX_BYTES:
        raise HTTPException(status_code=400, detail="图片过大")
    try:
        ocr_text = ocr_image(db, data, instruction="识别试卷图片中的全部题目文字，保留题号与选项。")
    except Exception:
        ocr_text = ""
    drafts = structure_questions_from_text(db, ocr_text or "")
    if not drafts:
        return {"count": 0, "ids": [], "message": "未能识别题目，请换更清晰照片或改用手工录入"}
    ids = []
    today = date_type.today()
    subj = (bank.subject or "").strip()
    for d in drafts:
        category = CATEGORY_OF_QTYPE.get(d.qtype, "subjective")
        q = Question(
            bank_id=bank_id,
            qtype=d.qtype or "short_answer",
            qtype_category=category,
            question=d.question,
            answer=d.answer,
            answer_json=json.dumps(d.answer_json or {}, ensure_ascii=False),
            options=json.dumps(d.options or [], ensure_ascii=False),
            analysis=d.analysis or "",
            difficulty=d.difficulty or "medium",
            tags=json.dumps({**(d.tags or {}), "source": "photo"}, ensure_ascii=False),
            subject=subj,
            date=today,
            status="pending",
        )
        db.add(q)
        db.flush()
        ids.append(q.id)
    if bank.source == "manual" and ids:
        bank.source = "photo"
    db.commit()
    return {"count": len(ids), "ids": ids}
