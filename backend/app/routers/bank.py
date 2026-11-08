"""独立题库/卷：建卷、列卷、拉题、做题判分。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import require_learning_user
from ..core.deps import get_current_user, require_role
from ..database import get_db
from ..models import Question, QuestionBank, User
from ..services.grade_question import grade_question, grade_subjective_with_ai

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


@router.get("/{bank_id}/questions")
def list_bank_questions(bank_id: int, _auth: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    qs = db.query(Question).filter_by(bank_id=bank_id, status="published").order_by(Question.id).all()
    return [{
        "id": q.id, "qtype": q.qtype, "qtype_category": q.qtype_category,
        "question": q.question, "options": json.loads(q.options or "[]"),
        "answer": q.answer, "analysis": q.analysis, "difficulty": q.difficulty,
        "tags": json.loads(q.tags or "{}"),
    } for q in qs]


@router.post("/submit")
def submit_bank(req: BankSubmitReq, user: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    qs = db.query(Question).filter(Question.id.in_([a.get("question_id") for a in req.answers])).all()
    by_id = {q.id: q for q in qs}
    results = []
    for a in req.answers:
        q = by_id.get(a.get("question_id"))
        if q is None:
            results.append({"question_id": a.get("question_id"), "is_correct": False})
            continue
        answer_json = json.loads(q.answer_json or "{}")
        student = {k: a.get(k) for k in ("selected_index", "blanks", "pairs", "text") if a.get(k) is not None}
        if q.qtype_category == "subjective":
            r = grade_subjective_with_ai(db, answer_json, student)
        else:
            r = grade_question(q.qtype_category, answer_json, student)
        results.append({"question_id": q.id, "is_correct": r["is_correct"],
                        "correct_answer_text": r["correct_answer_text"], "detail": r["detail"]})
    score = sum(1 for r in results if r["is_correct"] is True)
    return {"answers": results, "score": score, "total": len(results)}
