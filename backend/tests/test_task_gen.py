import json
from datetime import datetime, date, timedelta
from app.database import SessionLocal, Base, engine
from app.models import (
    User, PdfDocument, Lesson, WordBank, KnowledgePoint, WordMastery, Text, Task, Question,
    UserDocument, ChildConfig, QuestionBank, KnowledgeMastery, LearningProgress,
)
from app.services.task_gen import generate_tasks_for_user, _current_lesson


def _setup(db):
    db.query(WordMastery).delete()
    db.query(WordBank).delete()
    db.query(KnowledgePoint).delete()
    db.query(Text).delete()
    db.query(Lesson).delete()
    db.query(PdfDocument).delete()
    db.query(Task).delete()
    db.query(User).delete()
    db.query(UserDocument).delete()
    db.commit()
    u = User(name="测试孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l1 = Lesson(document_id=doc.id, subject="语文", title="第1课", start_page=1, end_page=2,
                extract_status="done", audit_status="approved")
    db.add(l1); db.flush()
    for w in ["白鹭", "矗立"]:
        db.add(WordBank(lesson_id=l1.id, subject="语文", word=w, extra="pinyin 释义"))
    db.add(KnowledgePoint(subject="语文", category="字词", content="形近字辨析", lesson_id=l1.id))
    db.add(Text(lesson_id=l1.id, content="白鹭是一首精巧的诗。"))
    db.add(UserDocument(user_id=u.id, document_id=doc.id))  # 孩子绑定该教材
    db.commit()
    return u.id, l1.id


def _add_words(db, lesson, words):
    for w in words:
        db.add(WordBank(lesson_id=lesson.id, subject=lesson.subject, word=w, extra=""))
    db.flush()


def test_current_lesson_matches_subject():
    db = SessionLocal()
    uid, l1 = _setup(db)
    lesson = _current_lesson(db, "语文", uid)
    assert lesson is not None and lesson.subject == "语文"
    db.close()


def test_generate_tasks_creates_dictation_and_knowledge_and_is_idempotent():
    db = SessionLocal()
    uid, l1 = _setup(db)
    generate_tasks_for_user(db, uid, date.today())
    rows = db.query(Task).filter_by(user_id=uid, date=date.today()).all()
    types = {r.task_type for r in rows}
    assert "dictation" in types
    assert "knowledge" in types

    before = db.query(Task).filter_by(user_id=uid, date=date.today()).count()
    generate_tasks_for_user(db, uid, date.today())  # 第二次调用应幂等，不新增行
    after = db.query(Task).filter_by(user_id=uid, date=date.today()).count()
    assert after == before
    db.close()


def test_generate_tasks_creates_review_when_word_is_due():
    db = SessionLocal()
    uid, l1_id = _setup(db)
    # 挑一个本课生词，造一条到期待复习记录
    wb = db.query(WordBank).filter_by(lesson_id=l1_id).first()
    db.add(WordMastery(word_bank_id=wb.id, is_weak=True,
                       next_review_at=datetime.utcnow() - timedelta(days=1), user_id=uid))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    types = {r.task_type for r in db.query(Task).filter_by(user_id=uid, date=date.today()).all()}
    assert "review" in types
    db.close()


