"""阿里云百炼 Qwen-TTS 非实时语音合成（HTTP）。"""
from __future__ import annotations

import re

_MAX_CHARS = 600
_DEFAULT_BASE = "https://dashscope.aliyuncs.com/api/v1"
_PATH = "/services/aigc/multimodal-generation/generation"


def map_language_type(text: str) -> str:
    from .tts import tts_lang_for_text

    lang = tts_lang_for_text(text or "")
    if lang == "zh":
        return "Chinese"
    if lang == "en":
        return "English"
    return "Auto"


def split_for_qwen(text: str, max_chars: int = _MAX_CHARS) -> list[str]:
    """按句切分；单句仍超限则硬切。保证拼接还原原文。"""
    body = text or ""
    if len(body) <= max_chars:
        return [body] if body.strip() else []

    parts = [p for p in re.split(r"(?<=[。！？；!?;])", body) if p]
    out: list[str] = []
    buf = ""
    for part in parts:
        while len(part) > max_chars:
            out.append(part[:max_chars])
            part = part[max_chars:]
        if len(buf + part) <= max_chars:
            buf += part
            continue
        if buf:
            out.append(buf)
        buf = part
    if buf:
        out.append(buf)
    return out