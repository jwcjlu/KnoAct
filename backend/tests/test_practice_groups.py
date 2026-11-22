"""题组两级模型：表结构、可空性、迁移幂等。"""
from sqlalchemy import inspect

from app.models import PracticeQuestionGroup, Question
from conftest import make_user


def test_new_tables_registered(setup_db, db):
    names = set(inspect(db.get_bind()).get_table_names())
    assert "practice_question_groups" in names
    assert "practice_import_pages" in names


def test_question_has_group_columns(setup_db, db):
    cols = {c["name"] for c in inspect(db.get_bind()).get_columns("questions")}
    assert {"group_id", "seq_in_group", "is_example", "work_mode"} <= cols


def test_group_lesson_no_is_nullable(setup_db, db):
    """综合练习页没有「第N课时」，lesson_no 必须允许 NULL。"""
    cols = {c["name"]: c for c in inspect(db.get_bind()).get_columns(
        "practice_question_groups")}
    assert cols["lesson_no"]["nullable"] is True


def test_group_columns_defaults(setup_db, db):
    from app.models import QuestionBank

    user = make_user(db)
    bank = QuestionBank(user_id=user.id, title="练习册", subject="数学",
                        grade=5, source="practice_pdf")
    db.add(bank)
    db.flush()
    g = PracticeQuestionGroup(bank_id=bank.id, user_id=user.id,
                              stem="直接写出得数", work_mode="oral",
                              page_start=1, page_end=1)
    db.add(g)
    db.flush()
    assert g.need_process is False
    assert g.incomplete is False
    assert g.instruction == ""
    assert g.lesson_title == ""
    assert g.lesson_no is None


def test_migration_is_idempotent():
    """连跑两次不报错（列/索引已存在时跳过）。"""
    from app.migrate_practice_groups import migrate

    migrate()
    migrate()