def _setup_english(db):
    db.query(WordMastery).delete()
    db.query(WordBank).delete()
    db.query(KnowledgePoint).delete()
    db.query(Text).delete()
    db.query(Lesson).delete()
    db.query(PdfDocument).delete()
    db.query(Task).delete()
    db.query(User).delete()
    db.query(UserDocument).delete()
    db.commit()
    u = User(name="测试孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="英语.pdf", subject="英语", storage_path="")
    db.add(doc); db.flush()
    l1 = Lesson(document_id=doc.id, subject="英语", title="Unit 1", start_page=1, end_page=2,
                extract_status="done", audit_status="approved")
    db.add(l1); db.flush()
    for w in ["apple", "banana"]:
        db.add(WordBank(lesson_id=l1.id, subject="英语", word=w, extra="释义"))
    db.add(KnowledgePoint(subject="英语", category="词汇", content="颜色词", lesson_id=l1.id))
    db.add(UserDocument(user_id=u.id, document_id=doc.id))
    db.commit()
    return u.id, l1.id


def test_generate_tasks_creates_listening_for_english():
    db = SessionLocal()
    uid, l1 = _setup_english(db)
    generate_tasks_for_user(db, uid, date.today())
    listening = db.query(Task).filter_by(
        user_id=uid, subject="英语", date=date.today(), task_type="listening").all()
    assert len(listening) == 1
    content = json.loads(listening[0].content)
    assert "dialogue" in content
    assert "questions" in content and len(content["questions"]) >= 3
    qrow = db.query(Question).filter_by(
        user_id=uid, subject="英语", date=date.today(), task_type="listening",
    ).first()
    assert qrow is not None
    assert qrow.question == content["questions"][0]["question"]
    db.close()


def test_generate_tasks_no_lesson_produces_no_tasks():
    db = SessionLocal()
    u = User(name="无课孩子", role="child")
    db.add(u); db.flush()
    uid = u.id
    db.commit()

    generate_tasks_for_user(db, uid, date.today())  # 两科均无课，不应抛异常
    assert db.query(Task).filter_by(user_id=uid, date=date.today()).count() == 0
    db.close()


def test_unbound_document_produces_no_tasks():
    """有教材但未绑定给该孩子 → 该科选不到课 → 不生成任务。"""
    db = SessionLocal()
    db.query(WordMastery).delete()
    db.query(WordBank).delete()
    db.query(KnowledgePoint).delete()
    db.query(Text).delete()
    db.query(Lesson).delete()
    db.query(PdfDocument).delete()
    db.query(Task).delete()
    db.query(User).delete()
    db.query(UserDocument).delete()
    db.commit()
    u = User(name="未绑定孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l1 = Lesson(document_id=doc.id, subject="语文", title="第1课", start_page=1, end_page=1,
                extract_status="done", audit_status="approved")
    db.add(l1); db.flush()
    for w in ["白鹭", "矗立"]:
        db.add(WordBank(lesson_id=l1.id, subject="语文", word=w, extra="pinyin 释义"))
    db.add(KnowledgePoint(subject="语文", category="字词", content="形近字辨析", lesson_id=l1.id))
    db.add(Text(lesson_id=l1.id, content="白鹭是一首精巧的诗。"))
    db.commit()
    uid = u.id

    generate_tasks_for_user(db, uid, date.today())
    assert db.query(Task).filter_by(user_id=uid, date=date.today()).count() == 0
    # 绑定后即可生成
    db.add(UserDocument(user_id=uid, document_id=doc.id))
    db.commit()
    generate_tasks_for_user(db, uid, date.today())
    assert db.query(Task).filter_by(user_id=uid, date=date.today()).count() > 0
    db.close()


def test_gen_knowledge_content_has_question_fields():
    db = SessionLocal()
    uid, l1_id = _setup(db)
    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="knowledge").first()
    assert t is not None
    content = json.loads(t.content)
    assert len(content) >= 1
    p = content[0]
    # fake provider 下 question 为空字符串，但字段必须存在
    assert "question" in p and "answer" in p and "keywords" in p
    assert "id" in p and "content" in p
    db.close()


