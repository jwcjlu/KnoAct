"""能力协议：TurnCapability + CapabilityManifest。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .context import UnifiedContext
from .stream import StreamBus


@dataclass
class CapabilityManifest:
    name: str
    description: str
    stages: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)


class TurnCapability(ABC):
    manifest: CapabilityManifest

    @abstractmethod
    async def run(self, ctx: UnifiedContext, stream: StreamBus) -> None:
        """执行能力流水线，向 stream 发事件。"""
        ...

    @property
    def name(self) -> str:
        return self.manifest.name
