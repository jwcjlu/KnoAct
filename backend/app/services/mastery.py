"""精通之路：掌握度评分 + 确定性判分。

compute_mastery 与 grade_answer 逐字复制自 DeepTutor（Apache-2.0）：
  - deeptutor/learning/mastery.py   (compute_mastery)
  - deeptutor/learning/grading.py   (grade_answer)
"""
import json
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from ..models import KnowledgeMastery, WordMastery
from .scheduler import next_review_after

_RECENCY_WEIGHTS = (0.5, 0.7, 0.85, 0.95, 1.0)
_CONFIDENCE_CAP = {1: 0.5, 2: 0.8}

GATE = 0.9


def compute_mastery(correctness: list[bool | float]) -> float:
    """0..1 掌握度：recency 加权 + 前 2 次封顶。"""
    if not correctness:
        return 0.0
    recent = correctness[-len(_RECENCY_WEIGHTS):]
    weights = _RECENCY_WEIGHTS[-len(recent):]
    score = sum(w * max(0.0, min(1.0, float(c)))
                for c, w in zip(recent, weights, strict=True)) / sum(weights)
    return min(score, _CONFIDENCE_CAP.get(len(recent), 1.0))


def grade_answer(user_answer: str, expected_answer: str, question_type: str = "choice") -> bool:
    user = user_answer.strip().lower()
    expected = expected_answer.strip().lower()
    if not expected:
        return False
    if question_type == "choice":
        return user.replace(" ", "") == expected.replace(" ", "")
    if question_type == "short":
        if user == expected:
            return True
        if len(expected) <= 30:
            return SequenceMatcher(None, user, expected).ratio() >= 0.85
        return False
    if question_type == "open":
        keywords = [k.strip() for k in re.split(r"[,;，；。\n]+", expected) if k.strip()]
        if not keywords:
            return False
        matched = sum(1 for kw in keywords if kw in user)
        return matched / len(keywords) >= 0.6
    return False


def is_mastered(mastery: float) -> bool:
    return mastery >= GATE


def _append(attempts: list, is_correct: bool) -> tuple[float, bool, datetime]:
    attempts.append(bool(is_correct))
    mastery = compute_mastery(attempts)
    mastered = is_mastered(mastery)
    now = datetime.utcnow()
    if mastered:
        nxt = next_review_after(6, now)   # 达标：末档 60 天
    else:
        streak = 0
        for c in reversed(attempts):
            if c:
                streak += 1
            else:
                break
        nxt = next_review_after(streak, now)
    return mastery, mastered, nxt


def record_attempt(db: Session, user_id: int, target_type: str,
                   target_id: int, is_correct: bool,
                   bucket_id: int | None = None) -> float:
    """记录一次答题，更新对应掌握度。返回新 mastery。

    target_type: 'knowledge' | 'word'
    """
    if target_type == "knowledge":
        row = (db.query(KnowledgeMastery)
               .filter_by(user_id=user_id, knowledge_point_id=target_id,
                          bucket_id=bucket_id).first())
        if not row:
            row = KnowledgeMastery(user_id=user_id, knowledge_point_id=target_id,
                                   bucket_id=bucket_id)
            db.add(row)
    else:
        row = (db.query(WordMastery)
               .filter_by(user_id=user_id, word_bank_id=target_id,
                          bucket_id=bucket_id).first())
        if not row:
            row = WordMastery(user_id=user_id, word_bank_id=target_id,
                              bucket_id=bucket_id,
                              correct_count=0, mistake_count=0, is_weak=False)
            db.add(row)

    attempts = json.loads(row.attempts or "[]")
    mastery, mastered, nxt = _append(attempts, is_correct)
    row.attempts = json.dumps(attempts)
    row.mastery = mastery
    if target_type == "knowledge":
        row.mastered = mastered
    row.next_review_at = nxt
    # 词层同时维护旧字段，供旧复习调度（select_words 依赖 mistake_count）
    if target_type == "word":
        if is_correct:
            row.correct_count += 1
            row.is_weak = False
        else:
            row.mistake_count += 1
            row.is_weak = True
            row.correct_count = 0
    db.commit()
    return mastery
