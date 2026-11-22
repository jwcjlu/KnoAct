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


def test_is_aligned_legacy_questions_unchanged(setup_db, db):
    """work_mode 为空的老题必须走原逻辑：cloze 无 blanks 不发布。"""
    from app.models import Question
    from app.services.practice_import import _is_aligned

    q = Question(qtype="cloze", qtype_category="blank", question="x",
                 answer="a", answer_json='{"blanks":[]}', work_mode="")
    assert _is_aligned(q) is False


def test_is_aligned_new_numeric_list_requires_blanks(setup_db, db):
    from app.models import Question
    from app.services.practice_import import _is_aligned

    q = Question(qtype="fill_blank", qtype_category="blank", question="x",
                 answer="1.2, 1.44", answer_json='{"blanks":["1.2","1.44"]}',
                 work_mode="pattern")
    assert _is_aligned(q) is True

    q2 = Question(qtype="fill_blank", qtype_category="blank", question="x",
                  answer="1.2", answer_json='{"blanks":[]}', work_mode="pattern")
    assert _is_aligned(q2) is False


def test_is_aligned_new_symbol_and_choice_do_not_need_blanks(setup_db, db):
    """symbol/choice 不是多空题，有答案就该发布（旧逻辑会误挡）。"""
    from app.models import Question
    from app.services.practice_import import _is_aligned

    sym = Question(qtype="fill_blank", qtype_category="blank",
                   question="30.5 ○ 3.05", answer=">", answer_json="{}",
                   work_mode="compare")
    assert _is_aligned(sym) is True

    ch = Question(qtype="single_choice", qtype_category="choice", question="x",
                  answer="B", answer_json='{"correct_index":1}',
                  work_mode="choice")
    assert _is_aligned(ch) is True


def test_is_aligned_empty_answer_never_published(setup_db, db):
    from app.models import Question
    from app.services.practice_import import _is_aligned

    for mode in ("oral", "pattern", "compare", "photo", "app", ""):
        q = Question(qtype="oral", qtype_category="subjective", question="x",
                     answer="", answer_json="{}", work_mode=mode)
        assert _is_aligned(q) is False, mode


import json  # noqa: E402


def _mk_job(db, prefix, pages, doc_name):
    """建 parent + bank + document + job，返回 (job_id, bank_id, doc_id)。"""
    from app.models import PdfDocument, PracticeImportJob, QuestionBank
    from conftest import make_account

    parent = make_account(db, f"{prefix}_p", role="parent")
    doc = PdfDocument(filename=doc_name, subject="数学",
                      storage_path=f"D:/tmp/{doc_name}", content_kind="practice")
    db.add(doc)
    db.flush()
    bank = QuestionBank(user_id=parent.id, title="练习册", subject="数学",
                        grade=5, source="practice_pdf")
    db.add(bank)
    db.flush()
    job = PracticeImportJob(user_id=parent.id, bank_id=bank.id, document_id=doc.id,
                            total_pages=pages, question_start_page=1,
                            question_end_page=pages)
    db.add(job)
    db.commit()
    return job.id, bank.id, doc.id


def test_run_import_job_creates_groups_and_items(setup_db, db, monkeypatch):
    """2 页 → 1 个题组（跨页合并）+ 4 个小题（3 示例 + 1 待做）。"""
    from app.models import PracticeQuestionGroup, Question
    from app.services import practice_import as pi

    job_id, bank_id, _doc_id = _mk_job(db, "rj1", 2, "b.pdf")

    page1 = {
        "page_type": "practice",
        "groups": [{
            "stem": "不计算，运用规律直接写出得数",
            "instruction": "", "lesson_no": 3,
            "lesson_title": "第3课时 一个数除以小数",
            "work_mode": "pattern", "need_process": False,
            "continues_next_page": True,
            "items": [
                {"seq": 1, "y": 0.2, "text": "$1.08 \\div 0.9 = 1.2$",
                 "answer_hint": "1.2", "is_example": True},
                {"seq": 2, "y": 0.4, "text": "$11.106 \\div 0.9 = 12.34$",
                 "answer_hint": "12.34", "is_example": True},
            ],
        }],
        "image_questions": [],
    }
    page2 = {
        "page_type": "practice",
        "groups": [{
            "stem": "不计算，运用规律直接写出得数",
            "instruction": "", "lesson_no": 3,
            "lesson_title": "第3课时 一个数除以小数",
            "work_mode": "pattern", "need_process": False,
            "continues_next_page": False,
            "items": [
                {"seq": 3, "y": 0.2, "text": "$111.06 \\div 0.9 = 123.4$",
                 "answer_hint": "123.4", "is_example": True},
                {"seq": 4, "y": 0.4, "text": "$1111.05 \\div 0.9 =$ ____",
                 "answer_hint": "", "is_example": False},
            ],
        }],
        "image_questions": [],
    }

    # render_page_png 收到的是 pno-1（0-based），所以 fake 的键是 0/1
    monkeypatch.setattr("app.services.practice_image.render_page_png",
                        lambda path, idx, dpi=150: f"png{idx}".encode())
    monkeypatch.setattr("app.services.parsers.math_page.analyze_page",
                        lambda db_, img, **kw: {0: page1, 1: page2}[int(img[-1:])])
    # 该组是 pattern（answer_kind=numeric_list），必须返回 blanks，
    # 否则 answer_json={} → 发布闸门挡下 → todo[0].status 不会是 published
    monkeypatch.setattr(
        "app.services.practice_solve.solve_math_items",
        lambda db_, items, **kw: {
            0: {"kind": "numeric_list", "blanks": ["1234.5"],
                "answer": "1234.5"},
        },
    )

    pi.run_import_job(job_id)

    db.expire_all()
    from app.models import PracticeImportJob

    job = db.get(PracticeImportJob, job_id)
    assert job.status == "done", job.error

    groups = db.query(PracticeQuestionGroup).filter_by(bank_id=bank_id).all()
    assert len(groups) == 1
    assert groups[0].page_start == 1 and groups[0].page_end == 2
    assert groups[0].lesson_no == 3
    assert groups[0].lesson_title == "第3课时 一个数除以小数"

    qs = (db.query(Question).filter_by(bank_id=bank_id)
          .order_by(Question.seq_in_group).all())
    assert len(qs) == 4
    assert sum(1 for q in qs if q.is_example) == 3
    todo = [q for q in qs if not q.is_example]
    assert len(todo) == 1
    assert todo[0].group_id == groups[0].id
    assert todo[0].answer == "1234.5"
    assert json.loads(todo[0].answer_json)["blanks"] == ["1234.5"]
    assert todo[0].status == "published"
    # 示例行也发布（前端要读它来展示），但不进每日一练（Task 15 过滤）
    assert all(q.status == "published" for q in qs if q.is_example)


