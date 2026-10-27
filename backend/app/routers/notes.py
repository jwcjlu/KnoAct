import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
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
    sentences: list[str] = []

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
        sentences=req.sentences,
    )
    return await route_to_capability(ctx)


@router.post("/api/ask/stream")
async def ask_stream(req: AskReq, db: Session = Depends(get_db)):
    from ..models import User
    child = db.query(User).filter_by(role="child").first()
    user_id = child.id if child else 0
    ctx = UnifiedContext(
        user_id=user_id, lesson_id=req.lesson_id, question=req.question,
        text=req.context, mode=req.mode, model=req.model, sentences=req.sentences,
    )
    return StreamingResponse(_event_stream(ctx), media_type="text/event-stream")


async def _event_stream(ctx: UnifiedContext):
    from ..core.stream import StreamBus
    from ..capabilities.registry import CapabilityRegistry
    from ..runtime.orchestrator import _extract_citations, _filter_citations, _persist

    registry = CapabilityRegistry()
    capability = registry.get(ctx.mode)
    stream = StreamBus()
    queue = stream.subscribe()

    task = asyncio.create_task(capability.run(ctx, stream))
    tool_events = []
    results_by_step = {}
    answer = ""
    citations = []

    try:
        while True:
            event = await queue.get()
            if event.type == "tool_call":
                tool_events.append(event)
                yield _sse(event.type, event.data)
            elif event.type == "tool_result":
                results_by_step[event.data.get("step", 0)] = event.data.get("result", {})
                yield _sse(event.type, event.data)
            elif event.type == "final":
                answer = event.data.get("answer", "")
                citations = _filter_citations(_extract_citations(answer), len(ctx.sentences))
                yield _sse("final", {"answer": answer, "citations": citations, "mode": ctx.mode})
                break
            else:
                yield _sse(event.type, event.data)
    finally:
        try:
            await task
        except Exception:
            pass

    _persist(ctx, capability.name, answer, citations, tool_events, results_by_step)


def _sse(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, 'data': data}, ensure_ascii=False)}\n\n"
