# backend/app/services/practice_grade.py
"""练习册判分入口：从 ORM 对象取字段，转交 math_grade。

这是 `math_grade.grade_by_answer_kind()` 的**薄包装**——按 answer_kind 分派的
具体逻辑只有一份，在 math_grade.py 里。此处只做「ORM 字段 → 判分参数」的搬运，
避免 bank.py / practice.py 各自拼字段。
"""
import json

from ..core.work_modes import answer_kind_of
from .math_grade import grade_by_answer_kind


def _parse_json(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def _blanks_from(answer_json: dict) -> list[str]:
    raw = answer_json.get("blanks")
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw]


def grade_practice_item(
    db,
    question,
    student_answer: str = "",
    *,
    blanks: list | None = None,
    photo_bytes: bytes | None = None,
) -> dict:
    """判一道练习册小题。返回 {is_correct, ai_status, final_answer,
    steps_plausible, reason}。

    `blanks` 为多空题的逐空作答；不传则从 `student_answer` 按逗号切。
    """
    work_mode = getattr(question, "work_mode", "") or ""
    answer_json = _parse_json(getattr(question, "answer_json", "") or "")
    expected_blanks = _blanks_from(answer_json)

    if blanks is None:
        if expected_blanks and student_answer:
            blanks = [s.strip() for s in student_answer.split(",")]
        else:
            blanks = []

    return grade_by_answer_kind(
        db,
        answer_kind=answer_kind_of(work_mode),
        answer=getattr(question, "answer", "") or "",
        answer_json=answer_json,
        student_answer=student_answer,
        blanks=blanks,
        photo_bytes=photo_bytes,
        question=getattr(question, "question", "") or "",
    )
