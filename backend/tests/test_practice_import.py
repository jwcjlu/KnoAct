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


def _client_router():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.practice_import import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_create_practice_book_bank(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child

    s = SessionLocal()
    _p, _c, parent_h, _ch = parent_child(s, "pib")
    s.close()
    client = _client_router()
    r = client.post("/api/banks/practice-book", headers=parent_h,
                    json={"title": "RJ五上", "subject": "数学", "grade": 5})
    assert r.status_code == 200
    assert r.json()["id"] > 0


def test_import_rejects_without_vision_model(setup_db, monkeypatch):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import QuestionBank
    from app.routers import practice_import as pi

    monkeypatch.setattr(pi, "_vision_ready", lambda db: False)

    s = SessionLocal()
    p, _c, parent_h, _ch = parent_child(s, "pib3")
    bank = QuestionBank(user_id=p.id, title="卷", subject="数学", source="practice_pdf")
    s.add(bank)
    s.commit()
    bank_id = bank.id
    s.close()

    client = _client_router()
    r = client.post(f"/api/banks/{bank_id}/import-practice-pdf", headers=parent_h,
                    files={"file": ("a.pdf", b"%PDF-1.4 fake", "application/pdf")},
                    data={"answer_start_page": 100, "answer_end_page": 107})
    assert r.status_code == 400
    assert "视觉模型" in r.json()["detail"]


def test_missing_answers_lists_pending_without_answer(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import Question, QuestionBank

    s = SessionLocal()
    p, _c, parent_h, _ch = parent_child(s, "pib4")
    bank = QuestionBank(user_id=p.id, title="卷", subject="数学", source="practice_pdf")
    s.add(bank)
    s.flush()
    s.add(Question(user_id=p.id, bank_id=bank.id, qtype="oral", question="a",
                   answer="", status="pending", lesson_no=3, question_no="1"))
    s.commit()
    bank_id = bank.id
    s.close()

    client = _client_router()
    r = client.get(f"/api/practice-import/missing-answers?bank_id={bank_id}",
                   headers=parent_h)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["question_no"] == "1"


def test_patch_question_publishes_after_answer(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import Question, QuestionBank

    s = SessionLocal()
    p, _c, parent_h, _ch = parent_child(s, "pib5")
    bank = QuestionBank(user_id=p.id, title="卷", subject="数学", source="practice_pdf")
    s.add(bank)
    s.flush()
    q = Question(user_id=p.id, bank_id=bank.id, qtype="oral", question="a",
                 answer="", status="pending")
    s.add(q)
    s.commit()
    qid = q.id
    s.close()

    client = _client_router()
    r = client.patch(f"/api/practice-import/questions/{qid}", headers=parent_h,
                     json={"answer": "13.4"})
    assert r.status_code == 200
    assert r.json()["status"] == "published"


def test_lessons_endpoint_counts_published(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import Question, QuestionBank

    s = SessionLocal()
    p, _c, parent_h, _ch = parent_child(s, "pib6")
    bank = QuestionBank(user_id=p.id, title="卷", subject="数学", source="practice_pdf")
    s.add(bank)
    s.flush()
    s.add(Question(user_id=p.id, bank_id=bank.id, qtype="oral", question="a",
                   answer="1", status="published", lesson_no=3, lesson_title="小数乘小数"))
    s.commit()
    bank_id = bank.id
    s.close()

    client = _client_router()
    r = client.get(f"/api/practice-import/lessons?bank_id={bank_id}", headers=parent_h)
    assert r.status_code == 200
    lessons = r.json()["lessons"]
    assert lessons[0]["lesson_no"] == 3
    assert lessons[0]["title"] == "小数乘小数"
    assert lessons[0]["count"] == 1


def test_practice_doc_hidden_from_textbook_list(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import PdfDocument

    s = SessionLocal()
    p, _c, parent_h, _ch = parent_child(s, "pi_hide")
    s.add(PdfDocument(filename="练习册.pdf", subject="数学", storage_path="uploads/a.pdf",
                      content_kind="practice"))
    s.add(PdfDocument(filename="教材.pdf", subject="数学", storage_path="uploads/b.pdf",
                      content_kind="textbook"))
    s.commit()
    s.close()

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.pdf import router as pdf_router

    app = FastAPI()
    app.include_router(pdf_router)
    r = TestClient(app).get("/api/pdf/documents", headers=parent_h)
    names = [d["filename"] for d in r.json()]
    assert "教材.pdf" in names
    assert "练习册.pdf" not in names

    r2 = TestClient(app).get("/api/pdf/documents?include_practice=true", headers=parent_h)
    assert "练习册.pdf" in [d["filename"] for d in r2.json()]


def test_practice_bank_excluded_from_practice_list(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import Question, QuestionBank

    s = SessionLocal()
    p, c, _ph, child_h = parent_child(s, "pi_hide2")
    bank = QuestionBank(user_id=p.id, title="练习册卷", subject="数学",
                        source="practice_pdf", status="active")
    s.add(bank)
    s.flush()
    s.add(Question(user_id=p.id, bank_id=bank.id, qtype="oral", question="a",
                   answer="1", status="published"))
    s.commit()
    s.close()

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.bank import router as bank_router

    app = FastAPI()
    app.include_router(bank_router)
    r = TestClient(app).get("/api/banks/practice", headers=child_h)
    assert r.status_code == 200
    assert all(b["title"] != "练习册卷" for b in r.json())


def test_strip_answer_removes_computed_result():
    """视觉模型会自己算答案写进题干，必须截断在等号。"""
    from app.services.practice_import import _strip_answer

    assert _strip_answer("8.9＋4.5＝13.4") == "8.9＋4.5 ="
    assert _strip_answer("1000－550＝450") == "1000－550 ="
    # 不带答案的原样保留
    assert _strip_answer("8.9 + 4.5 =") == "8.9 + 4.5 ="
    # 等号后是问号不算答案
    assert _strip_answer("1+1=？") == "1+1=？"


def test_build_drafts_strips_answer_from_question():
    from app.services.practice_import import build_drafts

    aligned = [{"lesson_no": 1, "question_no": "1",
                "question": "8.9＋4.5＝13.4", "answer": "13.4", "kind": "oral"}]
    drafts = build_drafts(aligned, document_id=1)
    assert drafts[0].question == "8.9＋4.5 ="
    assert drafts[0].answer == "13.4"


def test_strip_answer_keeps_equation():
    """方程不能被截断：4x-5.2 = 5.2 的右边是方程的一部分。"""
    from app.services.practice_import import _strip_answer

    assert _strip_answer("4x − 5.2 = 5.2") == "4x − 5.2 = 5.2"
    assert _strip_answer("2(x + 8) = 22") == "2(x + 8) = 22"
    assert _strip_answer("4.8x + 2.6x = 3.7") == "4.8x + 2.6x = 3.7"
    # 纯算式仍要剥离答案
    assert _strip_answer("8.9＋4.5＝13.4") == "8.9＋4.5 ="


from app.services.practice_import import _strip_answer, build_drafts


def test_strip_answer_closes_formula_and_adds_blank():
    """公式内截断必须重新闭合 $ 并补空位，而不是留一个孤立 $。"""
    out = _strip_answer(r"$111.06 \div 0.9 = 123.4$")
    assert out == r"$111.06 \div 0.9 =$ ____"
    assert out.count("$") % 2 == 0


def test_strip_answer_keeps_equation_with_variable():
    """含未知数的方程不截断（5.2 是方程的一部分）。"""
    src = r"$4x - 5.2 = 5.2$"
    assert _strip_answer(src) == src


def test_strip_answer_skips_example_rows():
    """示例行本来就要显示答案，完全不截断。"""
    src = r"$1.08 \div 0.9 = 1.2$"
    assert _strip_answer(src, is_example=True) == src


def test_strip_answer_legacy_plain_text_still_works():
    """没有 $ 的旧格式保持原行为。"""
    assert _strip_answer("8.9 + 4.5 = 13.4") == "8.9 + 4.5 ="


def test_strip_answer_no_equals_untouched():
    assert _strip_answer("求涂色部分的面积") == "求涂色部分的面积"


def test_strip_answer_right_side_not_numeric_untouched():
    src = r"$x + 1 = ?$"
    assert _strip_answer(src) == src


def test_strip_answer_always_keeps_dollar_pairing():
    for src in [
        r"$111.06 \div 0.9 = 123.4$",
        r"$1.08 \div 0.9 = 1.2$",
        r"$4x - 5.2 = 5.2$",
        r"$3.5 \times 2 = 7$",
    ]:
        assert _strip_answer(src).count("$") % 2 == 0, src


def test_build_drafts_passes_group_fields():
    drafts = build_drafts(
        [{
            "kind": "fill", "question": r"$1.08 \div 0.9 = 1.2$", "answer": "1.2",
            "group_id": 7, "seq_in_group": 3, "is_example": True,
            "work_mode": "pattern", "lesson_no": 5, "lesson_title": "第1课时",
            "page": 5,
        }],
        document_id=99,
    )
    d = drafts[0]
    assert d.group_id == 7
    assert d.seq_in_group == 3
    assert d.is_example is True
    assert d.work_mode == "pattern"
    # 示例行不截断，答案保留
    assert "1.2" in d.question


def test_build_drafts_writes_blanks_for_numeric_list():
    """numeric_list 必须把 blanks 写进 answer_json，否则永远过不了发布闸门。"""
    drafts = build_drafts(
        [{
            "kind": "fill", "question": "$1111.05 \\div 0.9 =$ ____",
            "answer": "1234.5, 12345", "blanks": ["1234.5", "12345"],
            "work_mode": "pattern", "is_example": False,
            "seq_in_group": 1, "group_id": 1,
        }],
        document_id=1,
    )
    d = drafts[0]
    assert d.answer_json.get("blanks") == ["1234.5", "12345"]
    # qtype 来自注册表，不是旧的 kind 映射
    assert d.qtype == "fill_blank"


def test_build_drafts_writes_correct_index_for_choice():
    drafts = build_drafts(
        [{
            "kind": "other", "question": "下列哪个是质数？",
            "answer": "B", "correct_index": 1,
            "work_mode": "choice", "is_example": False,
            "seq_in_group": 1, "group_id": 1,
        }],
        document_id=1,
    )
    d = drafts[0]
    assert d.qtype == "single_choice"
    assert d.answer_json.get("correct_index") == 1


def test_build_drafts_symbol_has_no_blanks_requirement():
    drafts = build_drafts(
        [{
            "kind": "fill", "question": "30.5 ○ 3.05", "answer": ">",
            "work_mode": "compare", "is_example": False,
            "seq_in_group": 1, "group_id": 1,
        }],
        document_id=1,
    )
    d = drafts[0]
    assert d.answer == ">"
    assert d.answer_json == {}


def test_build_drafts_legacy_fill_without_blanks_degrades_to_oral():
    """旧路径（无 work_mode）的 fill 题切不出 blanks 时降级成 oral，
    否则它既没有 blanks 又保持 fill_blank，会被发布闸门永久挡住。"""
    # 没有 blanks_of 回调、也没有 work_mode → 空数为 0 → 切不出 blanks
    drafts = build_drafts(
        [{"kind": "fill", "question": "$1+1=$", "answer": "2"}],
        document_id=1,
    )
    assert drafts[0].qtype == "oral"
    assert drafts[0].answer_json == {}


def test_build_drafts_legacy_equation_without_blanks_degrades_to_oral():
    drafts = build_drafts(
        [{"kind": "equation", "question": "$4x - 5.2 = 5.2$", "answer": "2.6"}],
        document_id=1,
    )
    assert drafts[0].qtype == "oral"


def test_solve_math_items_returns_dict_shape(monkeypatch):
    """返回结构从 dict[int, str] 改为 dict[int, dict]。"""
    import app.services.practice_solve as ps

    monkeypatch.setattr(ps, "_provider_ready", lambda db: True)
    monkeypatch.setattr(ps, "_call_solver", lambda db, chunk: {
        0: {"kind": "number", "answer": "13.4"},
        1: {"kind": "numeric_list", "blanks": ["1.2", "1.44"]},
    })

    out = ps.solve_math_items(None, [{"question": "a"}, {"question": "b"}])
    assert out[0]["answer"] == "13.4"
    assert out[1]["blanks"] == ["1.2", "1.44"]


def test_derive_page_range_without_answer_pages():
    """答案页可选：不填时题面页跑到最后一页，而不是 0 页。"""
    from app.routers.practice_import import _derive_page_range

    q_start, q_end = _derive_page_range(
        question_start_page=None, question_end_page=None,
        answer_start_page=None, answer_end_page=None, total_pages=12)
    assert (q_start, q_end) == (1, 12)


def test_derive_page_range_narrows_when_answer_page_given():
    """提供了答案页则收窄到答案页之前，少跑几次视觉调用。"""
    from app.routers.practice_import import _derive_page_range

    q_start, q_end = _derive_page_range(
        question_start_page=None, question_end_page=None,
        answer_start_page=96, answer_end_page=107, total_pages=107)
    assert (q_start, q_end) == (1, 95)


def test_derive_page_range_explicit_question_end_wins():
    from app.routers.practice_import import _derive_page_range

    q_start, q_end = _derive_page_range(
        question_start_page=3, question_end_page=40,
        answer_start_page=96, answer_end_page=107, total_pages=107)
    assert (q_start, q_end) == (3, 40)

def test_call_solver_includes_group_stem(monkeypatch):
    """字母规律题的 a、b 定义在题干里，求解器必须看到，否则只会答 'ab'。"""
    import app.services.ai as ai_mod
    import app.services.practice_solve as ps

    captured = {}

    class _P:
        name = "openai"

        def generate(self, prompt, system="", json_mode=False):
            captured["prompt"] = prompt
            return '{"answers":[{"index":0,"kind":"number","answer":"0.0125"}]}'

    monkeypatch.setattr(ai_mod, "get_provider",
                        lambda db, child_id=None: _P(), raising=False)
    out = ps._call_solver(
        None,
        [{"question": r"$a \times b =$ ____",
          "stem": r"若 $a = 0.\underbrace{00\cdots00}_{2020\text{个}0}1$"}],
    )
    assert "材料" in captured["prompt"], captured["prompt"]
    assert "underbrace" in captured["prompt"], "题干内容应传给求解器"
    assert out[0]["answer"] == "0.0125"


def test_call_solver_omits_redundant_stem(monkeypatch):
    """题干与题目相同时不要重复贴两遍（省 token）。"""
    import app.services.ai as ai_mod
    import app.services.practice_solve as ps

    captured = {}

    class _P:
        name = "openai"

        def generate(self, prompt, system="", json_mode=False):
            captured["prompt"] = prompt
            return '{"answers":[{"index":0,"kind":"number","answer":"1"}]}'

    monkeypatch.setattr(ai_mod, "get_provider",
                        lambda db, child_id=None: _P(), raising=False)
    ps._call_solver(None, [{"question": "1+1=____", "stem": "1+1=____"}])
    assert "材料" not in captured["prompt"]
    assert captured["prompt"].count("1+1=____") == 1
