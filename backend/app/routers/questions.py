from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Question, Text
from ..services.question_gen import generate_reading_questions

router = APIRouter(prefix="/api/questions", tags=["questions"])


class GenerateReq(BaseModel):
    lesson_id: int
    n: int = 3


class AddReq(BaseModel):
    lesson_id: int
    question: str
    answer: str = ""


@router.get("")
def list_questions(lesson_id: int, db: Session = Depends(get_db)):
    qs = db.query(Question).filter_by(lesson_id=lesson_id).order_by(Question.id).all()
    return [{"id": q.id, "qtype": q.qtype, "question": q.question, "answer": q.answer} for q in qs]


@router.post("/generate")
def regenerate_questions(req: GenerateReq, db: Session = Depends(get_db)):
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
def add_question(req: AddReq, db: Session = Depends(get_db)):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="题目内容不能为空")
    q = Question(lesson_id=req.lesson_id, qtype="reading", question=question, answer=req.answer.strip())
    db.add(q)
    db.commit()
    db.refresh(q)
    return {"id": q.id}


@router.delete("/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    db.delete(q)
    db.commit()
    return {"ok": True}


@router.get("/review")
def review_questions(d: date_type, subject: str = "", db: Session = Depends(get_db)):
    """待审核题目，按学科→课程分组。"""
    q = db.query(Question).filter(Question.status == "pending")
    if d:
        q = q.filter(Question.date == d)
    if subject:
        q = q.filter(Question.subject == subject)
    qs = q.order_by(Question.subject, Question.lesson_id, Question.id).all()
    grouped = {}
    for item in qs:
        grouped.setdefault((item.subject, item.lesson_id), []).append({
            "id": item.id, "qtype": item.qtype, "question": item.question,
            "answer": item.answer, "extra": item.extra, "task_type": item.task_type,
        })
    return {"groups": [
        {"subject": subj, "lesson_id": lid, "questions": items}
        for (subj, lid), items in grouped.items()
    ]}


@router.post("/{question_id}/approve")
def approve_question(question_id: int, db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    q.status = "published"
    db.commit()
    return {"ok": True}


@router.post("/{question_id}/reject")
def reject_question(question_id: int, db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    q.status = "rejected"
    db.commit()
    return {"ok": True}


@router.post("/approve-by-lesson")
def approve_by_lesson(lesson_id: int, d: date_type, db: Session = Depends(get_db)):
    db.query(Question).filter_by(lesson_id=lesson_id, date=d, status="pending").update(
        {"status": "published"}, synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.post("/approve-by-subject")
def approve_by_subject(subject: str, d: date_type, db: Session = Depends(get_db)):
    db.query(Question).filter_by(subject=subject, date=d, status="pending").update(
        {"status": "published"}, synchronize_session=False)
    db.commit()
    return {"ok": True}
