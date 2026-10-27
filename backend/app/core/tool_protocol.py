"""工具协议：BaseTool + ToolDefinition + ToolParameter。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .context import UnifiedContext


@dataclass
class ToolParameter:
    name: str
    type: str  # "string" | "integer" | "boolean" | "number" | "array" | "object"
    description: str = ""
    required: bool = True
    default: Any = None
    enum: list[str] | None = None
    items: dict[str, Any] | None = None

    def to_schema(self) -> dict[str, Any]:
        schema: dict[str, Any] = {"type": self.type, "description": self.description}
        if self.enum:
            schema["enum"] = list(self.enum)
        if self.type == "array":
            schema["items"] = self.items if self.items is not None else {"type": "string"}
        return schema


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)

    def to_schema(self) -> dict[str, Any]:
        props = {p.name: p.to_schema() for p in self.parameters}
        required = [p.name for p in self.parameters if p.required]
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        }


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: list[ToolParameter] = []

    def to_schema(self) -> dict[str, Any]:
        return ToolDefinition(
            name=self.name, description=self.description, parameters=self.parameters
        ).to_schema()

    @abstractmethod
    def run(self, args: dict[str, Any], ctx: UnifiedContext) -> dict[str, Any]:
        """同步执行，返回 JSON 可序列化的结果 dict。"""
        ...