def test_dictation_picks_new_and_due_words():
    """当前课内：新词与到期词都进；到期词不足不硬补。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 第1课：白鹭、矗立 两个生词（当前课）
    wb_ba = db.query(WordBank).filter_by(lesson_id=l1_id, word="白鹭").first()
    db.add(WordMastery(word_bank_id=wb_ba.id, is_weak=True,
                       next_review_at=datetime.utcnow() - timedelta(days=1),
                       user_id=uid, mastery=0.1, attempts=json.dumps([False]),
                       mistake_count=1))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    assert t is not None
    words = json.loads(t.content)
    got = {w["word"] for w in words}
    assert {"白鹭", "矗立"} <= got
    assert len(words) == 2
    assert "复习 1" in t.detail and "新课 1" in t.detail
    db.close()


def test_generated_questions_land_in_question_table():
    db = SessionLocal()
    db.query(Question).delete()
    db.commit()
    uid, l1_id = _setup(db)  # 语文第1课含知识点
    generate_tasks_for_user(db, uid, date.today())
    qs = db.query(Question).filter_by(task_type="knowledge", date=date.today(), status="pending").all()
    assert len(qs) >= 1
    assert qs[0].subject == "语文"
    db.close()


def test_generate_tasks_attaches_bucket():
    from app.services.bucket_service import ensure_bucket
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 语文第1课含生词/知识点
    bucket = ensure_bucket(db, uid)
    generate_tasks_for_user(db, uid, date.today())
    tasks = db.query(Task).filter_by(user_id=uid).all()
    assert len(tasks) >= 1
    for t in tasks:
        assert t.bucket_id == bucket.id
    db.close()


def test_generated_questions_attach_bucket_and_user():
    from app.services.bucket_service import ensure_bucket
    db = SessionLocal()
    db.query(Question).delete()
    db.commit()
    uid, l1_id = _setup(db)  # 语文第1课含知识点
    bucket = ensure_bucket(db, uid)
    generate_tasks_for_user(db, uid, date.today())
    qs = db.query(Question).filter_by(task_type="knowledge", date=date.today()).all()
    assert len(qs) >= 1
    for q in qs:
        assert q.bucket_id == bucket.id
        assert q.user_id == uid
    db.close()


def _setup_math(db):
    """数学教材 + 课文正文，孩子已绑定。"""
    db.query(WordMastery).delete()
    db.query(WordBank).delete()
    db.query(KnowledgePoint).delete()
    db.query(Text).delete()
    db.query(Lesson).delete()
    db.query(PdfDocument).delete()
    db.query(Task).delete()
    db.query(User).delete()
    db.query(UserDocument).delete()
    db.query(ChildConfig).delete()
    db.commit()
    u = User(name="数学测试孩子", role="child")
    db.add(u)
    db.flush()
    doc = PdfDocument(filename="数学.pdf", subject="数学", storage_path="")
    db.add(doc)
    db.flush()
    l1 = Lesson(document_id=doc.id, subject="数学", title="第1单元", start_page=1, end_page=2,
                extract_status="done", audit_status="approved")
    db.add(l1)
    db.flush()
    db.add(Text(lesson_id=l1.id, content="认识加法：3+5=8，凑十法与简单应用。"))
    db.add(UserDocument(user_id=u.id, document_id=doc.id))
    db.commit()
    return u.id, l1.id


def test_generate_tasks_math_respects_calc_and_word_counts():
    db = SessionLocal()
    uid, _ = _setup_math(db)
    db.add(ChildConfig(user_id=uid, key="task_math_calc_count", value="2"))
    db.add(ChildConfig(user_id=uid, key="task_math_word_count", value="1"))
    db.commit()
    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(
        user_id=uid, subject="数学", date=date.today(), task_type="math",
    ).first()
    assert t is not None
    content = json.loads(t.content)
    assert isinstance(content, dict)
    assert len(content.get("calc") or []) == 2
    assert len(content.get("word") or []) == 1
    assert "计算 2 道" in t.detail and "应用 1 道" in t.detail
    db.close()


def test_dictation_isolates_due_words_across_users():
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 孩子A：第1课（白鹭、矗立）
    # 孩子B：一个第2课生词，带一条到期 WordMastery（属于B）
    other = User(name="别的孩子", role="child")
    db.add(other); db.flush()
    doc = db.query(PdfDocument).first()
    l2 = Lesson(document_id=doc.id, subject="语文", title="第2课", start_page=3, end_page=4,
                extract_status="done", audit_status="approved")
    db.add(l2); db.flush()
    wb_b = WordBank(lesson_id=l2.id, subject="语文", word="B的旧词", extra="")
    db.add(wb_b); db.flush()
    db.add(WordMastery(word_bank_id=wb_b.id, is_weak=True,
                       next_review_at=datetime.utcnow() - timedelta(days=1), user_id=other.id))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    assert t is not None
    got = {w["word"] for w in json.loads(t.content)}
    # A 的听写只含本课新词，绝不能混入 B 的到期旧词
    assert got == {"白鹭", "矗立"}
    db.close()


def test_generate_bank_practice_when_flagged():
    db = SessionLocal()
    parent = User(name="家长", role="parent")
    db.add(parent); db.flush()
    uid, _l1 = _setup(db)
    db.query(User).filter_by(id=uid).update({"parent_id": parent.id})
    bank = QuestionBank(
        user_id=parent.id, title="每日卷", subject="语文",
        tags=json.dumps({"include_daily_task": True}, ensure_ascii=False),
    )
    db.add(bank); db.flush()
    db.add(Question(
        bank_id=bank.id, qtype="single_choice", qtype_category="choice",
        question="测试题", status="published", answer_json='{"correct_index":0}',
    ))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(
        user_id=uid, date=date.today(), task_type="practice", subject="语文",
    ).first()
    assert t is not None
    payload = json.loads(t.content)
    assert payload["bank_id"] == bank.id
    assert len(payload["question_ids"]) == 1
    db.close()


def test_dictation_due_cap_and_new_floor():
    """到期词受上限约束；未学课（id>当前课）不进池；不硬补。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 第1课：白鹭、矗立（当前课）
    doc = db.query(PdfDocument).first()
    l2 = Lesson(document_id=doc.id, subject="语文", title="第2课",
                start_page=3, end_page=4, extract_status="done", audit_status="approved")
    db.add(l2); db.flush()
    _add_words(db, l2, ["未学课词"])
    db.commit()

    for wb in db.query(WordBank).filter_by(lesson_id=l1_id).all():
        db.add(WordMastery(word_bank_id=wb.id, is_weak=True,
                           next_review_at=datetime.utcnow() - timedelta(days=1),
                           user_id=uid, mastery=0.1, attempts=json.dumps([False]),
                           mistake_count=1))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    words = json.loads(t.content)
    got = {w["word"] for w in words}
    assert "未学课词" not in got
    assert {"白鹭", "矗立"} <= got
    assert len(words) == 2
    db.close()