def test_run_import_job_skips_non_practice_pages(setup_db, db, monkeypatch):
    """目录页/答案页不入库，但要留页记录。"""
    from app.models import PracticeImportPage, PracticeQuestionGroup, Question
    from app.services import practice_import as pi

    job_id, bank_id, doc_id = _mk_job(db, "rj2", 2, "c.pdf")

    monkeypatch.setattr("app.services.practice_image.render_page_png",
                        lambda path, idx, dpi=150: b"x")
    monkeypatch.setattr("app.services.parsers.math_page.analyze_page",
                        lambda db_, img, **kw: {
                            "page_type": "toc", "groups": [],
                            "image_questions": []})

    pi.run_import_job(job_id)

    db.expire_all()
    assert db.query(PracticeQuestionGroup).filter_by(bank_id=bank_id).count() == 0
    assert db.query(Question).filter_by(bank_id=bank_id).count() == 0
    pages = db.query(PracticeImportPage).filter_by(document_id=doc_id).all()
    assert len(pages) == 2
    assert all(p.page_type == "toc" for p in pages)


def test_run_import_job_records_page_rows(setup_db, db, monkeypatch):
    from app.models import PracticeImportPage
    from app.services import practice_import as pi

    job_id, _bank_id, doc_id = _mk_job(db, "rj3", 1, "d.pdf")

    monkeypatch.setattr("app.services.practice_image.render_page_png",
                        lambda path, idx, dpi=150: b"x")
    monkeypatch.setattr("app.services.parsers.math_page.analyze_page",
                        lambda db_, img, **kw: {
                            "page_type": "practice",
                            "groups": [{
                                "stem": "", "instruction": "", "lesson_no": None,
                                "lesson_title": "", "work_mode": "oral",
                                "need_process": False,
                                "continues_next_page": False,
                                "items": [{"seq": 1, "y": 0.1, "text": "1+1=____",
                                           "answer_hint": "", "is_example": False}],
                            }],
                            "image_questions": []})
    monkeypatch.setattr(
        "app.services.practice_solve.solve_math_items",
        lambda db_, items, **kw: {0: {"kind": "number", "answer": "2"}},
    )

    pi.run_import_job(job_id)

    db.expire_all()
    pages = db.query(PracticeImportPage).filter_by(document_id=doc_id).all()
    assert len(pages) == 1
    assert pages[0].page_no == 1
    assert pages[0].page_type == "practice"
    assert pages[0].group_count == 1


def test_run_import_job_marks_failed_page(setup_db, db, monkeypatch):
    """AI 抛异常时该页标失败，job 标 failed 且可重试。"""
    from app.models import PracticeImportJob, PracticeImportPage
    from app.services import practice_import as pi

    job_id, _bank_id, doc_id = _mk_job(db, "rj4", 1, "e.pdf")

    monkeypatch.setattr("app.services.practice_image.render_page_png",
                        lambda path, idx, dpi=150: b"x")

    def _boom(db_, img, **kw):
        raise RuntimeError("vision down")

    monkeypatch.setattr("app.services.parsers.math_page.analyze_page", _boom)

    pi.run_import_job(job_id)

    db.expire_all()
    job = db.get(PracticeImportJob, job_id)
    assert job.status == "failed"
    assert job.failed_pages == "[1]"
    pages = db.query(PracticeImportPage).filter_by(document_id=doc_id).all()
    assert pages[0].status == "failed"
