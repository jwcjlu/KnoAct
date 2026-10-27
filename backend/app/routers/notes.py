from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Note
from ..core.context import UnifiedContext
from ..runtime.orchestrator import route_to_capability

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
    model: str = ""       # 覆盖默认模型（选模型）
    mode: str = "chat"    # chat=对话 | visualize=可视化 | solve=解题

@router.post("/api/notes")
def add_note(req: NoteReq, db: Session = Depends(get_db)):
    note = Note(**req.model_dump())
    db.add(note); db.commit(); db.refresh(note)
    return {"id": note.id, "content": note.content}

@router.get("/api/notes")
def list_notes(lesson_id: int, db: Session = Depends(get_db)):
    return db.query(Note).filter_by(lesson_id=lesson_id).order_by(Note.created_at.desc()).all()

@router.post("/api/ask")
async def ask_ai(req: AskReq, db: Session = Depends(get_db)):
    # TODO: wire real auth/user context (no session/auth yet — resolve first child as placeholder)
    from ..models import User
    child = db.query(User).filter_by(role="child").first()
    user_id = child.id if child else 0
    ctx = UnifiedContext(
        user_id=user_id, lesson_id=req.lesson_id, question=req.question,
        text=req.context, mode=req.mode, model=req.model,
    )
    return await route_to_capability(ctx)
