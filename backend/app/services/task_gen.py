"""今日任务生成：对每个孩子、每科，按当前课生成听写/基础练习/复习任务。"""
import json
from datetime import date, datetime

from sqlalchemy.orm import Session

from ..models import (
    User, Lesson, LearningProgress, WordBank, KnowledgePoint, WordMastery, KnowledgeMastery,
    Task, Text, UserDocument, Question, QuestionBank,
)


def _content_lesson_ids(db: Session, subject: str, document_ids: list[int], up_to_lesson_id: int) -> list[int]:
    """已学范围内的课。书末「单词列表」、语文识字/写字/词语表汇总课只供查阅，不进听写/知识点池。"""
    from .pdf_split import is_cn_table_title, is_word_list_title
    if not document_ids:
        return []
    rows = db.query(Lesson.id, Lesson.title).filter(
        Lesson.subject == subject,
        Lesson.document_id.in_(document_ids),
        Lesson.audit_status == "approved",
        Lesson.id <= up_to_lesson_id,
    ).all()
    return [
        i for i, title in rows
        if not is_word_list_title(title) and not is_cn_table_title(title)
    ]


def _current_lesson(db: Session, subject: str, user_id: int):
    """按科返回当前课：只在孩子绑定的教材里选。

    进度按 (user_id, document_id) 存，一个学科可能有多本教材；
    这里优先用「该科有进度的那本」，否则取绑定教材里该科的第一本。
    """
    bound_doc_ids = [r[0] for r in
                     db.query(UserDocument.document_id).filter_by(user_id=user_id).all()]
    if not bound_doc_ids:
        return None

    from .learning_progress import get_progress

    # 优先：绑定教材范围内、有 progress 的那本。
    # 老记录（document_id 为 NULL）也要认：把它当作「该科唯一进度」。
    rows = (db.query(LearningProgress)
            .filter_by(user_id=user_id, subject=subject).all())
    lesson = None
    for row in rows:
        if not row.current_lesson_id:
            continue
        if row.document_id is not None and row.document_id not in bound_doc_ids:
            continue
        cand = db.get(Lesson, row.current_lesson_id)
        if cand is not None and (row.document_id is None
                                 or cand.document_id in bound_doc_ids):
            lesson = cand
            break

    if lesson is None:
        lesson = (db.query(Lesson)
                  .filter(Lesson.subject == subject,
                          Lesson.document_id.in_(bound_doc_ids))
                  .order_by(Lesson.id).first())
    return lesson


def _default_count(db: Session, key: str, fallback: int, child_id=None) -> int:
    from .child_config import get_child_config_int
    return get_child_config_int(db, child_id, key, fallback)


