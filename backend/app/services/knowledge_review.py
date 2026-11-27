"""知识点复习队列：按学习进度与掌握度准入。"""
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import (
    KnowledgeMastery, KnowledgePoint, KnowledgeReviewItem, Lesson, Mistake, Question,
)

logger = logging.getLogger(__name__)


def in_progress_scope(db: Session, user_id: int, kp: KnowledgePoint) -> bool:
    if not kp.lesson_id:
        return False
    lesson = db.get(Lesson, kp.lesson_id)
    if not lesson:
        return False
    from .learning_progress import get_progress

    prog = get_progress(db, user_id, lesson.document_id, lesson.subject)
    if not prog or not prog.current_lesson_id:
        return False
    lessons = (
        db.query(Lesson)
        .filter_by(document_id=lesson.document_id, subject=lesson.subject)
        .order_by(Lesson.id)
        .all()
    )
    ids = [l.id for l in lessons]
    if lesson.id not in ids or prog.current_lesson_id not in ids:
        return False
    return ids.index(lesson.id) <= ids.index(prog.current_lesson_id)


def try_enroll(
    db: Session,
    user_id: int,
    knowledge_point_id: int,
    *,
    enrolled_by=None,
    source="mastery",
):
    from .bucket_guard import resolve_bucket_id
    from .mastery import GATE
    from .scheduler import INTERVALS

    bid = resolve_bucket_id(db, user_id, None)
    if bid is None:
        return None
    kp = db.get(KnowledgePoint, knowledge_point_id)
    if not kp or not in_progress_scope(db, user_id, kp):
        return None
    m = (
        db.query(KnowledgeMastery)
        .filter_by(user_id=user_id, knowledge_point_id=knowledge_point_id, bucket_id=bid)
        .first()
    )
    if not m or not (m.mastered or m.mastery >= GATE):
        return None
    row = (
        db.query(KnowledgeReviewItem)
        .filter_by(user_id=user_id, knowledge_point_id=knowledge_point_id, bucket_id=bid)
        .first()
    )
    if row and row.status in ("active", "paused"):
        return None
    now = datetime.utcnow()
    if row is None:
        row = KnowledgeReviewItem(
            user_id=user_id, knowledge_point_id=knowledge_point_id, bucket_id=bid
        )
        db.add(row)
    row.status = "active"
    row.interval_index = 0
    row.next_review_at = now + timedelta(days=INTERVALS[0])
    row.enrolled_by = enrolled_by
    row.enroll_source = source
    row.enrolled_at = now
    row.updated_at = now
    db.flush()
    return row


def enroll_due_to_progress(
    db: Session,
    user_id: int,
    document_id: int | None,
    subject: str,
    *,
    old_lesson_id: int | None,
    new_lesson_id: int | None,
    enrolled_by=None,
) -> int:
    """进度前推时，为新纳入进度范围的已掌握知识点补入复习队列（不后退撤队）。"""
    if new_lesson_id is None:
        return 0
    q = db.query(Lesson).filter(Lesson.subject == subject)
    if document_id is not None:
        q = q.filter(Lesson.document_id == document_id)
    lessons = q.order_by(Lesson.id).all()
    ids = [l.id for l in lessons]
    if new_lesson_id not in ids:
        return 0
    new_idx = ids.index(new_lesson_id)
    old_idx = ids.index(old_lesson_id) if old_lesson_id in ids else -1
    if new_idx < old_idx:
        return 0
    if old_lesson_id is None or old_lesson_id not in ids:
        lesson_ids = ids[: new_idx + 1]
    else:
        lesson_ids = ids[old_idx + 1 : new_idx + 1]
    if not lesson_ids:
        return 0
    kps = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.lesson_id.in_(lesson_ids))
        .all()
    )
    n = 0
    for kp in kps:
        if try_enroll(
            db,
            user_id,
            kp.id,
            enrolled_by=enrolled_by,
            source="progress_adjust",
        ):
            n += 1
    return n


