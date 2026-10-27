import pytest

from app.core.context import UnifiedContext
from app.core.tool_protocol import BaseTool, ToolParameter
from app.tools.registry import ToolRegistry, ToolNotFoundError
from app.tools.builtin import lookup_word, search_text, render_mermaid


def test_registry_register_and_get():
    class Dummy(BaseTool):
        name = "dummy"
        description = "d"
        parameters = []
        def run(self, args, ctx):
            return {"ok": True}

    reg = ToolRegistry()
    reg.register(Dummy())
    assert reg.get("dummy").name == "dummy"


def test_registry_get_unknown_raises():
    reg = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        reg.get("nope")


def test_registry_list_schemas():
    reg = ToolRegistry()
    reg.register(lookup_word)
    reg.register(search_text)
    schemas = reg.list_schemas()
    names = [s["name"] for s in schemas]
    assert "lookup_word" in names
    assert "search_text" in names


def test_lookup_word_returns_meaning():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = lookup_word.run({"word": "徘徊"}, ctx)
    assert "meaning" in result


def test_render_mermaid_valid():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = render_mermaid.run({"code": "graph TD; A-->B;"}, ctx)
    assert result.get("ok") is True


def test_render_mermaid_invalid():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = render_mermaid.run({"code": "not mermaid"}, ctx)
    assert result.get("ok") is False


import asyncio

from app.core.stream import StreamBus
from app.runtime.turn_engine import TurnEngine


class ScriptedProvider:
    """按脚本依次返回，模拟 LLM。"""
    name = "scripted"
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def generate(self, prompt, system="", json_mode=False):
        self.calls.append(prompt)
        return self.responses.pop(0)


def _make_engine(provider):
    reg = ToolRegistry()
    reg.register(lookup_word)
    return TurnEngine(provider=provider, registry=reg)


def test_turn_engine_single_final_answer():
    provider = ScriptedProvider(['{"final_answer": "你好呀"}'])
    engine = _make_engine(provider)
    bus = StreamBus()
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="你好", text="")
    result = asyncio.run(engine.run(ctx, bus))
    assert result["answer"] == "你好呀"
    assert len(provider.calls) == 1


def test_turn_engine_tool_then_final():
    provider = ScriptedProvider([
        '{"tool": "lookup_word", "args": {"word": "徘徊"}}',
        '{"final_answer": "徘徊是来回走动的意思"}',
    ])
    engine = _make_engine(provider)
    bus = StreamBus()
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="徘徊是什么意思", text="")
    result = asyncio.run(engine.run(ctx, bus))
    assert result["answer"] == "徘徊是来回走动的意思"
    assert len(provider.calls) == 2
    # 工具结果回填进了第二次 prompt
    assert "meaning" in provider.calls[1]


def test_turn_engine_max_steps_forced_finish():
    # 永远返回 tool 调用，触发步数上限
    provider = ScriptedProvider(['{"tool": "lookup_word", "args": {"word": "x"}}'] * 20)
    engine = _make_engine(provider)
    bus = StreamBus()
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="?", text="")
    result = asyncio.run(engine.run(ctx, bus))
    assert result["status"] == "error"
    assert len(provider.calls) <= TurnEngine.MAX_STEPS + 1


def test_turn_engine_invalid_json_falls_back():
    provider = ScriptedProvider(["not json at all"])
    engine = _make_engine(provider)
    bus = StreamBus()
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="?", text="")
    result = asyncio.run(engine.run(ctx, bus))
    assert result["status"] == "error"
    assert "抱歉" in result["answer"]
