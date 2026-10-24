from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Note
from ..services.ai import get_provider

router = APIRouter(tags=["notes"])

class NoteReq(BaseModel):
    lesson_id: int
    author_role: str
    content: str
    anchor_text: str = ""
    page_number: int | None = None

class AskReq(BaseModel):
    lesson_id: int
    question: str
    context: str = ""

@router.post("/api/notes")
def add_note(req: NoteReq, db: Session = Depends(get_db)):
    note = Note(**req.model_dump())
    db.add(note); db.commit(); db.refresh(note)
    return {"id": note.id, "content": note.content}

@router.get("/api/notes")
def list_notes(lesson_id: int, db: Session = Depends(get_db)):
    return db.query(Note).filter_by(lesson_id=lesson_id).order_by(Note.created_at.desc()).all()

@router.post("/api/ask")
def ask_ai(req: AskReq, db: Session = Depends(get_db)):
    provider = get_provider(db)
    prompt = f"教材上下文：{req.context}\n孩子提问：{req.question}\n请用小学生能懂的话解答。"
    answer = provider.generate(prompt=prompt, system="你是小学生的学习助手，讲解要通俗、有耐心。")
    return {"answer": answer}