def apply_review_result(db: Session, item: KnowledgeReviewItem, result: str) -> KnowledgeReviewItem:
    """根据三档自评更新 SRS 间隔（remember / fuzzy / forgot）。"""
    from .scheduler import INTERVALS

    now = datetime.utcnow()
    if item.last_result and item.updated_at and item.updated_at.date() == now.date():
        return item
    i = item.interval_index or 0
    if result == "remember":
        i = min(i + 1, len(INTERVALS) - 1)
        item.next_review_at = now + timedelta(days=INTERVALS[i])
    elif result == "fuzzy":
        item.next_review_at = now + timedelta(days=INTERVALS[i])
    else:
        i = 0
        item.next_review_at = now + timedelta(days=INTERVALS[0])
    item.interval_index = i
    item.last_result = result
    item.updated_at = now
    db.flush()
    return item


# ---------------------------------------------------------------------------
# 到期选取 / 出题回退 / 完成复习
# ---------------------------------------------------------------------------

RESULTS = ("remember", "fuzzy", "forgot")


class KnowledgeReviewError(Exception):
    """业务错误；code 供路由映射 HTTP 状态。"""

    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def select_due_items(
    db: Session, user_id: int, subject: str | None = None
) -> list[KnowledgeReviewItem]:
    """到期的 active 复习项：当前 active 桶；按学科各取 task_kp_review_count 个。"""
    from .bucket_guard import resolve_bucket_id
    from .child_config import get_child_config_int

    bid = resolve_bucket_id(db, user_id, None)
    if bid is None:
        return []
    now = datetime.utcnow()
    q = (
        db.query(KnowledgeReviewItem, KnowledgePoint)
        .join(KnowledgePoint, KnowledgeReviewItem.knowledge_point_id == KnowledgePoint.id)
        .filter(
            KnowledgeReviewItem.user_id == user_id,
            KnowledgeReviewItem.bucket_id == bid,
            KnowledgeReviewItem.status == "active",
            KnowledgeReviewItem.next_review_at.isnot(None),
            KnowledgeReviewItem.next_review_at <= now,
        )
    )
    if subject:
        q = q.filter(KnowledgePoint.subject == subject)
    rows = q.order_by(
        KnowledgeReviewItem.next_review_at,
        KnowledgeReviewItem.interval_index,
        KnowledgeReviewItem.id,
    ).all()
    cap = max(get_child_config_int(db, user_id, "task_kp_review_count", 6), 0)
    per_subject: dict[str, int] = {}
    picked: list[KnowledgeReviewItem] = []
    for item, kp in rows:
        n = per_subject.get(kp.subject, 0)
        if n >= cap:
            continue
        per_subject[kp.subject] = n + 1
        picked.append(item)
    return picked


def _question_kp_id(q: Question) -> int | None:
    for raw in (q.extra, q.tags):
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("knowledge_point_id") is not None:
            try:
                return int(data["knowledge_point_id"])
            except (TypeError, ValueError):
                continue
    return None


def _find_reusable_question(db: Session, user_id: int, kp_id: int) -> Question | None:
    pat = f'%"knowledge_point_id": {kp_id}%'
    cands = (
        db.query(Question)
        .filter(
            or_(Question.extra.like(pat), Question.tags.like(pat)),
            or_(Question.user_id == user_id, Question.user_id.is_(None)),
            Question.answer != "",
            Question.question != "",
        )
        .order_by(Question.id.desc())
        .limit(200)
        .all()
    )
    for q in cands:
        if (q.answer or "").strip() and _question_kp_id(q) == kp_id:
            return q
    return None


def _question_keywords(q: Question) -> list[str]:
    try:
        data = json.loads(q.extra or "{}")
    except ValueError:
        return []
    kws = data.get("keywords") if isinstance(data, dict) else None
    return [str(k).strip() for k in (kws or []) if str(k).strip()]


