"""路由 UnifiedContext → 选中的 capability。"""
import asyncio
import json
import re
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
    answer = append_mermaid_from_tool_results(answer, results_by_step)
    if ctx.mode == "visualize" and "```mermaid" not in answer:
        answer = await ensure_mermaid_diagram(ctx, answer)
    if "```mermaid" in answer:
        from ..services.mermaid_sanitize import normalize_mermaid_in_answer

        answer = normalize_mermaid_in_answer(answer, question=ctx.question)
    citations = filter_citations(extract_citations(answer), len(ctx.sentences))

    persist_turn(ctx, capability.name, answer, citations, tool_events, results_by_step)
    return {
        "answer": answer,
        "citations": citations,
        "mode": ctx.mode,
        "render_task_id": extract_render_task_id(results_by_step),
    }


def extract_citations(answer: str) -> list[int]:
    import re
    return sorted(set(int(n) for n in re.findall(r"第\s*(\d+)\s*句", answer)))


def _strip_mermaid_fences(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:mermaid)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


async def ensure_mermaid_diagram(ctx: UnifiedContext, answer: str) -> str:
    """visualize 仍无图时：单次 LLM 生成 mermaid 并校验后追加到回答。"""
    from ..database import SessionLocal
    from ..services.ai import get_provider
    from ..tools.builtin import render_mermaid

    db = SessionLocal()
    try:
        provider = get_provider(db, child_id=ctx.user_id or None)
        if ctx.model:
            provider.model = ctx.model
        prompt = (
            f"教材上下文：{(ctx.text or '')[:2500]}\n"
            f"孩子的问题：{ctx.question}\n"
            "请用 mermaid 的 graph TD 画思维导图，节点格式必须是 id[\"中文标签\"]，"
            "例如：graph TD\\n  root[\"小数\"]\\n  a[\"意义\"]\\n  root --> a\n"
            "只输出 mermaid 源码，不要 markdown 围栏，不要 mindmap 语法，不要解释。"
        )
        raw = await asyncio.to_thread(
            provider.generate,
            prompt,
            "你是 mermaid 专家，只输出 graph TD 且中文标签必须写在双引号里。",
            False,
        )
        code = _strip_mermaid_fences(raw)
        result = render_mermaid.run({"code": code}, ctx)
        if result.get("ok") and result.get("code"):
            return answer.rstrip() + f"\n\n```mermaid\n{result['code']}\n```"
    except Exception:
        pass
    finally:
        db.close()
    return answer


def append_mermaid_from_tool_results(answer: str, results_by_step: dict[int, dict]) -> str:
    """visualize 模式：模型调了 render_mermaid 但 final 未带代码块时，自动补上。"""
    if not answer or "```mermaid" in answer:
        return answer
    code = ""
    for result in results_by_step.values():
        if isinstance(result, dict) and result.get("ok") and result.get("code"):
            code = str(result["code"]).strip()
    if not code:
        return answer
    return answer.rstrip() + f"\n\n```mermaid\n{code}\n```"


def extract_render_task_id(results_by_step: dict[int, dict]) -> str:
    """从 tool_result 里找 render_manim 返回的 task_id。"""
    for result in results_by_step.values():
        if isinstance(result, dict) and result.get("task_id"):
            return result["task_id"]
    return ""


def filter_citations(citations: list[int], max_n: int) -> list[int]:
    """剔除越界句号。max_n<=0（未传 sentences）时不过滤。"""
    if max_n <= 0:
        return citations
    return [n for n in citations if 1 <= n <= max_n]


def persist_turn(ctx, capability_name, answer, citations, tool_events, results_by_step):
    """落库 Turn + ToolCall。失败不阻断响应（对话是主链路，DB 是副产物）。"""
    import logging
    from ..database import SessionLocal
    from ..models import Turn, ToolCall, User, Lesson

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        # user_id / lesson_id 是外键：0 或不存在的 id 不能落库
        if not ctx.user_id or db.get(User, ctx.user_id) is None:
            logger.warning("persist turn skipped: user %s not found", ctx.user_id)
            return
        lesson_id = ctx.lesson_id if ctx.lesson_id and db.get(Lesson, ctx.lesson_id) else None
        status = "done" if answer else "error"
        turn = Turn(
            user_id=ctx.user_id, lesson_id=lesson_id, capability=capability_name,
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
