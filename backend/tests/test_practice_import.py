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