def _prompt_from_question(q: Question, source: str) -> dict:
    # 不下发标准答案：判分只在服务端按 question_id 进行
    return {
        "source": source,
        "question_id": q.id,
        "question": q.question,
        "qtype": "short",
    }


def _build_prompt(db: Session, user_id: int, kp: KnowledgePoint) -> dict:
    """reuse（已有题）→ generated（现出并落库）→ self_rate（无题，纯自评）。"""
    from .bucket_guard import resolve_bucket_id

    existing = _find_reusable_question(db, user_id, kp.id)
    if existing:
        return _prompt_from_question(existing, "reuse")
    try:
        from .knowledge_quiz import generate_knowledge_questions

        out = generate_knowledge_questions(
            db, [{"id": kp.id, "content": kp.content, "category": kp.category}], kp.subject
        )
        item = out[0] if out else {}
        text = (item.get("question") or "").strip()
        answer = (item.get("answer") or "").strip()
        if text and answer:
            q = Question(
                lesson_id=kp.lesson_id,
                qtype="knowledge",
                question=text,
                answer=answer,
                subject=kp.subject,
                date=datetime.utcnow().date(),
                status="pending",
                task_type="knowledge",
                user_id=user_id,
                bucket_id=resolve_bucket_id(db, user_id, None),
                extra=json.dumps(
                    {
                        "knowledge_point_id": kp.id,
                        "keywords": item.get("keywords") or [],
                        "content": kp.content or "",
                    },
                    ensure_ascii=False,
                ),
            )
            db.add(q)
            db.flush()
            return _prompt_from_question(q, "generated")
    except Exception:
        logger.exception("knowledge review prompt generation failed kp=%s", kp.id)
    return {"source": "self_rate", "question_id": None, "question": None, "qtype": None}


def serialize_due_item(db: Session, user_id: int, item: KnowledgeReviewItem) -> dict:
    kp = db.get(KnowledgePoint, item.knowledge_point_id)
    lesson = db.get(Lesson, kp.lesson_id) if kp and kp.lesson_id else None
    content = (kp.content if kp else "") or ""
    return {
        "item_id": item.id,
        "knowledge_point_id": item.knowledge_point_id,
        "title": content[:40],
        "content": content,
        "lesson_title": lesson.title if lesson else "",
        "prompt": _build_prompt(db, user_id, kp) if kp else
        {"source": "self_rate", "question_id": None, "question": None, "qtype": None},
    }


def maybe_settle_kp_review_task(db: Session, user_id: int, subject: str) -> None:
    """占位：后续任务接入每日 KP 复习任务的自动结算。"""
    return None


def _grade_question(db: Session, q: Question, student_answer: str) -> bool:
    from .knowledge_quiz import grade_knowledge_answer
    from .mastery import grade_answer

    kws = _question_keywords(q)
    if kws:
        ok, _ = grade_knowledge_answer(student_answer, kws, q.answer or "", db=db)
        return ok
    return grade_answer(student_answer or "", q.answer or "", "short")


def _record_kp_mistake(
    db: Session, user_id: int, bucket_id, kp: KnowledgePoint,
    question: str, your_answer: str, correct_answer: str,
) -> None:
    row = (
        db.query(Mistake)
        .filter_by(user_id=user_id, knowledge_point_id=kp.id, bucket_id=bucket_id,
                   source_type="review")
        .first()
    )
    if row:
        row.mistake_count += 1
        row.consecutive_correct = 0
        row.question = question
        row.your_answer = your_answer
        row.correct_answer = correct_answer
    else:
        db.add(Mistake(
            user_id=user_id, bucket_id=bucket_id, source_type="review",
            question=question, your_answer=your_answer, correct_answer=correct_answer,
            knowledge_point_id=kp.id,
        ))


