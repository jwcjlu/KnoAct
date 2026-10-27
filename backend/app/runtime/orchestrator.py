"""路由 UnifiedContext → 选中的 capability。"""
from ..core.context import UnifiedContext
from ..core.stream import StreamBus
from ..capabilities.registry import CapabilityRegistry


async def route_to_capability(ctx: UnifiedContext) -> dict:
    """异步入口：驱动 capability，返回最终 {answer, citations, mode}。"""
    registry = CapabilityRegistry()
    capability = registry.get(ctx.mode)
    stream = StreamBus()
    await capability.run(ctx, stream)
    # 从 stream 最后一个 final 事件取答案
    final_event = None
    for e in reversed(stream.events):
        if e.type == "final":
            final_event = e
            break
    answer = final_event.data.get("answer", "") if final_event else ""
    citations = _extract_citations(answer)
    return {"answer": answer, "citations": citations, "mode": ctx.mode}


def _extract_citations(answer: str) -> list[int]:
    import re
    return sorted(set(int(n) for n in re.findall(r"第\s*(\d+)\s*句", answer)))
