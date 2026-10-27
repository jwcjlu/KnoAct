"""学习助手 capability：chat / visualize / solve 三模式。"""
from ..core.capability_protocol import CapabilityManifest, TurnCapability
from ..core.context import UnifiedContext
from ..core.stream import StreamBus, StreamEvent
from ..runtime.turn_engine import TurnEngine
from ..tools.registry import ToolRegistry
from ..tools.builtin import lookup_word, search_text, render_mermaid


ALL_TOOLS = {"lookup_word": lookup_word, "search_text": search_text, "render_mermaid": render_mermaid}


class AgenticChatCapability(TurnCapability):
    """共享基类：封装「调 TurnEngine 多步循环」的公共逻辑。"""

    system_prompt: str = "你是小学生的学习助手，讲解要通俗、有耐心。"
    tools: list[str] = ["lookup_word", "search_text", "render_mermaid"]

    @property
    def _registry(self) -> ToolRegistry:
        reg = ToolRegistry()
        for name in self.tools:
            if name in ALL_TOOLS:
                reg.register(ALL_TOOLS[name])
        return reg

    async def run(self, ctx: UnifiedContext, stream: StreamBus) -> None:
        stream.emit(StreamEvent(type="stage", data={"stage": "thinking"}))
        engine = TurnEngine(provider=_get_provider(ctx), registry=self._registry, system_prompt=self.system_prompt)
        await engine.run(ctx, stream)


def _get_provider(ctx: UnifiedContext):
    from ..database import SessionLocal
    from ..services.ai import get_provider
    db = SessionLocal()
    try:
        provider = get_provider(db)
        if ctx.model:
            provider.model = ctx.model
        return provider
    finally:
        db.close()


class ChatCapability(AgenticChatCapability):
    manifest = CapabilityManifest(
        name="chat",
        description="普通问答",
        stages=["thinking"],
        tools_used=["lookup_word", "search_text", "render_mermaid"],
    )


class VisualizeCapability(AgenticChatCapability):
    manifest = CapabilityManifest(
        name="visualize",
        description="把知识画成图",
        stages=["thinking"],
        tools_used=["render_mermaid", "search_text"],
    )
    system_prompt = (
        "你是小学生的学习助手，擅长把知识画成图。"
        "当孩子提问适合用图表达时，调用 render_mermaid 工具画图，图下方再用一两句小学生能懂的话解释。"
        "如果不适合画图，就直接用通俗的话解答。"
    )
    tools = ["render_mermaid", "search_text"]


class SolveCapability(AgenticChatCapability):
    manifest = CapabilityManifest(
        name="solve",
        description="分步解题",
        stages=["thinking"],
        tools_used=["lookup_word", "search_text"],
    )
    system_prompt = (
        "你是小学生的解题助手。请分步骤讲解解题思路（读题 → 分析 → 列式 → 作答），"
        "每一步用一句小学生能懂的话说明，最后给出答案。"
    )
    tools = ["lookup_word", "search_text"]