def _gen_dictation(db, lesson, user_id, count, due_cap=0.5, new_floor=0.3):
    """按「已学课范围 + 无限循环」出听写：
    - 候选池：绑定教材下、audit_status=approved、subject 匹配、且 id <= 当前课(lesson.id)
      的全部 WordBank（未学课不进池，已学课永不踢出）。
    - 四档优先级：到期词 -> 错词 -> 新词 -> 轮转补位。
      - 到期词（next_review_at<=now）+ 错词（mistake_count>0 未到期）合计受 due_n 上限。
      - 新词（无 WordMastery 或 attempts 为空）受 new_n **下限**保障，且优先吃满剩余名额。
      - 轮转词（已考过、没错、未到期，含已掌握）在新词用尽后才补位。
    - 所有词永不移出（B2）；已掌握的词靠轮转档回来。
    """
    import math
    subject = lesson.subject
    now = datetime.utcnow()

    bound_doc_ids = [r[0] for r in db.query(UserDocument.document_id).filter_by(user_id=user_id).all()]
    lesson_ids = _content_lesson_ids(db, subject, bound_doc_ids, lesson.id)
    if not lesson_ids:
        return None

    words = (db.query(WordBank)
             .filter(WordBank.lesson_id.in_(lesson_ids))
             .order_by(WordBank.id).all())
    if subject == "语文":
        from .child_config import get_dictation_kinds_cn
        allowed = set(get_dictation_kinds_cn(db, user_id))
        words = [w for w in words if w.kind in allowed]
    else:
        from .word_kinds import is_en_dictation_kind
        words = [w for w in words if is_en_dictation_kind(w.kind)]
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

    # 新词档：`new_n` 是**下限**（配置项名就叫「新课生词下限比例」），不是上限。
    # 剩余名额优先给新词——学新课才是目标；新词不够了才轮到轮转词。
    # 旧实现写作 `new_words[...][:new_n]`，把下限当上限用：新课当天只出
    # floor(7*0.3)=2 个词，而轮转档又排除新词，剩下的名额就空着（2/7）。
    new_candidates = [w for w in words if _is_new(w) and w.id not in picked_ids]
    take_new = max(new_n, count - len(picked))
    picked += new_candidates[:take_new]
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

    if subject == "语文":
        from .dictation_cue_fill import fill_missing_cues
        from .dictation_speak import (
            build_speak_payload, resolve_cues_for_word, dump_cue, parse_cue,
        )
        fill_missing_cues(db, picked)
        db.flush()
        items = []
        for w in picked:
            cues = resolve_cues_for_word(
                word=w.word, kind=w.kind, extra=w.extra or "",
                cue_raw=getattr(w, "dictation_cue", None) or "",
            )
            if cues.get("compound") or cues.get("gloss_short"):
                existing = parse_cue(getattr(w, "dictation_cue", None) or "")
                if not existing.get("compound") and cues.get("compound"):
                    existing["compound"] = cues["compound"]
                    existing["source"] = cues.get("source") or "extra"
                if not existing.get("gloss_short") and cues.get("gloss_short"):
                    existing["gloss_short"] = cues["gloss_short"]
                    existing["source"] = existing.get("source") or cues.get("source") or "extra"
                w.dictation_cue = dump_cue(existing)
            payload = build_speak_payload(
                word=w.word, kind=w.kind,
                compound=cues.get("compound") or None,
                gloss_short=cues.get("gloss_short") or None,
            )
            items.append({
                "id": w.id, "word": w.word, "extra": w.extra, "kind": w.kind,
                **payload,
            })
    else:
        items = [
            {"id": w.id, "word": w.word, "extra": w.extra, "kind": w.kind}
            for w in picked
        ]

    return Task(
        task_type="dictation", subject=subject, title=f"{lesson.title} 生词听写",
        detail=f"今日听写 · {len(picked)} 个（复习 {n_review} + 新课 {n_new} + 轮转 {n_rot}）",
        content=json.dumps(items, ensure_ascii=False),
        points=20,
    )


