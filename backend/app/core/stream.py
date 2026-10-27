"""流事件协议 + 事件总线（同步收集事件列表）。"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamEvent:
    type: str                # stage | tool_call | tool_result | final
    data: dict[str, Any] = field(default_factory=dict)


class StreamBus:
    def __init__(self) -> None:
        self.events: list[StreamEvent] = []

    def emit(self, event: StreamEvent) -> None:
        self.events.append(event)
