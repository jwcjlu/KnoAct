"""今日任务生成：对每个孩子、每科，按当前课生成听写/基础练习/复习任务。"""
import json
from datetime import date, datetime

from sqlalchemy.orm import Session

from ..models import (
    User, Lesson, LearningProgress, WordBank, KnowledgePoint, WordMastery, KnowledgeMastery,
    Task, Text, UserDocument, Question, QuestionBank,
)


def _current_lesson(db: Session, subject: str, user_id: int):
    """按科返回当前课：只在孩子绑定的教材里选；LearningProgress 匹配 (user_id, subject)
    则用它（须在绑定范围内），否则回退绑定教材该科第一课。未绑定任何教材则返回 None。"""
    bound_doc_ids = [r[0] for r in db.query(UserDocument.document_id).filter_by(user_id=user_id).all()]
    if not bound_doc_ids:
        return None
    prog = db.query(LearningProgress).filter_by(user_id=user_id, subject=subject).first()
    lessons = (db.query(Lesson)
               .filter(Lesson.subject == subject, Lesson.document_id.in_(bound_doc_ids))
               .order_by(Lesson.id).all())
    if not lessons:
        return None
    if prog and prog.current_lesson_id:
        for l in lessons:
            if l.id == prog.current_lesson_id:
                return l
    return lessons[0]


def _default_count(db: Session, key: str, fallback: int, child_id=None) -> int:
    from .child_config import get_child_config_int
    return get_child_config_int(db, child_id, key, fallback)


def _gen_dictation(db, lesson, user_id, count, due_cap=0.5, new_floor=0.3):
    """按「已学课范围 + 无限循环」出听写：
    - 候选池：绑定教材下、audit_status=approved、subject 匹配、且 id <= 当前课(lesson.id)
      的全部 WordBank（未学课不进池，已学课永不踢出）。
    - 四档优先级：到期词 -> 错词 -> 新词 -> 轮转补位。
      - 到期词（next_review_at<=now）+ 错词（mistake_count>0 未到期）合计受 due_n 上限。
      - 新词（无 WordMastery 或 attempts 为空）受 new_n 下限保障。
      - 轮转词（已考过、没错、未到期，含已掌握）按「最久没考」补满 count。
    - 所有词永不移出（B2）；已掌握的词靠轮转档回来。
    """
    import math
    subject = lesson.subject
    now = datetime.utcnow()

    bound_doc_ids = [r[0] for r in db.query(UserDocument.document_id).filter_by(user_id=user_id).all()]
    lesson_ids = [r[0] for r in db.query(Lesson.id).filter(
        Lesson.subject == subject,
        Lesson.document_id.in_(bound_doc_ids),
        Lesson.audit_status == "approved",
        Lesson.id <= lesson.id).all()]
    if not lesson_ids:
        return None

    words = (db.query(WordBank)
             .filter(WordBank.lesson_id.in_(lesson_ids))
             .order_by(WordBank.id).all())
    if not words:
        return None

    mrows = {m.word_bank_id: m for m in db.query(WordMastery).filter(
        WordMastery.user_id == user_id,
        WordMastery.word_bank_id.in_([w.id for w in words])).all()}

    def _m(wb):
        return mrows.get(wb.id)

    def _is_new(wb):
        m = _m(wb)
        if m is None:
            return True
        try:
            return not json.loads(m.attempts or "[]")
        except (ValueError, TypeError):
            return True

    def _is_due(wb):
        m = _m(wb)
        return bool(m and m.next_review_at and m.next_review_at <= now)

    def _is_mistaken(wb):
        m = _m(wb)
        return bool(m and (m.mistake_count or 0) > 0 and not _is_due(wb))

    due_n = int(math.ceil(count * due_cap))
    new_n = max(1, int(math.floor(count * new_floor)))

    due_words = sorted((w for w in words if _is_due(w)),
                       key=lambda w: _m(w).next_review_at)[:due_n]
    picked = list(due_words)
    if len(picked) < due_n:
        mistaken = sorted((w for w in words if _is_mistaken(w)),
                          key=lambda w: -(_m(w).mistake_count or 0))
        picked += mistaken[:due_n - len(picked)]

    picked_ids = {w.id for w in picked}

    new_words = [w for w in words if _is_new(w) and w.id not in picked_ids][:new_n]
    picked += new_words
    picked_ids = {w.id for w in picked}

    if len(picked) < count:
        def _last_review(w):
            m = _m(w)
            return m.next_review_at or now
        rotation = sorted((w for w in words
                           if w.id not in picked_ids
                           and not _is_new(w)
                           and not _is_due(w)
                           and not _is_mistaken(w)),
                          key=_last_review)
        picked += rotation[:count - len(picked)]

    picked = picked[:count]
    if not picked:
        return None
    n_review = len([w for w in picked if _is_due(w) or _is_mistaken(w)])
    n_new = len([w for w in picked if _is_new(w) and not _is_due(w) and not _is_mistaken(w)])
    n_rot = len(picked) - n_review - n_new
    return Task(
        task_type="dictation", subject=subject, title=f"{lesson.title} 生词听写",
        detail=f"今日听写 · {len(picked)} 个（复习 {n_review} + 新课 {n_new} + 轮转 {n_rot}）",
        content=json.dumps([{"id": w.id, "word": w.word, "extra": w.extra} for w in picked], ensure_ascii=False),
        points=20,
    )