def complete_item(
    db: Session,
    user_id: int,
    item_id: int,
    result: str,
    question_id: int | None = None,
    student_answer: str | None = None,
    duration_ms: int | None = None,
) -> dict:
    from .answer_record import record_answer
    from .mastery import record_attempt

    if result not in RESULTS:
        raise KnowledgeReviewError("invalid_result", 400)
    item = db.get(KnowledgeReviewItem, item_id)
    if item is None or item.user_id != user_id:
        raise KnowledgeReviewError("item_not_found", 404)
    if item.status != "active":
        raise KnowledgeReviewError("item_not_active", 400)
    kp = db.get(KnowledgePoint, item.knowledge_point_id)
    if kp is None:
        raise KnowledgeReviewError("item_not_found", 404)

    graded = False
    is_correct: bool | None = None
    q: Question | None = None
    if question_id is not None:
        q = db.get(Question, question_id)
        if q is None or _question_kp_id(q) != kp.id:
            raise KnowledgeReviewError("question_not_found", 404)
        is_correct = _grade_question(db, q, student_answer or "")
        graded = True
        # 服务端判分为准：答错必为 forgot；答对时保留孩子的 fuzzy 自评，否则 remember
        if not is_correct:
            result = "forgot"
        elif result != "fuzzy":
            result = "remember"

    apply_review_result(db, item, result)

    q_text = q.question if q else (kp.content or "")
    std = q.answer if q else (kp.content or "")
    ans_correct = is_correct if graded else (result != "forgot")
    record_answer(
        db, user_id=user_id, subject=kp.subject, module="knowledge",
        question=q_text, student_answer=student_answer or result,
        correct_answer=std or "", is_correct=bool(ans_correct),
        duration_ms=duration_ms, source_type="knowledge_review",
        source_id=kp.id, lesson_id=kp.lesson_id, bucket_id=item.bucket_id,
    )
    if result == "forgot":
        _record_kp_mistake(
            db, user_id, item.bucket_id, kp, q_text, student_answer or "", std or "",
        )
    db.flush()
    if graded:
        # record_attempt 内部 commit
        record_attempt(db, user_id, "knowledge", kp.id, bool(is_correct),
                       bucket_id=item.bucket_id)
    else:
        db.commit()
    maybe_settle_kp_review_task(db, user_id, kp.subject)
    db.refresh(item)
    return {
        "ok": True,
        "result": result,
        "is_correct": is_correct,
        "graded": graded,
        "interval_index": item.interval_index,
        "next_review_at": item.next_review_at.isoformat() if item.next_review_at else None,
    }


def _get_item_for_user(db: Session, user_id: int, item_id: int) -> KnowledgeReviewItem:
    item = db.get(KnowledgeReviewItem, item_id)
    if item is None or item.user_id != user_id:
        raise KnowledgeReviewError("item_not_found", 404)
    return item


def pause_item(db: Session, user_id: int, item_id: int) -> KnowledgeReviewItem:
    """暂停：冻结 next_review_at，不再被选为到期。（不动 updated_at，避免触发当日去重）"""
    item = _get_item_for_user(db, user_id, item_id)
    if item.status != "active":
        raise KnowledgeReviewError("item_not_active", 400)
    item.status = "paused"
    db.commit()
    kp = db.get(KnowledgePoint, item.knowledge_point_id)
    if kp:
        maybe_settle_kp_review_task(db, user_id, kp.subject)
    return item


def resume_item(db: Session, user_id: int, item_id: int) -> KnowledgeReviewItem:
    item = _get_item_for_user(db, user_id, item_id)
    if item.status != "paused":
        raise KnowledgeReviewError("item_not_paused", 400)
    item.status = "active"
    db.commit()
    return item


def remove_item(db: Session, user_id: int, item_id: int) -> KnowledgeReviewItem:
    item = _get_item_for_user(db, user_id, item_id)
    if item.status == "removed":
        return item
    item.status = "removed"
    db.commit()
    kp = db.get(KnowledgePoint, item.knowledge_point_id)
    if kp:
        maybe_settle_kp_review_task(db, user_id, kp.subject)
    return item
