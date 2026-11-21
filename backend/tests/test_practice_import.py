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


def test_parse_lesson_page_extracts_header_and_items():
    from app.services.practice_import import parse_lesson_page

    text = """第3课时 小数乘小数
1. 8.9 + 4.5 =        2. 1000 - 550 =
3. 0.76 - 0.39 =      4. 3.4 - 1.24 =
"""
    out = parse_lesson_page(text)
    assert out["lesson_no"] == 3
    assert out["lesson_title"] == "小数乘小数"
    assert [i["question_no"] for i in out["items"]] == ["1", "2", "3", "4"]
    assert "8.9" in out["items"][0]["question"]
    assert "0.76" in out["items"][2]["question"]


def test_parse_lesson_page_does_not_split_on_decimals():
    from app.services.practice_import import parse_lesson_page

    out = parse_lesson_page("第1课时 口算\n1. 计算 3.25 + 1.8 =")
    assert len(out["items"]) == 1
    assert "3.25" in out["items"][0]["question"]


def test_parse_lesson_page_handles_fullwidth_and_no_title():
    from app.services.practice_import import parse_lesson_page

    out = parse_lesson_page("第 12 课时 练习课\n（1）0.6×0.4＝")
    assert out["lesson_no"] == 12
    assert out["lesson_title"] == "练习课"
    assert out["items"][0]["question_no"] == "1"


def test_parse_lesson_page_returns_empty_when_no_header():
    from app.services.practice_import import parse_lesson_page

    out = parse_lesson_page("随便一段没有课时标题的文字")
    assert out["lesson_no"] is None
    assert out["items"] == []


def test_align_answers_matches_by_lesson_and_number():
    from app.services.practice_import import align_answers

    questions = [
        {"lesson_no": 3, "question_no": "1", "question": "8.9+4.5="},
        {"lesson_no": 3, "question_no": "2", "question": "1000-550="},
    ]
    answers = [{"lesson_no": 3, "question_no": "1", "answer": "13.4"}]
    aligned, missing = align_answers(questions, answers)
    assert aligned[0]["answer"] == "13.4"
    assert [m["question_no"] for m in missing] == ["2"]


def test_split_blanks_by_count():
    from app.services.practice_import import split_blanks

    assert split_blanks("0.24, 1.16", 2) == ["0.24", "1.16"]
    assert split_blanks("13.4", 1) == ["13.4"]
    assert split_blanks("1, 2, 3", 2) is None


def test_kind_maps_to_qtype():
    from app.services.practice_import import QTYPE_OF_KIND

    assert QTYPE_OF_KIND["oral"] == "oral"
    assert QTYPE_OF_KIND["fill"] == "fill_blank"
    assert QTYPE_OF_KIND["vertical"] == "calculation"
    assert QTYPE_OF_KIND["step"] == "calculation"
    assert QTYPE_OF_KIND["app"] == "application"


def test_qtype_category_is_derived_not_hardcoded():
    from app.core.question_types import CATEGORY_OF_QTYPE
    from app.services.practice_import import QTYPE_OF_KIND

    for qtype in QTYPE_OF_KIND.values():
        assert qtype in CATEGORY_OF_QTYPE
    assert "objective" not in set(CATEGORY_OF_QTYPE.values())


def test_build_drafts_sets_lesson_and_blank_json():
    from app.services.practice_import import build_drafts

    aligned = [
        {"lesson_no": 3, "lesson_title": "小数乘小数", "question_no": "1",
         "question": "8.9+4.5=", "answer": "13.4", "kind": "oral", "page": 11},
        {"lesson_no": 3, "lesson_title": "小数乘小数", "question_no": "2",
         "question": "____ + ____ =", "answer": "1, 2", "kind": "fill", "page": 11},
    ]
    drafts = build_drafts(aligned, document_id=7, blanks_of=lambda q: 2)
    assert drafts[0].qtype == "oral"
    assert drafts[0].lesson_no == 3
    assert drafts[0].source_document_id == 7
    assert drafts[1].qtype == "fill_blank"
    assert drafts[1].answer_json["blanks"] == ["1", "2"]


def test_build_drafts_downgrades_bad_fill_to_oral():
    """空位数与答案切分不符时降级为 oral，避免永远判错。"""
    from app.services.practice_import import build_drafts

    aligned = [{"lesson_no": 1, "question_no": "1", "question": "____",
                "answer": "1, 2, 3", "kind": "fill"}]
    drafts = build_drafts(aligned, document_id=1, blanks_of=lambda q: 2)
    assert drafts[0].qtype == "oral"


def test_publish_only_aligned(db):
    """未对齐的题保持 pending，不能进孩子端。"""
    from app.models import Question, QuestionBank
    from conftest import make_account
    from app.services.practice_import import publish_aligned

    parent = make_account(db, "pi_pub", "parent")
    bank = QuestionBank(user_id=parent.id, title="卷", subject="数学")
    db.add(bank)
    db.commit()
    q1 = Question(user_id=parent.id, bank_id=bank.id, qtype="oral",
                  question="a", answer="1", status="pending")
    q2 = Question(user_id=parent.id, bank_id=bank.id, qtype="oral",
                  question="b", answer="", status="pending")
    db.add_all([q1, q2])
    db.commit()

    n = publish_aligned(db, bank.id)
    db.commit()

    assert n == 1
    assert db.get(Question, q1.id).status == "published"
    assert db.get(Question, q2.id).status == "pending"


def test_publish_skips_fill_blank_without_blanks(db):
    from app.models import Question, QuestionBank
    from conftest import make_account
    from app.services.practice_import import publish_aligned

    parent = make_account(db, "pi_pub2", "parent")
    bank = QuestionBank(user_id=parent.id, title="卷2", subject="数学")
    db.add(bank)
    db.commit()
    q = Question(user_id=parent.id, bank_id=bank.id, qtype="fill_blank",
                 question="__ + __ =", answer="1, 2", answer_json="{}",
                 status="pending")
    db.add(q)
    db.commit()

    assert publish_aligned(db, bank.id) == 0
    assert db.get(Question, q.id).status == "pending"
