"""统一上下文：一次 turn 的输入。"""
from dataclasses import dataclass


@dataclass
class UnifiedContext:
    user_id: int
    lesson_id: int
    question: str
    text: str = ""
    mode: str = "chat"
    model: str = ""
