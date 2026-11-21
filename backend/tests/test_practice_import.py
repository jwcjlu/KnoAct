from app import models  # noqa: F401  确保表已注册


def test_question_has_practice_columns(db):
    from app.models import Question

    cols = {c.name for c in Question.__table__.columns}
    for name in ("lesson_no", "lesson_title", "question_no", "source_document_id"):
        assert name in cols, f"缺少列 {name}"


def test_practice_tables_exist(db):
    from app.models import PracticeAttempt, PracticeImportJob

    assert PracticeImportJob.__tablename__ == "practice_import_jobs"
    assert PracticeAttempt.__tablename__ == "practice_attempts"
    cols = {c.name for c in PracticeAttempt.__table__.columns}
    # 家长查看要能还原「当时练的题干」与「AI 判定」
    for name in (
        "question_snapshot",
        "photo_path",
        "ai_status",
        "ai_final_answer",
        "ai_steps_plausible",
        "ai_reason",
    ):
        assert name in cols, f"PracticeAttempt 缺少列 {name}"


def test_question_index_on_bank_lesson(db):
    from app.models import Question

    names = {i.name for i in Question.__table__.indexes}
    assert "ix_questions_bank_lesson" in names


def test_persist_drafts_sets_user_id(db):
    """不写 user_id 的题会被 migrate_grade_buckets 在下次启动时删光。"""
    from app.models import Question, QuestionBank
    from conftest import make_account
    from app.core.source_adapter import QuestionDraft
    from app.routers.bank import _persist_drafts

    parent = make_account(db, "pi_parent", "parent")
    bank = QuestionBank(user_id=parent.id, title="测试卷", subject="数学", source="manual")
    db.add(bank)
    db.commit()

    ids = _persist_drafts(db, bank, [
        QuestionDraft(qtype="oral", question="8.9+4.5=", answer="13.4"),
    ], "test")
    db.commit()

    row = db.get(Question, ids[0])
    assert row.user_id == parent.id, "user_id 必须是卷主，否则启动迁移会删题"


def test_persist_drafts_survives_startup_migration(db):
    """回归：创建题 → 跑启动迁移 → 题还在。"""
    from app.models import Question, QuestionBank
    from conftest import make_account
    from app.core.source_adapter import QuestionDraft
    from app.routers.bank import _persist_drafts
    from app.migrate_grade_buckets import migrate

    parent = make_account(db, "pi_parent2", "parent")
    bank = QuestionBank(user_id=parent.id, title="卷2", subject="数学", source="manual")
    db.add(bank)
    db.commit()
    _persist_drafts(db, bank, [
        QuestionDraft(qtype="oral", question="1+1=", answer="2"),
    ], "test")
    db.commit()
    before = db.query(Question).count()

    migrate(db)  # 这是服务启动时跑的迁移

    assert db.query(Question).count() == before, "启动迁移把练习册题目删掉了"


def test_persist_drafts_passes_lesson_fields(db):
    from app.models import PdfDocument, Question, QuestionBank
    from conftest import make_account
    from app.core.source_adapter import QuestionDraft
    from app.routers.bank import _persist_drafts

    parent = make_account(db, "pi_parent3", "parent")
    bank = QuestionBank(user_id=parent.id, title="卷3", subject="数学", source="manual")
    doc = PdfDocument(filename="b.pdf", subject="数学", storage_path="uploads/b.pdf",
                      content_kind="practice")
    db.add_all([bank, doc])
    db.commit()

    d = QuestionDraft(qtype="oral", question="1+1=", answer="2")
    d.lesson_no = 3
    d.lesson_title = "小数乘小数"
    d.question_no = "1"
    d.source_document_id = doc.id
    ids = _persist_drafts(db, bank, [d], "practice_pdf")
    db.commit()

    row = db.get(Question, ids[0])
    assert row.lesson_no == 3
    assert row.lesson_title == "小数乘小数"
    assert row.question_no == "1"
    assert row.source_document_id == doc.id
