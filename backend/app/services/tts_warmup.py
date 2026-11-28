from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)
_MAX_TEXTS_PER_TASK = 40


def collect_dictation_warmup_texts(content) -> list[str]:
    if isinstance(content, str):
        try:
            content = json.loads(content or "[]")
        except json.JSONDecodeError:
            return []
    if not isinstance(content, list):
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = (s or "").strip()
        if not s or s in seen:
            return
        seen.add(s)
        out.append(s)

    for item in content:
        if not isinstance(item, dict):
            continue
        speak = (item.get("speak_text") or "").strip()
        word = (item.get("word") or "").strip()
        if speak:
            add(speak)
        if word and word != speak:
            add(word)
        elif word and not speak:
            add(word)
        if len(out) >= _MAX_TEXTS_PER_TASK:
            break
    return out[:_MAX_TEXTS_PER_TASK]