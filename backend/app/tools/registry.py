"""工具注册表。"""
from ..core.tool_protocol import BaseTool


class ToolNotFoundError(KeyError):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def list_schemas(self) -> list[dict]:
        return [t.to_schema() for t in self._tools.values()]
