"""流事件协议 + 事件总线（同步收集 + 可选实时推送）。"""
import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamEvent:
    type: str                # stage | tool_call | tool_result | final
    data: dict[str, Any] = field(default_factory=dict)


class StreamBus:
    def __init__(self) -> None:
        self.events: list[StreamEvent] = []
        self._queue: asyncio.Queue | None = None   # 惰性创建，仅流式路径用

    def emit(self, event: StreamEvent) -> None:
        self.events.append(event)
        if self._queue is not None:
            self._queue.put_nowait(event)

    def subscribe(self) -> asyncio.Queue:
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue
