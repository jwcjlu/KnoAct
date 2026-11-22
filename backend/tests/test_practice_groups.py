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


def test_persist_drafts_writes_group_fields(setup_db, db):
    from app.core.source_adapter import QuestionDraft
    from app.models import Question, QuestionBank
    from app.routers.bank import _persist_drafts
    from conftest import make_user

    user = make_user(db)
    bank = QuestionBank(user_id=user.id, title="练习册", subject="数学",
                        grade=5, source="practice_pdf")
    db.add(bank)
    db.flush()

    g = PracticeQuestionGroup(bank_id=bank.id, user_id=user.id,
                              stem="直接写出得数", work_mode="pattern",
                              page_start=3, page_end=3)
    db.add(g)
    db.flush()

    d = QuestionDraft(qtype="fill_blank", question="1+1=____", answer="2")
    d.group_id = g.id
    d.seq_in_group = 2
    d.is_example = True
    d.work_mode = "pattern"
    _persist_drafts(db, bank, [d], "practice_pdf")
    db.commit()

    row = db.query(Question).filter_by(bank_id=bank.id).one()
    assert row.group_id == g.id
    assert row.seq_in_group == 2
    assert row.is_example is True
    assert row.work_mode == "pattern"


def test_dict_to_draft_keeps_practice_fields():
    """草稿预览→确认导入不能丢练习册字段。"""
    from app.routers.bank import _dict_to_draft

    d = _dict_to_draft({
        "qtype": "fill_blank", "question": "1+1=____", "answer": "2",
        "lesson_no": 5, "question_no": "3", "image_path": "uploads/x.png",
        "group_id": 11, "seq_in_group": 2, "is_example": True,
        "work_mode": "pattern",
    })
    assert d.lesson_no == 5
    assert d.image_path == "uploads/x.png"
    assert d.group_id == 11
    assert d.is_example is True
    assert d.work_mode == "pattern"


import pytest


def test_vision_json_requires_configured_endpoint(setup_db, db, monkeypatch):
    """未配置中转站时必须明确报错，而不是静默返回空串。"""
    import app.services.ai as ai_mod

    monkeypatch.setattr(ai_mod, "resolve", lambda *a, **k: type("R", (), {
        "api_key": "", "base_url": "", "options": {},
    })())
    with pytest.raises(RuntimeError):
        ai_mod.vision_json(db, b"\x89PNG", system="sys", prompt="p")


def test_vision_json_sends_json_mode_and_system(setup_db, db, monkeypatch):
    """断言：带 system 消息 + response_format=json_object + 图片。"""
    import app.services.ai as ai_mod

    captured = {}

    class _FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)

            class _Resp:
                choices = [type("C", (), {
                    "message": type("M", (), {"content": '{"page_type":"practice"}'})(),
                })()]

            return _Resp()

    class _FakeClient:
        def __init__(self, **kw):
            captured["client_kwargs"] = kw
            self.chat = type("C", (), {"completions": _FakeCompletions()})()

    monkeypatch.setattr(ai_mod, "_openai_client", lambda **kw: _FakeClient(**kw))
    monkeypatch.setattr(ai_mod, "resolve", lambda *a, **k: type("R", (), {
        "api_key": "k", "base_url": "http://x",
        "options": {"vision_model": "vl"},
    })())

    out = ai_mod.vision_json(db, b"\x89PNG", system="SYS", prompt="PROMPT")
    assert out.startswith("{")
    assert captured["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in captured["messages"]] == ["system", "user"]
    parts = captured["messages"][1]["content"]
    assert any(p.get("type") == "image_url" for p in parts)
    assert captured["model"] == "vl"