def test_dictation_rotation_includes_mastered_words():
    """B2 无限循环：已掌握的词不移出，在轮转档回来。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)
    wb_ba = db.query(WordBank).filter_by(lesson_id=l1_id, word="白鹭").first()
    db.add(WordMastery(word_bank_id=wb_ba.id, is_weak=False,
                       next_review_at=datetime.utcnow() + timedelta(days=30),
                       user_id=uid, mastery=0.95,
                       attempts=json.dumps([True, True, True]),
                       mistake_count=0))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    assert t is not None
    got = {w["word"] for w in json.loads(t.content)}
    assert "白鹭" in got
    assert "矗立" in got
    db.close()


def test_dictation_fills_with_rotation_words():
    """到期+新词不足 count 时，用轮转词补满。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 白鹭、矗立 两个新词
    _add_words(db, db.query(Lesson).filter_by(id=l1_id).first(),
               ["轮转1", "轮转2", "轮转3", "轮转4", "轮转5"])
    for wb in db.query(WordBank).filter_by(lesson_id=l1_id).all():
        if wb.word in ("白鹭", "矗立"):
            continue
        db.add(WordMastery(word_bank_id=wb.id, is_weak=False,
                           next_review_at=datetime.utcnow() + timedelta(days=3),
                           user_id=uid, mastery=0.4, attempts=json.dumps([True]),
                           mistake_count=0))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    words = json.loads(t.content)
    assert len(words) == 7
    db.close()


