import json
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import require_learning_user
from ..core.deps import get_current_user, require_role
from ..database import get_db
from ..models import Question, Lesson, Text, User
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
    qs = q.order_by(Question.subject, Question.lesson_id, Question.id).all()
    grouped = {}
    lesson_titles = {}
    for item in qs:
        grouped.setdefault((item.subject, item.lesson_id), []).append({
            "id": item.id, "qtype": item.qtype, "question": item.question,
            "answer": item.answer, "extra": item.extra, "task_type": item.task_type,
        })
        if item.lesson_id not in lesson_titles:
            lesson = db.get(Lesson, item.lesson_id)
            lesson_titles[item.lesson_id] = lesson.title if lesson else f"课程{item.lesson_id}"
    return {"groups": [
        {"subject": subj, "lesson_id": lid, "lesson_title": lesson_titles.get(lid, ""), "questions": items}
        for (subj, lid), items in grouped.items()
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
