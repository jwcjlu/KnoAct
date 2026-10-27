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
    from ..runtime.orchestrator import extract_citations, filter_citations, persist_turn, extract_render_task_id

    registry = CapabilityRegistry()
    capability = registry.get(ctx.mode)
    stream = StreamBus()
    task = asyncio.create_task(capability.run(ctx, stream))

    tool_events = []
    results_by_step = {}
    answer = ""
    citations = []
    consumed = 0  # 已消费的 stream.events 下标（events 是权威有序列表）

    def _yield_event(event):
        nonlocal answer, citations
        if event.type == "tool_call":
            tool_events.append(event)
            return _sse(event.type, event.data)
        if event.type == "tool_result":
            results_by_step[event.data.get("step", 0)] = event.data.get("result", {})
            return _sse(event.type, event.data)
        if event.type == "final":
            answer = event.data.get("answer", "")
            citations = filter_citations(extract_citations(answer), len(ctx.sentences))
            return _sse("final", {
                "answer": answer,
                "citations": citations,
                "mode": ctx.mode,
                "render_task_id": extract_render_task_id(results_by_step),
            })
        return _sse(event.type, event.data)

    try:
        while True:
            # 先消费已就绪的事件
            if consumed < len(stream.events):
                yield _yield_event(stream.events[consumed])
                consumed += 1
                continue
            if task.done():
                break
            # 没有新事件且任务仍在跑：让出事件循环。TurnEngine 每次 emit 后都
            # await asyncio.to_thread（阻塞的 LLM 调用），会自然让出，这里只是轮询检查点。
            await asyncio.sleep(0)
    finally:
        try:
            await task
        except Exception:
            pass

    # task 结束后兜底：provider 抛异常时 final 未发出，补发 error
    if consumed < len(stream.events):
        for event in stream.events[consumed:]:
            yield _yield_event(event)
    if task.done() and task.exception() is not None and answer == "":
        yield _sse("error", {"error": str(task.exception())})

    persist_turn(ctx, capability.name, answer, citations, tool_events, results_by_step)


def _sse(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, 'data': data}, ensure_ascii=False)}\n\n"
