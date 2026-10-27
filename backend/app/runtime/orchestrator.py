"""路由 UnifiedContext → 选中的 capability。"""
import json
from datetime import datetime

from ..core.context import UnifiedContext
from ..core.stream import StreamBus
from ..capabilities.registry import CapabilityRegistry


async def route_to_capability(ctx: UnifiedContext) -> dict:
    """异步入口：驱动 capability，返回最终 {answer, citations, mode}，并落库。"""
    registry = CapabilityRegistry()
    capability = registry.get(ctx.mode)
    stream = StreamBus()
    await capability.run(ctx, stream)

    final_event = None
    tool_events = []
    results_by_step: dict[int, dict] = {}
    for e in stream.events:
        if e.type == "final":
            final_event = e
        elif e.type == "tool_call":
            tool_events.append(e)
        elif e.type == "tool_result":
            results_by_step[e.data.get("step", 0)] = e.data.get("result", {})

    answer = final_event.data.get("answer", "") if final_event else ""
    citations = _filter_citations(_extract_citations(answer), len(ctx.sentences))

    _persist(ctx, capability.name, answer, citations, tool_events, results_by_step)
    return {"answer": answer, "citations": citations, "mode": ctx.mode}


def _extract_citations(answer: str) -> list[int]:
    import re
    return sorted(set(int(n) for n in re.findall(r"第\s*(\d+)\s*句", answer)))


def _filter_citations(citations: list[int], max_n: int) -> list[int]:
    """剔除越界句号。max_n<=0（未传 sentences）时不过滤。"""
    if max_n <= 0:
        return citations
    return [n for n in citations if 1 <= n <= max_n]


def _persist(ctx, capability_name, answer, citations, tool_events, results_by_step):
    """落库 Turn + ToolCall。失败不阻断响应（对话是主链路，DB 是副产物）。"""
    import logging
    from ..database import SessionLocal
    from ..models import Turn, ToolCall

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        status = "done" if answer else "error"
        turn = Turn(
            user_id=ctx.user_id, lesson_id=ctx.lesson_id, capability=capability_name,
            mode=ctx.mode, question=ctx.question, context=ctx.text,
            status=status, final_answer=answer,
            citations=json.dumps(citations, ensure_ascii=False),
            finished_at=datetime.utcnow(),
        )
        db.add(turn); db.commit(); db.refresh(turn)
        for e in tool_events:
            step = e.data.get("step", 0)
            result = results_by_step.get(step, {})
            db.add(ToolCall(
                turn_id=turn.id, step=step,
                tool_name=e.data.get("tool", ""),
                args=json.dumps(e.data.get("args", {}), ensure_ascii=False),
                result=json.dumps(result, ensure_ascii=False),
            ))
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("persist turn failed", exc_info=True)
    finally:
        db.close()
