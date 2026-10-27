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


def test_search_text_uses_sentences_field():
    # text 是一整行（无换行），但 sentences 显式给出两句；「适宜」在第 2 句
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="",
                         text="白鹭是一首精巧的诗。色素的配合，身段的大小，一切都很适宜。",
                         sentences=["白鹭是一首精巧的诗。", "色素的配合，身段的大小，一切都很适宜。"])
    result = search_text.run({"query": "适宜"}, ctx)
    # 用 sentences 时，第 2 句才含「适宜」→ sentence_no == 2
    # 旧代码用 text.splitlines() 只有 1 行 → sentence_no == 1（错）
    assert result["matches"][0]["sentence_no"] == 2


def test_search_text_falls_back_to_text_split():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="",
                         text="第一句。\n第二句。", sentences=[])
    result = search_text.run({"query": "第二"}, ctx)
    assert result["matches"][0]["sentence_no"] == 2


def test_search_text_no_sentences_and_no_text():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = search_text.run({"query": "任何"}, ctx)
    assert result["matches"] == []


def test_lookup_word_returns_meaning():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = lookup_word.run({"word": "徘徊"}, ctx)
    assert "meaning" in result


def test_lookup_word_error_path_returns_error_not_fake_meaning(monkeypatch):
    import app.tools.builtin as builtin
    import app.services.ai as ai
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    def boom(db):
        raise RuntimeError("no key")
    monkeypatch.setattr(ai, "get_provider", boom)
    result = builtin.lookup_word.run({"word": "徘徊"}, ctx)
    assert result["meaning"] == ""
    assert "error" in result


def test_render_mermaid_valid():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = render_mermaid.run({"code": "graph TD; A-->B;"}, ctx)
    assert result.get("ok") is True


def test_render_mermaid_invalid():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = render_mermaid.run({"code": "not mermaid"}, ctx)
    assert result.get("ok") is False


def test_render_mermaid_rejects_non_declaration_substring():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = render_mermaid.run({"code": "photograph of a graph"}, ctx)
    assert result.get("ok") is False


def test_render_mermaid_accepts_extended_types():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = render_mermaid.run({"code": "sequenceDiagram\nAlice->>Bob: hi"}, ctx)
    assert result.get("ok") is True


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


def test_turn_engine_uses_custom_system_prompt():
    provider = ScriptedProvider(['{"final_answer": "ok"}'])
    reg = ToolRegistry()
    reg.register(lookup_word)
    engine = TurnEngine(provider=provider, registry=reg, system_prompt="自定义提示词XYZ")
    bus = StreamBus()
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="?", text="")
    asyncio.run(engine.run(ctx, bus))
    # system prompt 是 generate 的第二个位置参数，这里通过检查第二次生成调用来验证太复杂；
    # 改为直接验证 _system 方法
    assert "自定义提示词XYZ" in engine._system(ctx)


def test_forced_finish_prompt_includes_context_and_no_fabrication():
    provider = ScriptedProvider(["not json", '{"final_answer": "白鹭是精巧的诗"}'])
    reg = ToolRegistry()
    reg.register(lookup_word)
    engine = TurnEngine(provider=provider, registry=reg)
    bus = StreamBus()
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="?", text="白鹭是一首精巧的诗。")
    asyncio.run(engine.run(ctx, bus))
    # 第一次调用解析失败 → _forced_finish 第二次调用
    assert len(provider.calls) == 2
    forced_prompt = provider.calls[1]
    assert "教材上下文" in forced_prompt
    assert "白鹭是一首精巧的诗" in forced_prompt
    assert "不要编造" in forced_prompt