def test_dictation_mistaken_words_fill_review_bucket():
    """错词（未到期，mistake_count>0）落入复习档，且与到期词共用 due_n 上限。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 白鹭、矗立
    # 白鹭：到期；矗立：错词但未到期
    wb_ba = db.query(WordBank).filter_by(lesson_id=l1_id, word="白鹭").first()
    wb_ch = db.query(WordBank).filter_by(lesson_id=l1_id, word="矗立").first()
    db.add(WordMastery(word_bank_id=wb_ba.id, is_weak=True,
                       next_review_at=datetime.utcnow() - timedelta(days=1),
                       user_id=uid, mastery=0.1, attempts=json.dumps([False]),
                       mistake_count=2))
    db.add(WordMastery(word_bank_id=wb_ch.id, is_weak=True,
                       next_review_at=datetime.utcnow() + timedelta(days=2),
                       user_id=uid, mastery=0.3, attempts=json.dumps([False]),
                       mistake_count=3))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    assert t is not None
    # 白鹭(到期) 与 矗立(错词) 都进复习档
    got = {w["word"] for w in json.loads(t.content)}
    assert {"白鹭", "矗立"} <= got
    # 复习档计数 = 2（1 到期 + 1 错词）
    assert "复习 2" in t.detail
    db.close()


def test_dictation_due_cap_truncates_excess_due_words():
    """到期词超过 due_n 上限时被截断，且总数不超过 count。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 白鹭、矗立（当前课）
    # 追加 5 个到期词，使到期词总数 7 > due_n(=ceil(7*0.5)=4)
    _add_words(db, db.query(Lesson).filter_by(id=l1_id).first(),
               ["到期1", "到期2", "到期3", "到期4", "到期5"])
    for wb in db.query(WordBank).filter_by(lesson_id=l1_id).all():
        db.add(WordMastery(word_bank_id=wb.id, is_weak=True,
                           next_review_at=datetime.utcnow() - timedelta(days=1),
                           user_id=uid, mastery=0.1, attempts=json.dumps([False]),
                           mistake_count=1))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    assert t is not None
    words = json.loads(t.content)
    # 到期词只取 due_n=4 个（截断），不取满 7 个
    assert len(words) == 4
    db.close()


def _add_kps(db, lesson, contents):
    for c in contents:
        db.add(KnowledgePoint(subject=lesson.subject, category="字词", content=c, lesson_id=lesson.id))
    db.flush()


