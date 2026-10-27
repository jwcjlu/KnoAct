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
