"""阅读理解材料：建材料、带子题、按卷列出、取详情。"""
import json
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.deps import require_role
from ..core.passage_markup import FILL_BLANK_QTYPES, blanks_aligned
from ..core.question_types import CATEGORY_OF_QTYPE
from ..database import get_db
from ..models import Question, QuestionBank, ReadingPassage, User

router = APIRouter(prefix="/api/passages", tags=["passages"])


class PassageQuestionIn(BaseModel):
    qtype: str = "short_answer"
    question: str
    answer: str = ""
    options: list[dict] = []
    answer_json: dict = {}
    analysis: str = ""
    difficulty: str = "medium"
    tags: dict = {}


class PassageCreateReq(BaseModel):
    title: str
    content: str
    subject: str = ""
    grade: int | None = None
    bank_id: int | None = None
    questions: list[PassageQuestionIn] = []


def _dump_question(q: Question) -> dict:
    try:
        options = json.loads(q.options or "[]")
    except (ValueError, TypeError):
        options = []
    try:
        answer_json = json.loads(q.answer_json or "{}")
    except (ValueError, TypeError):
        answer_json = {}
    return {
        "id": q.id,
        "qtype": q.qtype,
        "qtype_category": q.qtype_category,
        "question": q.question,
        "answer": q.answer,
        "options": options,
        "answer_json": answer_json,
        "analysis": q.analysis or "",
        "difficulty": q.difficulty,
        "status": q.status,
        "bank_id": q.bank_id,
    }


@router.post("")
def create_passage(req: PassageCreateReq, user: User = Depends(require_role("parent", "admin")),
                   db: Session = Depends(get_db)):
    title = req.title.strip()
    content = req.content.strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="标题和正文不能为空")
    fill_n = sum(1 for q in req.questions if q.qtype in FILL_BLANK_QTYPES)
    if not blanks_aligned(content, fill_n):
        raise HTTPException(status_code=400, detail="材料挖空个数须与填空子题个数一致")

    bank = None
    if req.bank_id:
        bank = db.get(QuestionBank, req.bank_id)
        if not bank or (user.role != "admin" and bank.user_id != user.id):
            raise HTTPException(status_code=404, detail="卷子不存在")

    subject = (req.subject or "").strip() or ((bank.subject or "").strip() if bank else "")
    grade = req.grade if req.grade is not None else (bank.grade if bank else None)

    psg = ReadingPassage(
        user_id=user.id,
        bank_id=req.bank_id,
        subject=subject,
        title=title,
        content=content,
        grade=grade,
        status="pending",
    )
    db.add(psg)
    db.flush()

    today = date_type.today()
    question_ids: list[int] = []
    for item in req.questions:
        qtext = item.question.strip()
        if not qtext:
            continue
        category = CATEGORY_OF_QTYPE.get(item.qtype, "subjective")
        q = Question(
            bank_id=req.bank_id,
            passage_id=psg.id,
            qtype=item.qtype,
            qtype_category=category,
            question=qtext,
            answer=item.answer.strip() if item.answer else "",
            answer_json=json.dumps(item.answer_json or {}, ensure_ascii=False),
            options=json.dumps(item.options or [], ensure_ascii=False),
            analysis=item.analysis.strip() if item.analysis else "",
            difficulty=item.difficulty or "medium",
            tags=json.dumps(item.tags or {}, ensure_ascii=False),
            subject=subject,
            date=today,
            status="pending",
        )
        db.add(q)
        db.flush()
        question_ids.append(q.id)

    db.commit()
    db.refresh(psg)
    return {"id": psg.id, "question_ids": question_ids}


@router.get("")
def list_passages(bank_id: int | None = None,
                  user: User = Depends(require_role("parent", "admin")),
                  db: Session = Depends(get_db)):
    q = db.query(ReadingPassage).filter_by(user_id=user.id)
    if bank_id is not None:
        q = q.filter_by(bank_id=bank_id)
    rows = q.order_by(ReadingPassage.id.desc()).all()
    counts = dict(
        db.query(Question.passage_id, func.count(Question.id))
        .filter(Question.passage_id.isnot(None))
        .group_by(Question.passage_id)
        .all()
    )
    return [{
        "id": p.id,
        "title": p.title,
        "content": p.content,
        "subject": p.subject,
        "grade": p.grade,
        "bank_id": p.bank_id,
        "status": p.status,
        "question_count": int(counts.get(p.id, 0)),
    } for p in rows]


@router.get("/{passage_id}")
def get_passage(passage_id: int, user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    psg = db.get(ReadingPassage, passage_id)
    if not psg or (user.role != "admin" and psg.user_id != user.id):
        raise HTTPException(status_code=404, detail="材料不存在")
    qs = db.query(Question).filter_by(passage_id=psg.id).order_by(Question.id).all()
    return {
        "id": psg.id,
        "title": psg.title,
        "content": psg.content,
        "subject": psg.subject,
        "grade": psg.grade,
        "bank_id": psg.bank_id,
        "status": psg.status,
        "questions": [_dump_question(q) for q in qs],
    }