def test_knowledge_learned_lesson_scope():
    """已学课（id<=当前课）的知识点进池；未学课（id>当前课）不进。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 第1课，1 个知识点「形近字辨析」
    doc = db.query(PdfDocument).first()
    # 第2课（已学）含一个到期知识点
    l2 = Lesson(document_id=doc.id, subject="语文", title="第2课",
                start_page=3, end_page=4, extract_status="done", audit_status="approved")
    db.add(l2); db.flush()
    kp2 = KnowledgePoint(subject="语文", category="字词", content="第2课到期点", lesson_id=l2.id)
    db.add(kp2); db.flush()
    db.add(KnowledgeMastery(user_id=uid, knowledge_point_id=kp2.id,
                            attempts=json.dumps([False]), mastery=0.1, mastered=False,
                            next_review_at=datetime.utcnow() - timedelta(days=1)))
    # 第3课（未学）含一个到期知识点
    l3 = Lesson(document_id=doc.id, subject="语文", title="第3课",
                start_page=5, end_page=6, extract_status="done", audit_status="approved")
    db.add(l3); db.flush()
    kp3 = KnowledgePoint(subject="语文", category="字词", content="第3课到期点", lesson_id=l3.id)
    db.add(kp3); db.flush()
    db.add(KnowledgeMastery(user_id=uid, knowledge_point_id=kp3.id,
                            attempts=json.dumps([False]), mastery=0.1, mastered=False,
                            next_review_at=datetime.utcnow() - timedelta(days=1)))
    # 推进进度到第2课
    db.add(LearningProgress(user_id=uid, subject="语文", current_lesson_id=l2.id))
    # 降低 new_ratio，使旧算法「跨课到期」路径生效（count-new_ratio>0），
    # 否则旧算法会因 limit(0) 恰好漏掉第3课到期点，无法区分新旧语义
    db.add(ChildConfig(user_id=uid, key="task_new_ratio", value="1"))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="knowledge").first()
    assert t is not None
    contents = {q.get("content") for q in json.loads(t.content)}
    assert "第2课到期点" in contents   # 已学课（当前课=第2课）进池
    assert "第3课到期点" not in contents  # 未学课不进池
    db.close()


def test_knowledge_rotation_includes_mastered():
    """无限循环：已掌握知识点（在已学但非当前课）仍靠轮转档回来。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 第1课 1 个知识点「形近字辨析」
    doc = db.query(PdfDocument).first()
    # 第2课（已学）含一个已掌握知识点
    l2 = Lesson(document_id=doc.id, subject="语文", title="第2课",
                start_page=3, end_page=4, extract_status="done", audit_status="approved")
    db.add(l2); db.flush()
    kp2 = KnowledgePoint(subject="语文", category="字词", content="已掌握点", lesson_id=l2.id)
    db.add(kp2); db.flush()
    db.add(KnowledgeMastery(user_id=uid, knowledge_point_id=kp2.id,
                            attempts=json.dumps([True, True]),
                            mastery=0.95, mastered=True,
                            next_review_at=datetime.utcnow() + timedelta(days=30)))
    # 第3课（当前课）含一个新知识点，使旧算法只会取到当前课的点而漏掉「已掌握点」
    l3 = Lesson(document_id=doc.id, subject="语文", title="第3课",
                start_page=5, end_page=6, extract_status="done", audit_status="approved")
    db.add(l3); db.flush()
    db.add(KnowledgePoint(subject="语文", category="字词", content="第3课新点", lesson_id=l3.id))
    db.add(LearningProgress(user_id=uid, subject="语文", current_lesson_id=l3.id))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="knowledge").first()
    assert t is not None
    contents = {q.get("content") for q in json.loads(t.content)}
    # 已掌握点在已学但非当前课，仍应靠轮转档回来（旧算法只取当前课点，不会取到它）
    assert "已掌握点" in contents
    db.close()


def test_knowledge_due_priority_over_new():
    """到期知识点优先于新知识点（排在前面）。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)
    _add_kps(db, db.query(Lesson).filter_by(id=l1_id).first(), ["新点A", "新点B"])
    due_kp = KnowledgePoint(subject="语文", category="字词", content="到期点", lesson_id=l1_id)
    db.add(due_kp); db.flush()
    db.add(KnowledgeMastery(user_id=uid, knowledge_point_id=due_kp.id,
                            attempts=json.dumps([False]),
                            mastery=0.1, mastered=False,
                            next_review_at=datetime.utcnow() - timedelta(days=1)))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="knowledge").first()
    assert t is not None
    contents = [q.get("content") for q in json.loads(t.content)]
    # 到期点必须排在最前
    assert contents[0] == "到期点"
    db.close()


def test_knowledge_review_cap_truncates_excess_due():
    """到期知识点超过 review_n=ceil(count/2) 时被截断。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # count 默认 5 → review_n = 3
    # 造 5 个到期知识点（> review_n）
    for i in range(5):
        kp = KnowledgePoint(subject="语文", category="字词", content=f"到期{i}", lesson_id=l1_id)
        db.add(kp); db.flush()
        db.add(KnowledgeMastery(user_id=uid, knowledge_point_id=kp.id,
                                attempts=json.dumps([False]), mastery=0.1, mastered=False,
                                next_review_at=datetime.utcnow() - timedelta(days=1)))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="knowledge").first()
    assert t is not None
    qs = json.loads(t.content)
    # 到期档只取 review_n=3 个；新知识点（形近字辨析）至少 1 个；总数不超 count=5
    due_picked = [q for q in qs if (q.get("content") or "").startswith("到期")]
    assert len(due_picked) == 3
    assert len(qs) <= 5
    db.close()
