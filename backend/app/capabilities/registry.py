"""能力注册表：mode → capability。"""
from ..core.capability_protocol import TurnCapability
from .chat import ChatCapability, VisualizeCapability, SolveCapability


class CapabilityRegistry:
    def __init__(self) -> None:
        self._caps: dict[str, TurnCapability] = {
            "chat": ChatCapability(),
            "visualize": VisualizeCapability(),
            "solve": SolveCapability(),
        }

    def get(self, mode: str) -> TurnCapability:
        return self._caps.get(mode, self._caps["chat"])
