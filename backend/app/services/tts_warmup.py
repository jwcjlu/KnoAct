from __future__ import annotations

import json
import logging

from .model_config import resolve
from .tts import get_tts, synthesize_commercial_cached

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


def _should_skip_warmup(tts) -> bool:
    return getattr(tts, "name", "") == "fake"


def _configured_speed(db, child_id=None) -> float:
    try:
        raw = (resolve(db, "tts", child_id).options or {}).get("speed")
        val = float(raw)
    except (TypeError, ValueError):
        return 1.0
    return max(0.5, min(2.0, val))


def warmup_dictation_task(task_id: int) -> None:
    """自开 Session；失败吞掉。供线程目标调用。"""
    from ..database import SessionLocal
    from ..models import Task

    db = SessionLocal()
    try:
        task = db.query(Task).filter_by(id=task_id, task_type="dictation").first()
        if not task:
            return
        tts = get_tts(db, task.user_id)
        if _should_skip_warmup(tts):
            logger.info("warmup skip fake task_id=%s", task_id)
            return
        texts = collect_dictation_warmup_texts(task.content)
        logger.info(
            "warmup start task_id=%s user_id=%s n=%s",
            task_id,
            task.user_id,
            len(texts),
        )
        speed = _configured_speed(db, task.user_id)
        voice = tts.voice or ""
        for text in texts:
            try:
                synthesize_commercial_cached(
                    db,
                    text,
                    voice=voice,
                    speed=speed,
                    child_id=task.user_id,
                )
            except Exception as e:
                logger.info(
                    "warmup item_fail task_id=%s text_len=%s err=%s",
                    task_id,
                    len(text),
                    str(e)[:120],
                )
        logger.info("warmup done task_id=%s", task_id)
    except Exception as e:
        logger.info("warmup abort task_id=%s err=%s", task_id, str(e)[:120])
    finally:
        db.close()


def schedule_dictation_warmup(task_id: int) -> None:
    """短命 daemon 线程；不阻塞调用方。"""
    import threading

    threading.Thread(
        target=warmup_dictation_task,
        args=(task_id,),
        daemon=True,
        name=f"tts-warmup-{task_id}",
    ).start()