def _gen_knowledge(db, lesson, user_id, count, bucket_id=None):
    """按「已学课范围 + 无限循环」取知识点：
    - 候选池：绑定教材下、approved、subject 匹配、id <= 当前课的全部知识点。
    - 四档优先级：到期 -> 错 -> 新 -> 轮转。
      - 到期（next_review_at<=now）+ 错（最近一次答错、未到期）合计受 ceil(count/2) 上限。
      - 新（无 KnowledgeMastery 或 attempts 空）至少 1 个。
      - 轮转（其余，含 mastered）按最久没考补满 count。
    - 已掌握永不移出（B2 无限循环）。
    """
    import math
    subject = lesson.subject
    now = datetime.utcnow()

    bound_doc_ids = [r[0] for r in db.query(UserDocument.document_id).filter_by(user_id=user_id).all()]
    lesson_ids = _content_lesson_ids(db, subject, bound_doc_ids, lesson.id)
    if not lesson_ids:
        return None

    points = (db.query(KnowledgePoint)
              .filter(KnowledgePoint.lesson_id.in_(lesson_ids))
              .order_by(KnowledgePoint.id).all())
    if not points:
        return None

    mrows = {m.knowledge_point_id: m for m in db.query(KnowledgeMastery).filter(
        KnowledgeMastery.user_id == user_id,
        KnowledgeMastery.knowledge_point_id.in_([p.id for p in points])).all()}

    def _m(p):
        return mrows.get(p.id)

    def _attempts(p):
        m = _m(p)
        if m is None:
            return []
        try:
            a = json.loads(m.attempts or "[]")
            return a if isinstance(a, list) else []
        except (ValueError, TypeError):
            return []

    def _is_new(p):
        return not _attempts(p)

    def _is_due(p):
        m = _m(p)
        return bool(m and m.next_review_at and m.next_review_at <= now)

    def _is_mistaken(p):
        a = _attempts(p)
        # `a[-1] is False` 依赖 attempts 只存 Python bool（见 mastery._append 的 bool(is_correct) 写入）。
        # 若未来改用 0/1 或其他序列化，须同步改这里的身份判断。
        return bool(a and a[-1] is False and not _is_due(p))

    review_n = int(math.ceil(count / 2))
    # new_n 的 max(1, ...) 仅用于 count=1 时保证至少留 1 个新知识点名额（否则全被到期档占满）；
    # count>=2 时 review_n + new_n == count。
    new_n = max(1, count - review_n)

    due_pts = sorted((p for p in points if _is_due(p)),
                     key=lambda p: _m(p).next_review_at)[:review_n]
    picked = list(due_pts)
    if len(picked) < review_n:
        mistaken = [p for p in points if _is_mistaken(p) and p.id not in {x.id for x in picked}]
        picked += mistaken[:review_n - len(picked)]

    picked_ids = {p.id for p in picked}
    new_pts = [p for p in points if _is_new(p) and p.id not in picked_ids][:new_n]
    picked += new_pts
    picked_ids = {p.id for p in picked}

    if len(picked) < count:
        def _last_review(p):
            m = _m(p)
            return m.next_review_at or now
        rotation = sorted((p for p in points
                           if p.id not in picked_ids
                           and not _is_new(p)
                           and not _is_due(p)
                           and not _is_mistaken(p)),
                          key=_last_review)
        picked += rotation[:count - len(picked)]

    picked = picked[:count]
    if not picked:
        return None

    from .knowledge_quiz import generate_knowledge_questions
    from ..models import Question
    raw = [{"id": p.id, "content": p.content, "category": p.category} for p in picked]
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
    n_due = len(due_pts)
    n_mist = len([p for p in picked if _is_mistaken(p)])
    n_new = len(new_pts)
    n_rot = len(picked) - n_due - n_mist - n_new
    return Task(
        task_type="knowledge", subject=subject, title=f"{lesson.title} 基础知识",
        detail=f"重点巩固 · {len(picked)} 个知识点（到期 {n_due} + 错 {n_mist} + 新课 {n_new} + 轮转 {n_rot}）",
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
    words = db.query(WordBank).filter(WordBank.id.in_(weak_ids), WordBank.lesson_id == lesson.id).all()
    subject = lesson.subject
    if subject == "语文":
        from .child_config import get_dictation_kinds_cn
        allowed = set(get_dictation_kinds_cn(db, user_id))
        words = [w for w in words if w.kind in allowed]
    else:
        from .word_kinds import is_en_dictation_kind
        words = [w for w in words if is_en_dictation_kind(w.kind)]
    words = words[:count]
    if not words:
        return None
    return Task(
        task_type="review", subject=lesson.subject, title="到期复习",
        detail=f"遗忘曲线 · {len(words)} 个到期生词",
        content=json.dumps([
            {"id": w.id, "word": w.word, "extra": w.extra, "kind": w.kind}
            for w in words
        ], ensure_ascii=False),
        points=25,
    )


def _gen_kp_review(db, user_id, subject, day, bucket_id):
    """知识点遗忘曲线复习任务（快照到期 KnowledgeReviewItem）。幂等：当天已有则跳过。"""
    from .knowledge_review import select_due_items, serialize_due_item
    exists = db.query(Task).filter_by(
        user_id=user_id, subject=subject, date=day, task_type="kp_review").first()
    if exists:
        return None
    items = select_due_items(db, user_id, subject=subject)
    if not items:
        return None
    payload = [serialize_due_item(db, user_id, it) for it in items]
    return Task(
        task_type="kp_review", subject=subject, title="知识点复习",
        detail=f"遗忘曲线 · {len(payload)} 个到期知识点",
        content=json.dumps(payload, ensure_ascii=False),
        points=25, content_status="published", submit_status="not_started",
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
    """从家长勾选「纳入每日任务」的卷子中抽已发布题，生成 task_type=practice。

    练习册（source=practice_pdf）按「课时」逐日推进：优先练家长设定的当前课时，
    练完就往后走。普通题库卷仍按原来的整卷轮转。

    **一个科目只有一个练习任务**（数据库有唯一约束 `uq_task_user_subject_date_type`），
    但该任务可以**合并多个卷**的题：家长导入新练习册后，旧卷不会再把新卷挤掉。
    每个卷抽 `task_bank_practice_count` 道，最多合并 `task_bank_practice_volumes`
    个卷（默认 2），总量封顶 `task_bank_practice_total_cap`（默认 12）。
    """
    child = db.get(User, user_id)
    if not child or not child.parent_id:
        return []
    n_pick = _default_count(db, "task_bank_practice_count", 3, child_id=user_id)
    if n_pick <= 0:
        return []
    max_volumes = _default_count(
        db, "task_bank_practice_volumes", 2, child_id=user_id)
    if max_volumes <= 0:
        max_volumes = 1
    total_cap = _default_count(
        db, "task_bank_practice_total_cap", 12, child_id=user_id)
    banks = (
        db.query(QuestionBank)
        .filter_by(user_id=child.parent_id, status="active")
        .order_by(QuestionBank.id)
        .all()
    )

    # 每个科目收集最多 max_volumes 个卷的题，合成一个任务
    merged: dict[str, dict] = {}
    for bank in banks:
        if not _bank_include_daily(bank.tags):
            continue
        subj = (bank.subject or "").strip() or "综合"
        entry = merged.setdefault(subj, {"banks": [], "items": [], "titles": []})
        if len(entry["banks"]) >= max_volumes:
            continue
        if len(entry["items"]) >= total_cap:
            continue

        room = min(n_pick, total_cap - len(entry["items"]))
        if room <= 0:
            continue
        picked, lesson_no, lesson_title = _pick_practice_questions(
            db, bank, user_id, day, room)
        if not picked:
            continue

        entry["banks"].append(bank.id)
        entry["titles"].append(bank.title)
        for q in picked:
            entry["items"].append({
                "id": q.id,
                "bank_id": bank.id,
                "bank_title": bank.title,
                "lesson_no": lesson_no,
                "lesson_title": lesson_title,
            })

    created: list[Task] = []
    for subj, entry in merged.items():
        if not entry["items"]:
            continue
        # 幂等：该科目今天已有练习任务就跳过
        if db.query(Task).filter_by(
                user_id=user_id, subject=subj, date=day,
                task_type="practice").first():
            continue

        titles = entry["titles"]
        title = (f"{titles[0]} 题库练习" if len(titles) == 1
                 else f"{titles[0]} 等 {len(titles)} 套卷 题库练习")
        detail = f"每日抽练 · {len(titles)} 套卷 · {len(entry['items'])} 道题"
        content = {
            "bank_id": entry["banks"][0],
            "bank_title": titles[0],
            "question_ids": [it["id"] for it in entry["items"]],
            "lesson_no": entry["items"][0]["lesson_no"],
            "lesson_title": entry["items"][0]["lesson_title"],
            "groups": _group_context(
                db, [it["id"] for it in entry["items"]]),
            # 多卷信息：前端按题 id 归到对应卷
            "banks": [
                {"bank_id": bid, "bank_title": t}
                for bid, t in zip(entry["banks"], titles)
            ],
            "items": entry["items"],
        }
        created.append(Task(
            task_type="practice",
            subject=subj,
            title=title,
            detail=detail,
            content=json.dumps(content, ensure_ascii=False),
            points=15,
            content_status="published",
        ))
    return created


def _pick_practice_questions(db: Session, bank, user_id: int, day: date, n_pick: int):
    """给出当天该抽的题。返回 (questions, lesson_no, lesson_title)。

    练习册卷：按课时推进（当前课时 → 练完顺延）。普通卷：整卷轮转。
    """
    from ..models import ChildConfig

    base = (
        db.query(Question)
        .filter_by(bank_id=bank.id, status="published")
        .filter(Question.is_example.is_(False))   # 示例行不是待做题
        .order_by(Question.lesson_no, Question.id)
    )
    # photo 类题（竖式/脱式/应用/图形）需拍照作答，拍照链路未实现，本期不布置，
    # 否则孩子答了没有任何反馈。answer_kind 由 work_mode 查表得来，不能写进 SQL。
    from ..core.work_modes import answer_kind_of

    all_q = [q for q in base.all()
             if answer_kind_of(q.work_mode) != "photo"]
    if not all_q:
        return [], None, ""

    source = getattr(bank, "source", "") or ""
    if source != "practice_pdf":
        offset = day.toordinal() % len(all_q)
        return [all_q[(offset + i) % len(all_q)] for i in range(min(n_pick, len(all_q)))], None, ""

    # 练习册：按课时推进
    lessons = sorted({q.lesson_no for q in all_q if q.lesson_no is not None})
    if not lessons:
        offset = day.toordinal() % len(all_q)
        return [all_q[(offset + i) % len(all_q)] for i in range(min(n_pick, len(all_q)))], None, ""

    cur = (
        db.query(ChildConfig)
        .filter_by(user_id=user_id, key="practice_current_lesson")
        .first()
    )
    try:
        no = int(cur.value) if cur and cur.value else lessons[0]
    except (TypeError, ValueError):
        no = lessons[0]

    # 指定的课时不在本卷里 → 取最近的
    if no not in lessons:
        no = min(lessons, key=lambda x: abs(x - no))

    pool = [q for q in all_q if q.lesson_no == no]
    # 该课时已练完（当天已有该课时任务）→ 顺延到下一课时
    taken = db.query(Task).filter_by(user_id=user_id, date=day, task_type="practice").first()
    if taken is not None and len(pool) <= n_pick:
        idx = lessons.index(no)
        if idx + 1 < len(lessons):
            no = lessons[idx + 1]
            pool = [q for q in all_q if q.lesson_no == no]

    title = (pool[0].lesson_title or "") if pool else ""
    offset = day.toordinal() % len(pool) if pool else 0
    picked = [pool[(offset + i) % len(pool)] for i in range(min(n_pick, len(pool)))] if pool else []
    return picked, no, title


def _group_context(db: Session, question_ids: list[int]) -> list[dict]:
    """给抽中的小题带上所属题组题干与示例行，便于孩子理解引导语。"""
    from ..models import PracticeQuestionGroup, Question

    if not question_ids:
        return []
    qs = db.query(Question).filter(Question.id.in_(question_ids)).all()
    gids = {q.group_id for q in qs if q.group_id}
    if not gids:
        return []
    groups = {g.id: g for g in db.query(PracticeQuestionGroup)
              .filter(PracticeQuestionGroup.id.in_(gids)).all()}
    examples: dict[int, list[dict]] = {}
    for ex in (db.query(Question)
               .filter(Question.group_id.in_(gids),
                       Question.is_example.is_(True))
               .order_by(Question.seq_in_group).all()):
        examples.setdefault(ex.group_id, []).append(
            {"question": ex.question, "answer": ex.answer})
    out = []
    for gid in sorted(gids):
        g = groups.get(gid)
        if g is None:
            continue
        out.append({
            "group_id": g.id,
            "stem": g.stem,
            "instruction": g.instruction,
            "work_mode": g.work_mode,
            "examples": examples.get(gid, []),
        })
    return out


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
        # kp_review 独立于常规任务：已有听写等任务时仍要尝试补生成
        kp_gen = _gen_kp_review(db, user_id, subject, day, bucket.id)
        if kp_gen is not None:
            kp_gen.user_id = user_id
            kp_gen.date = day
            kp_gen.bucket_id = bucket.id
            db.add(kp_gen)
            db.flush()
        exists = (
            db.query(Task)
            .filter(Task.user_id == user_id, Task.subject == subject, Task.date == day,
                    Task.task_type != "kp_review")
            .first()
        )
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
                _gen_knowledge(db, lesson, user_id, n_know, bucket.id),
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
