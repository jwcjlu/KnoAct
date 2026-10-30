"""今日任务生成：对每个孩子、每科，按当前课生成听写/基础练习/复习任务。"""
import json
from datetime import date, datetime

from sqlalchemy.orm import Session

from ..models import User, Lesson, LearningProgress, WordBank, KnowledgePoint, WordMastery, KnowledgeMastery, Task, Text


def _current_lesson(db: Session, subject: str, user_id: int):
    """按科返回当前课：LearningProgress 匹配 (user_id, subject) 则用它，否则回退该科第一课。"""
    prog = db.query(LearningProgress).filter_by(user_id=user_id, subject=subject).first()
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


def _gen_dictation(db, lesson, user_id, count, new_ratio=5):
    """按遗忘曲线出听写：当前课取「新」名额，旧课到期词取「旧」名额，凑不满不补。"""
    subject = lesson.subject
    # 新：当前课生词
    new_words = db.query(WordBank).filter_by(lesson_id=lesson.id).order_by(WordBank.id).limit(new_ratio).all()
    # 旧：其它课中到期待复习的词（next_review_at <= now），按用户隔离
    now = datetime.utcnow()
    due_ids = [r[0] for r in db.query(WordMastery.word_bank_id).filter(
        WordMastery.user_id == user_id,
        WordMastery.next_review_at.isnot(None), WordMastery.next_review_at <= now).all()]
    due_words = []
    if due_ids:
        due_words = (db.query(WordBank)
                     .filter(WordBank.id.in_(due_ids), WordBank.lesson_id != lesson.id)
                     .order_by(WordBank.id).limit(max(0, count - new_ratio)).all())
    words = new_words + due_words
    if not words:
        return None
    return Task(
        task_type="dictation", subject=subject, title=f"{lesson.title} 生词听写",
        detail=f"今日听写 · {len(words)} 个（新课 {len(new_words)} + 复习 {len(due_words)}）",
        content=json.dumps([{"id": w.id, "word": w.word, "extra": w.extra} for w in words], ensure_ascii=False),
        points=20,
    )


def _gen_knowledge(db, lesson, user_id, count, new_ratio=5):
    """按遗忘曲线出知识点：当前课取「新」名额，旧课到期知识点取「旧」名额。"""
    subject = lesson.subject
    new_pts = db.query(KnowledgePoint).filter_by(lesson_id=lesson.id).order_by(KnowledgePoint.id).limit(new_ratio).all()
    now = datetime.utcnow()
    due_ids = [r[0] for r in db.query(KnowledgeMastery.knowledge_point_id).filter(
        KnowledgeMastery.user_id == user_id,
        KnowledgeMastery.next_review_at.isnot(None), KnowledgeMastery.next_review_at <= now).all()]
    due_pts = []
    if due_ids:
        due_pts = (db.query(KnowledgePoint)
                   .join(KnowledgeMastery, KnowledgeMastery.knowledge_point_id == KnowledgePoint.id)
                   .filter(KnowledgePoint.id.in_(due_ids), KnowledgePoint.lesson_id != lesson.id,
                           KnowledgeMastery.user_id == user_id)
                   .order_by(KnowledgeMastery.mastery.asc(), KnowledgePoint.id)
                   .limit(max(0, count - new_ratio)).all())
    pts = new_pts + due_pts
    if not pts:
        return None
    return Task(
        task_type="knowledge", subject=subject, title=f"{lesson.title} 基础知识",
        detail=f"重点巩固 · {len(pts)} 个知识点（新课 {len(new_pts)} + 复习 {len(due_pts)}）",
        content=json.dumps([{"id": p.id, "content": p.content, "category": p.category} for p in pts], ensure_ascii=False),
        points=20,
    )


def _gen_review(db, lesson, user_id, count):
    now = datetime.utcnow()
    weak_ids = [r[0] for r in db.query(WordMastery.word_bank_id).filter(
        WordMastery.user_id == user_id,
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


def _gen_math_practice(db, lesson):
    """数学练习：基于本课正文出计算/应用题，content 存题目 JSON。"""
    from .math_gen import generate_math_questions
    text = db.query(Text).filter_by(lesson_id=lesson.id).first()
    if not text or not text.content.strip():
        return None
    qs = generate_math_questions(db, text.content, n=3)
    if not qs:
        return None
    return Task(
        task_type="math", subject=lesson.subject, title=f"{lesson.title} 数学练习",
        detail=f"今日练习 · {len(qs)} 道计算/应用题",
        content=json.dumps(qs, ensure_ascii=False),
        points=20,
        content_status="published",
    )


def generate_tasks_for_user(db: Session, user_id: int, day: date, force: bool = False):
    """为单个孩子生成当天各科任务。幂等：同 (user_id, subject, date) 已存在则跳过。
    force=True 时先删除该孩子当天全部任务再重新生成（家长手动触发覆盖重生成）。"""
    if force:
        db.query(Task).filter_by(user_id=user_id, date=day).delete(synchronize_session=False)
    subjects = ["语文", "英语", "数学"]
    for subject in subjects:
        exists = db.query(Task).filter_by(user_id=user_id, subject=subject, date=day).first()
        if exists:
            continue
        lesson = _current_lesson(db, subject, user_id)
        if not lesson:
            continue
        n_dict = _default_count(db, f"task_dictation_count_{subject}", 7)
        n_know = _default_count(db, "task_knowledge_count", 5)
        new_ratio = _default_count(db, "task_new_ratio", 5)
        gens = [_gen_dictation(db, lesson, user_id, n_dict, new_ratio),
                _gen_knowledge(db, lesson, user_id, n_know, new_ratio),
                _gen_review(db, lesson, user_id, n_dict)]
        if subject == "英语":
            gens.append(_gen_listening(db, lesson))
        if subject == "数学":
            gens.append(_gen_math_practice(db, lesson))
        for gen in gens:
            if gen is not None:
                gen.user_id = user_id
                gen.date = day
                db.add(gen)
    db.commit()


def generate_daily_tasks(db: Session, day: date, force: bool = False):
    """定时任务入口：为所有孩子生成当天任务。force=True 时覆盖重生成。"""
    for (uid,) in db.query(User.id).filter_by(role="child").all():
        generate_tasks_for_user(db, uid, day, force=force)
