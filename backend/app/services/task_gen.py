"""今日任务生成：对每个孩子、每科，按当前课生成听写/基础练习/复习任务。"""
import json
from datetime import date, datetime

from sqlalchemy.orm import Session

from ..models import User, Lesson, LearningProgress, WordBank, KnowledgePoint, WordMastery, Task


def _current_lesson(db: Session, subject: str, user_id: int):
    """按科返回当前课：LearningProgress.current_lesson_id 匹配该科则用它，否则回退该科第一课。"""
    prog = db.query(LearningProgress).filter_by(user_id=user_id).first()
    lessons = db.query(Lesson).filter_by(subject=subject).order_by(Lesson.id).all()
    if not lessons:
        return None
    if prog and prog.current_lesson_id:
        for l in lessons:
            if l.id == prog.current_lesson_id:
                return l
    return lessons[0]


def _default_count(db: Session, key: str, fallback: int) -> int:
    from ..models import ModelConfig
    row = db.query(ModelConfig).filter_by(key=key).first()
    try:
        return int(row.value) if row and row.value else fallback
    except ValueError:
        return fallback


def _gen_dictation(db, lesson, count):
    words = db.query(WordBank).filter_by(lesson_id=lesson.id).limit(count).all()
    if not words:
        return None
    return Task(
        task_type="dictation", subject=lesson.subject, title=f"{lesson.title} 生词听写",
        detail=f"今日新学 · {len(words)} 个重点生词",
        content=json.dumps([{"id": w.id, "word": w.word, "extra": w.extra} for w in words], ensure_ascii=False),
        points=20,
    )


def _gen_knowledge(db, lesson, count):
    pts = db.query(KnowledgePoint).filter_by(lesson_id=lesson.id).limit(count).all()
    if not pts:
        return None
    return Task(
        task_type="knowledge", subject=lesson.subject, title=f"{lesson.title} 基础知识",
        detail=f"重点巩固 · {len(pts)} 个知识点",
        content=json.dumps([{"id": p.id, "content": p.content, "category": p.category} for p in pts], ensure_ascii=False),
        points=20,
    )


def _gen_review(db, lesson, count):
    now = datetime.utcnow()
    weak_ids = [r[0] for r in db.query(WordMastery.word_bank_id).filter(
        WordMastery.next_review_at.isnot(None), WordMastery.next_review_at <= now).all()]
    if not weak_ids:
        return None
    words = db.query(WordBank).filter(WordBank.id.in_(weak_ids), WordBank.lesson_id == lesson.id).limit(count).all()
    if not words:
        return None
    return Task(
        task_type="review", subject=lesson.subject, title="到期复习",
        detail=f"遗忘曲线 · {len(words)} 个到期生词",
        content=json.dumps([{"id": w.id, "word": w.word, "extra": w.extra} for w in words], ensure_ascii=False),
        points=25,
    )


def _gen_listening(db, lesson):
    words = [w.word for w in db.query(WordBank).filter_by(lesson_id=lesson.id).all()]
    kps = [p.content for p in db.query(KnowledgePoint).filter_by(lesson_id=lesson.id).all()]
    if not words:
        return None
    from ..tools.generation import generate_listening
    from ..core.context import UnifiedContext
    ctx = UnifiedContext(user_id=0, lesson_id=lesson.id, question="")
    result = generate_listening.run({"words": words, "knowledge_points": kps}, ctx)
    return Task(
        task_type="listening", subject=lesson.subject, title="英语听力练习",
        detail=f"基于 {len(words)} 个已学生词",
        content=json.dumps(result, ensure_ascii=False),
        points=15,
        content_status="published",
    )


def generate_tasks_for_user(db: Session, user_id: int, day: date):
    """为单个孩子生成当天两科任务。幂等：同 (user_id, subject, date) 已存在则跳过。"""
    subjects = ["语文", "英语"]
    for subject in subjects:
        exists = db.query(Task).filter_by(user_id=user_id, subject=subject, date=day).first()
        if exists:
            continue
        lesson = _current_lesson(db, subject, user_id)
        if not lesson:
            continue
        n_dict = _default_count(db, "task_dictation_count", 15)
        n_know = _default_count(db, "task_knowledge_count", 5)
        n_review = _default_count(db, "task_review_count", 15)
        gens = [_gen_dictation(db, lesson, n_dict),
                _gen_knowledge(db, lesson, n_know),
                _gen_review(db, lesson, n_review)]
        if subject == "英语":
            gens.append(_gen_listening(db, lesson))
        for gen in gens:
            if gen is not None:
                gen.user_id = user_id
                gen.date = day
                db.add(gen)
    db.commit()


def generate_daily_tasks(db: Session, day: date):
    """定时任务入口：为所有孩子生成当天任务。"""
    for (uid,) in db.query(User.id).filter_by(role="child").all():
        generate_tasks_for_user(db, uid, day)
