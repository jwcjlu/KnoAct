"""做题明细写入 helper：各做题入口判分后逐题调用。"""
from sqlalchemy.orm import Session

from ..models import AnswerRecord


def record_answer(
    db: Session,
    *,
    user_id: int,
    subject: str,
    module: str,
    question: str,
    student_answer: str = "",
    correct_answer: str = "",
    is_correct: bool = False,
    difficulty: str = "",
    duration_ms: int | None = None,
    source_type: str = "",
    source_id: int | None = None,
    lesson_id: int | None = None,
    bucket_id: int | None = None,
) -> AnswerRecord:
    row = AnswerRecord(
        user_id=user_id, bucket_id=bucket_id, subject=subject or "",
        module=module, lesson_id=lesson_id, question=question or "",
        student_answer=student_answer or "", correct_answer=correct_answer or "",
        is_correct=is_correct, difficulty=difficulty or "",
        duration_ms=duration_ms, source_type=source_type, source_id=source_id,
    )
    db.add(row)
    return row
