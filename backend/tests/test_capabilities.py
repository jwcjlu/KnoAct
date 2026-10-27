import pytest

from app.core.context import UnifiedContext
from app.core.stream import StreamEvent, StreamBus
from app.core.capability_protocol import CapabilityManifest, TurnCapability


def test_unified_context_defaults():
    ctx = UnifiedContext(user_id=1, lesson_id=2, question="你好")
    assert ctx.user_id == 1
    assert ctx.lesson_id == 2
    assert ctx.question == "你好"
    assert ctx.text == ""
    assert ctx.mode == "chat"
    assert ctx.model == ""


def test_stream_bus_collects_events():
    bus = StreamBus()
    bus.emit(StreamEvent(type="tool_call", data={"tool": "lookup_word"}))
    bus.emit(StreamEvent(type="final", data={"answer": "好"}))
    assert [e.type for e in bus.events] == ["tool_call", "final"]


def test_capability_manifest_fields():
    m = CapabilityManifest(name="chat", description="对话", stages=["thinking"], tools_used=["lookup_word"])
    assert m.name == "chat"
    assert m.stages == ["thinking"]
    assert m.tools_used == ["lookup_word"]


from app.capabilities.chat import ChatCapability, VisualizeCapability, SolveCapability
from app.capabilities.registry import CapabilityRegistry


def test_chat_manifest():
    assert ChatCapability().name == "chat"
    assert "lookup_word" in ChatCapability().manifest.tools_used


def test_visualize_uses_render_mermaid():
    assert "render_mermaid" in VisualizeCapability().manifest.tools_used


def test_solve_system_prompt_is_stepwise():
    assert "分步骤" in SolveCapability().system_prompt


def test_registry_routes_mode():
    reg = CapabilityRegistry()
    assert isinstance(reg.get("chat"), ChatCapability)
    assert isinstance(reg.get("visualize"), VisualizeCapability)
    assert isinstance(reg.get("solve"), SolveCapability)


def test_registry_unknown_mode_falls_back_to_chat():
    reg = CapabilityRegistry()
    assert isinstance(reg.get("nope"), ChatCapability)
