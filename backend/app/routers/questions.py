import json
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import require_learning_user
from ..core.deps import get_current_user, require_role
from ..database import get_db
from ..models import Question, Lesson, QuestionBank, Text, User
from ..services.question_gen import generate_reading_questions

router = APIRouter(prefix="/api/questions", tags=["questions"])


class GenerateReq(BaseModel):
    lesson_id: int
    n: int = 3


class AddReq(BaseModel):
    lesson_id: int | None = None
    bank_id: int | None = None
    qtype: str = "short_answer"
    question: str
    answer: str = ""
    options: list[dict] = []
    answer_json: dict = {}
    analysis: str = ""
    difficulty: str = "medium"
    tags: dict = {}


@router.get("")
def list_questions(lesson_id: int, _auth: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    qs = db.query(Question).filter_by(lesson_id=lesson_id).order_by(Question.id).all()
    return [{"id": q.id, "qtype": q.qtype, "question": q.question, "answer": q.answer} for q in qs]


@router.post("/generate")
def regenerate_questions(req: GenerateReq, _auth: User = Depends(require_role("parent", "admin")),
                         db: Session = Depends(get_db)):
    t = db.query(Text).filter_by(lesson_id=req.lesson_id).first()
    if not t or not t.content.strip():
        raise HTTPException(status_code=404, detail="该课暂无课文，无法出题")
    n = max(1, min(req.n, 10))
    db.query(Question).filter_by(lesson_id=req.lesson_id, qtype="reading").delete(synchronize_session=False)
    qs = generate_reading_questions(db, t.content, n=n)
    for q in qs:
        db.add(Question(lesson_id=req.lesson_id, qtype="reading", question=q["question"], answer=q["answer"]))
    db.commit()
    return {"count": len(qs)}


@router.post("")
def add_question(req: AddReq, _auth: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="题目内容不能为空")
    from ..core.question_types import CATEGORY_OF_QTYPE
    category = CATEGORY_OF_QTYPE.get(req.qtype, "subjective")
    subject = ""
    if req.bank_id:
        bank = db.get(QuestionBank, req.bank_id)
        if bank:
            subject = (bank.subject or "").strip()
    q = Question(
        lesson_id=req.lesson_id,
        bank_id=req.bank_id,
        qtype=req.qtype,
        qtype_category=category,
        question=question,
        answer=req.answer.strip(),
        answer_json=json.dumps(req.answer_json, ensure_ascii=False),
        options=json.dumps(req.options, ensure_ascii=False),
        analysis=req.analysis.strip(),
        difficulty=req.difficulty,
        tags=json.dumps(req.tags, ensure_ascii=False),
        subject=subject,
        date=date_type.today(),
        status="pending",  # 人工录入默认进审核队列
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return {"id": q.id}


@router.delete("/{question_id}")
def delete_question(question_id: int, _auth: User = Depends(require_role("parent", "admin")),
                    db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    db.delete(q)
    db.commit()
    return {"ok": True}


@router.get("/review")
def review_questions(d: date_type, subject: str = "",
                     _auth: User = Depends(require_role("parent", "admin")),
                     db: Session = Depends(get_db)):
    """待审核题目，按学科→课程分组。"""
    q = db.query(Question).filter(Question.status == "pending")
    if d:
        q = q.filter(Question.date == d)
    if subject:
        q = q.filter(Question.subject == subject)
    qs = q.order_by(Question.subject, Question.lesson_id, Question.bank_id, Question.id).all()
    grouped: dict[tuple, list] = {}
    group_meta: dict[tuple, dict] = {}

    def _group_key(item: Question) -> tuple:
        if item.lesson_id:
            return ("lesson", item.lesson_id)
        if item.bank_id:
            return ("bank", item.bank_id)
        return ("solo", item.id)

    for item in qs:
        gkey = _group_key(item)
        grouped.setdefault(gkey, []).append({
            "id": item.id, "qtype": item.qtype, "qtype_category": item.qtype_category,
            "question": item.question, "answer": item.answer, "extra": item.extra,
            "task_type": item.task_type, "analysis": item.analysis or "",
            "options": json.loads(item.options or "[]"),
            "answer_json": json.loads(item.answer_json or "{}"),
            "bank_id": item.bank_id,
        })
        if gkey not in group_meta:
            subj = (item.subject or "").strip() or "未分类"
            if gkey[0] == "lesson":
                lesson = db.get(Lesson, gkey[1])
                title = lesson.title if lesson else f"课程{gkey[1]}"
                group_meta[gkey] = {"subject": subj, "lesson_id": gkey[1], "bank_id": None, "lesson_title": title}
            elif gkey[0] == "bank":
                bank = db.get(QuestionBank, gkey[1])
                title = bank.title if bank else f"题库卷{gkey[1]}"
                if bank and (bank.subject or "").strip():
                    subj = bank.subject.strip()
                group_meta[gkey] = {"subject": subj, "lesson_id": None, "bank_id": gkey[1], "lesson_title": title}
            else:
                group_meta[gkey] = {"subject": subj, "lesson_id": None, "bank_id": None, "lesson_title": "独立录入"}

    return {"groups": [
        {**group_meta[gkey], "questions": items}
        for gkey, items in grouped.items()
    ]}


@router.post("/{question_id}/approve")
def approve_question(question_id: int, _auth: User = Depends(require_role("parent", "admin")),
                     db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    q.status = "published"
    db.commit()
    return {"ok": True}


@router.post("/{question_id}/reject")
def reject_question(question_id: int, _auth: User = Depends(require_role("parent", "admin")),
                    db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    q.status = "rejected"
    db.commit()
    return {"ok": True}


@router.post("/approve-by-lesson")
def approve_by_lesson(lesson_id: int, d: date_type,
                      _auth: User = Depends(require_role("parent", "admin")),
                      db: Session = Depends(get_db)):
    db.query(Question).filter_by(lesson_id=lesson_id, date=d, status="pending").update(
        {"status": "published"}, synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.post("/approve-by-subject")
def approve_by_subject(subject: str, d: date_type,
                       _auth: User = Depends(require_role("parent", "admin")),
                       db: Session = Depends(get_db)):
    db.query(Question).filter_by(subject=subject, date=d, status="pending").update(
        {"status": "published"}, synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.post("/approve-by-bank")
def approve_by_bank(bank_id: int, d: date_type,
                    _auth: User = Depends(require_role("parent", "admin")),
                    db: Session = Depends(get_db)):
    db.query(Question).filter_by(bank_id=bank_id, date=d, status="pending").update(
        {"status": "published"}, synchronize_session=False)
    db.commit()
    return {"ok": True}