def _gen_knowledge(db, lesson, user_id, count, new_ratio=5, bucket_id=None):
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
    from .knowledge_quiz import generate_knowledge_questions
    from ..models import Question
    raw = [{"id": p.id, "content": p.content, "category": p.category} for p in pts]
    qs = generate_knowledge_questions(db, raw, subject)
    for item in qs:
        db.add(Question(
            lesson_id=lesson.id, qtype="knowledge",
            question=item.get("question") or item.get("content") or "",
            answer=item.get("answer") or "",
            subject=subject, date=datetime.utcnow().date(),
            status="pending", task_type="knowledge",
            user_id=user_id, bucket_id=bucket_id,
            extra=json.dumps({"keywords": item.get("keywords") or [], "content": item.get("content") or ""}, ensure_ascii=False),
        ))
    return Task(
        task_type="knowledge", subject=subject, title=f"{lesson.title} 基础知识",
        detail=f"重点巩固 · {len(pts)} 个知识点（新课 {len(new_pts)} + 复习 {len(due_pts)}）",
        content=json.dumps(qs, ensure_ascii=False),
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


def _gen_listening(db, lesson, user_id=None, bucket_id=None):
    words = [w.word for w in db.query(WordBank).filter_by(lesson_id=lesson.id).all()]
    kps = [p.content for p in db.query(KnowledgePoint).filter_by(lesson_id=lesson.id).all()]
    if not words:
        return None
    from ..tools.generation import generate_listening
    from ..core.context import UnifiedContext
    from ..models import Question
    ctx = UnifiedContext(user_id=0, lesson_id=lesson.id, question="")
    result = generate_listening.run({"words": words, "knowledge_points": kps}, ctx)
    questions = result.get("questions") or []
    q0 = questions[0] if questions else {}
    stem = (q0.get("question") or "").strip()
    opts = q0.get("options") or []
    try:
        ci = int(q0.get("correct_index", 0))
    except (TypeError, ValueError):
        ci = 0
    if opts:
        ci = max(0, min(len(opts) - 1, ci))
        answer_text = opts[ci]
    else:
        answer_text = ""
    db.add(Question(
        lesson_id=lesson.id, qtype="listening",
        question=stem,
        answer=answer_text,
        subject=lesson.subject, date=datetime.utcnow().date(),
        status="pending", task_type="listening",
        user_id=user_id, bucket_id=bucket_id,
        extra=json.dumps({"dialogue": result.get("dialogue") or ""}, ensure_ascii=False),
    ))
    return Task(
        task_type="listening", subject=lesson.subject, title="英语听力练习",
        detail=f"基于 {len(words)} 个已学生词",
        content=json.dumps(result, ensure_ascii=False),
        points=15,
        content_status="published",
    )


def _gen_math_practice(db, lesson, user_id=None, bucket_id=None):
    """数学练习：基于本课正文出计算/应用题，content 存 {"calc":[...], "word":[...]}。"""
    from .math_gen import generate_math_questions_split
    from ..models import Question
    text = db.query(Text).filter_by(lesson_id=lesson.id).first()
    if not text or not text.content.strip():
        return None
    n_calc = _default_count(db, "task_math_calc_count", 2, child_id=user_id)
    n_word = _default_count(db, "task_math_word_count", 2, child_id=user_id)
    if n_calc <= 0 and n_word <= 0:
        return None
    split = generate_math_questions_split(db, text.content, n_calc=n_calc, n_word=n_word)
    calc_qs = split.get("calc") or []
    word_qs = split.get("word") or []
    if not calc_qs and not word_qs:
        return None

    def _persist_questions(qs):
        for q in qs:
            db.add(Question(
                lesson_id=lesson.id, qtype="math",
                question=q.get("question") or q.get("q") or "",
                answer=str(q.get("answer") or q.get("ans") or ""),
                subject=lesson.subject, date=datetime.utcnow().date(),
                status="pending", task_type="math",
                user_id=user_id, bucket_id=bucket_id,
                extra=json.dumps({k: q.get(k) for k in q if k not in ("question", "answer", "q", "ans")},
                                 ensure_ascii=False),
            ))

    _persist_questions(calc_qs)
    _persist_questions(word_qs)
    total = len(calc_qs) + len(word_qs)
    return Task(
        task_type="math", subject=lesson.subject, title=f"{lesson.title} 数学练习",
        detail=f"今日练习 · 计算 {len(calc_qs)} 道 + 应用 {len(word_qs)} 道（共 {total} 道）",
        content=json.dumps(split, ensure_ascii=False),
        points=20,
        content_status="published",
    )


def _bank_include_daily(tags_json: str) -> bool:
    try:
        return bool(json.loads(tags_json or "{}").get("include_daily_task"))
    except (ValueError, TypeError):
        return False


def _gen_bank_practice_tasks(db: Session, user_id: int, day: date):
    """从家长勾选「纳入每日任务」的卷子中抽已发布题，生成 task_type=practice。"""
    child = db.get(User, user_id)
    if not child or not child.parent_id:
        return []
    n_pick = _default_count(db, "task_bank_practice_count", 3, child_id=user_id)
    if n_pick <= 0:
        return []
    banks = (
        db.query(QuestionBank)
        .filter_by(user_id=child.parent_id, status="active")
        .order_by(QuestionBank.id)
        .all()
    )
    created: list[Task] = []
    used_subjects: set[str] = set()
    for bank in banks:
        if not _bank_include_daily(bank.tags):
            continue
        subj = (bank.subject or "").strip() or "综合"
        if subj in used_subjects:
            continue
        if db.query(Task).filter_by(user_id=user_id, subject=subj, date=day, task_type="practice").first():
            continue
        pool = (
            db.query(Question)
            .filter_by(bank_id=bank.id, status="published")
            .order_by(Question.id)
            .all()
        )
        if not pool:
            continue
        offset = day.toordinal() % len(pool)
        picked = [pool[(offset + i) % len(pool)] for i in range(min(n_pick, len(pool)))]
        created.append(Task(
            task_type="practice",
            subject=subj,
            title=f"{bank.title} 题库练习",
            detail=f"每日抽练 · {len(picked)} 道题",
            content=json.dumps({
                "bank_id": bank.id,
                "bank_title": bank.title,
                "question_ids": [q.id for q in picked],
            }, ensure_ascii=False),
            points=15,
            content_status="published",
        ))
        used_subjects.add(subj)
    return created


def generate_tasks_for_user(db: Session, user_id: int, day: date, force: bool = False):
    """为单个孩子生成当天各科任务。幂等：同 (user_id, subject, date) 已存在则跳过。
    force=True 时先删除该孩子当天全部任务再重新生成（家长手动触发覆盖重生成）。"""
    from .bucket_service import ensure_bucket
    bucket = ensure_bucket(db, user_id)
    if force:
        db.query(Task).filter_by(user_id=user_id, date=day).delete(synchronize_session=False)
        # 同时删除当天该孩子的生成类题目，避免重复累积
        from ..models import Question
        db.query(Question).filter_by(date=day, user_id=user_id).delete(synchronize_session=False)
    subjects = ["语文", "英语", "数学"]
    for subject in subjects:
        exists = db.query(Task).filter_by(user_id=user_id, subject=subject, date=day).first()
        if exists:
            continue
        lesson = _current_lesson(db, subject, user_id)
        if not lesson:
            continue
        n_dict = _default_count(db, f"task_dictation_count_{subject}", 7, child_id=user_id)
        n_know = _default_count(db, "task_knowledge_count", 5, child_id=user_id)
        from .child_config import get_child_config_float
        due_cap = get_child_config_float(db, user_id, "task_dictation_due_cap", 0.5)
        new_floor = get_child_config_float(db, user_id, "task_dictation_new_floor", 0.3)
        gens = [_gen_dictation(db, lesson, user_id, n_dict, due_cap, new_floor),
                _gen_knowledge(db, lesson, user_id, n_know, 5, bucket.id),
                _gen_review(db, lesson, user_id, n_dict)]
        if subject == "英语":
            gens.append(_gen_listening(db, lesson, user_id, bucket.id))
        if subject == "数学":
            gens.append(_gen_math_practice(db, lesson, user_id, bucket.id))
        for gen in gens:
            if gen is not None:
                gen.user_id = user_id
                gen.date = day
                gen.bucket_id = bucket.id
                db.add(gen)
    for gen in _gen_bank_practice_tasks(db, user_id, day):
        gen.user_id = user_id
        gen.date = day
        gen.bucket_id = bucket.id
        db.add(gen)
    db.commit()


def generate_daily_tasks(db: Session, day: date, force: bool = False):
    """定时任务入口：为所有孩子生成当天任务。force=True 时覆盖重生成。"""
    from .bucket_service import ensure_bucket
    for (uid,) in db.query(User.id).filter_by(role="child", status="active").all():
        ensure_bucket(db, uid)
        generate_tasks_for_user(db, uid, day, force=force)
