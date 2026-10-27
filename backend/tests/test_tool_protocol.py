from app.core.tool_protocol import ToolParameter, ToolDefinition, BaseTool


def test_tool_parameter_to_schema_basic():
    p = ToolParameter(name="word", type="string", description="要查的词")
    assert p.to_schema() == {"type": "string", "description": "要查的词"}


def test_tool_parameter_to_schema_enum():
    p = ToolParameter(name="kind", type="string", enum=["a", "b"])
    assert p.to_schema()["enum"] == ["a", "b"]


def test_tool_parameter_array_has_items():
    p = ToolParameter(name="ids", type="array")
    assert p.to_schema()["items"] == {"type": "string"}


def test_tool_definition_to_schema():
    td = ToolDefinition(
        name="lookup_word",
        description="查词",
        parameters=[ToolParameter(name="word", type="string", description="词")],
    )
    schema = td.to_schema()
    assert schema["name"] == "lookup_word"
    assert schema["description"] == "查词"
    assert schema["parameters"]["properties"]["word"]["type"] == "string"
    assert "word" in schema["parameters"]["required"]


def test_tool_definition_optional_param_not_required():
    td = ToolDefinition(
        name="t",
        description="d",
        parameters=[ToolParameter(name="x", type="string", required=False)],
    )
    assert "x" not in td.to_schema()["parameters"]["required"]


def test_base_tool_to_schema():
    class Dummy(BaseTool):
        name = "dummy"
        description = "测试工具"
        parameters = [ToolParameter(name="a", type="string", description="参数")]

        def run(self, args, ctx):
            return {"ok": True}

    assert Dummy().to_schema()["name"] == "dummy"
