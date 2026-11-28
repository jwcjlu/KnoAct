"""语文听写课堂报读：分类、种子化、拼装 speak_text/accept。"""
from __future__ import annotations
import json
import re

from .word_kinds import KIND_PHRASE, KIND_RECOGNIZE, KIND_WORD, KIND_WRITE

_HAN = re.compile(r"[\u4e00-\u9fff]+")


def _han_len(s: str) -> int:
    return len("".join(_HAN.findall(s or "")))


def _han_only(s: str) -> str:
    return "".join(_HAN.findall(s or ""))


def classify_speak_mode(*, kind: str | None, word: str) -> str:
    k = (kind or "").strip()
    if k in (KIND_WRITE, KIND_RECOGNIZE):
        return "char"
    if k in (KIND_PHRASE, KIND_WORD):
        return "word"
    return "char" if _han_len(word) <= 1 else "word"


def _extra_gloss_part(extra: str) -> str:
    parts = (extra or "").strip().split()
    if len(parts) <= 1:
        return (extra or "").strip()
    return " ".join(parts[1:]).strip()


def seed_compound_from_extra(word: str, extra: str) -> str | None:
    g = _han_only(_extra_gloss_part(extra))
    if not g or word not in g:
        return None
    n = _han_len(g)
    if 2 <= n <= 4:
        return g
    return None


def gloss_from_extra(word: str, extra: str) -> str | None:
    g = _extra_gloss_part(extra).strip()
    if not g:
        return None
    # 去掉可能的非汉字噪音后量汉字长度；保留原文短释义供播报
    if _han_len(g) == 0 or _han_len(g) > 8:
        return None
    return g


def parse_cue(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def dump_cue(cue: dict) -> str:
    return json.dumps(cue or {}, ensure_ascii=False)


def valid_compound(word: str, compound: str | None) -> str | None:
    c = (compound or "").strip()
    if not c or word not in c:
        return None
    if not (2 <= _han_len(c) <= 4):
        return None
    return c


def valid_gloss(gloss: str | None) -> str | None:
    g = (gloss or "").strip()
    if not g or _han_len(g) == 0 or _han_len(g) > 8:
        return None
    return g


def build_speak_payload(
    *, word: str, kind: str | None, compound: str | None, gloss_short: str | None
) -> dict:
    mode = classify_speak_mode(kind=kind, word=word)
    if mode == "char":
        c = valid_compound(word, compound)
        if c:
            return {
                "speak_text": f"{word}，{c}的{word}",
                "speak_incomplete": False,
                "accept": [word, c],
            }
        return {
            "speak_text": f"{word}，{word}",
            "speak_incomplete": True,
            "accept": [word],
        }
    g = valid_gloss(gloss_short)
    if g:
        return {
            "speak_text": f"{word}，{g}",
            "speak_incomplete": False,
            "accept": [word],
        }
    return {
        "speak_text": f"{word}，{word}",
        "speak_incomplete": True,
        "accept": [word],
    }


def resolve_cues_for_word(*, word: str, kind: str | None, extra: str, cue_raw: str | None) -> dict:
    """合并 dictation_cue + extra 种子，返回 {compound, gloss_short, source}。"""
    cue = parse_cue(cue_raw)
    compound = valid_compound(word, cue.get("compound"))
    gloss = valid_gloss(cue.get("gloss_short"))
    source = cue.get("source") or ""
    mode = classify_speak_mode(kind=kind, word=word)
    if mode == "char" and not compound:
        seeded = seed_compound_from_extra(word, extra)
        if seeded:
            compound, source = seeded, "extra"
    if mode == "word" and not gloss:
        seeded_g = gloss_from_extra(word, extra)
        if seeded_g:
            gloss, source = seeded_g, "extra"
    return {"compound": compound or "", "gloss_short": gloss or "", "source": source}