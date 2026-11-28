"""批量 AI 补全听写组词/短释义（失败静默，不阻塞听写）。"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from .ai import get_provider
from .dictation_speak import (
    _han_len,
    classify_speak_mode,
    dump_cue,
    parse_cue,
    resolve_cues_for_word,
    valid_compound,
    valid_gloss,
)

FILL_TIMEOUT_SEC = 15.0

_FILL_SYSTEM = (
    "你是小学语文听写助手。只输出合法 JSON，不要 markdown 或其它说明。"
)

_FILL_PROMPT = """请为下列词条补全听写播报线索。
规则：
- mode 为 char：给出 compound，2–4 个汉字且必须包含该字（组词）
- mode 为 word：给出 gloss_short，仅汉字释义，长度 4–8 字
- 每条只补缺失的那一类字段，另一字段可留空字符串

词条：
{lines}

返回 JSON：{{"items":[{{"id":<数字>,"compound":"...","gloss_short":"..."}}, ...]}}"""


def valid_ai_gloss(gloss: str | None) -> str | None:
    g = valid_gloss(gloss)
    if not g:
        return None
    n = _han_len(g)
    if not (4 <= n <= 8):
        return None
    return g


def fill_missing_cues(
    db: Session, words: list, timeout: float = FILL_TIMEOUT_SEC
) -> None:
    try:
        need: list[dict] = []
        by_id: dict[int, object] = {}
        for w in words:
            resolved = resolve_cues_for_word(
                word=w.word,
                kind=w.kind,
                extra=w.extra or "",
                cue_raw=w.dictation_cue or "",
            )
            mode = classify_speak_mode(kind=w.kind, word=w.word)
            missing = (mode == "char" and not resolved["compound"]) or (
                mode == "word" and not resolved["gloss_short"]
            )
            if not missing:
                continue
            need.append(
                {
                    "id": w.id,
                    "word": w.word,
                    "kind": w.kind or "",
                    "mode": mode,
                }
            )
            by_id[w.id] = w

        if not need:
            return

        lines = "\n".join(
            f'- id={n["id"]} word={n["word"]!r} kind={n["kind"]!r} mode={n["mode"]}'
            for n in need
        )
        prompt = _FILL_PROMPT.format(lines=lines)
        raw = get_provider(db).generate(
            prompt,
            system=_FILL_SYSTEM,
            json_mode=True,
            timeout=timeout,
        )
        data = json.loads(raw or "{}")
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return

        for item in items:
            if not isinstance(item, dict):
                continue
            wid = item.get("id")
            w = by_id.get(wid)
            if w is None:
                continue
            mode = classify_speak_mode(kind=w.kind, word=w.word)
            existing = parse_cue(w.dictation_cue)
            updated = False
            if mode == "char":
                c = valid_compound(w.word, item.get("compound"))
                if c:
                    existing["compound"] = c
                    updated = True
            elif mode == "word":
                g = valid_ai_gloss(item.get("gloss_short"))
                if g:
                    existing["gloss_short"] = g
                    updated = True
            if updated:
                existing["source"] = "ai"
                w.dictation_cue = dump_cue(existing)

        db.flush()
    except Exception:
        return