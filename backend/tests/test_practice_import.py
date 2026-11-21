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
    """大题号只作分组，每个算式行才是一道题。"""
    from app.services.practice_import import parse_lesson_page

    text = """第3课时 小数乘小数
1. 直接写出得数。
8.9 + 4.5 =
1000 - 550 =
2. 计算下面各题，能简算的要简算。
(72 ÷ 18 + 8) × 28
"""
    out = parse_lesson_page(text)
    assert out["lesson_no"] == 3
    assert out["lesson_title"] == "小数乘小数"
    assert len(out["items"]) == 3
    assert out["items"][0]["question"] == "8.9 + 4.5 ="
    assert out["items"][0]["kind"] == "oral"
    assert out["items"][2]["question"] == "(72 ÷ 18 + 8) × 28"
    assert out["items"][2]["kind"] == "step"


def test_parse_lesson_page_real_book_page():
    """真实页面（第 3 课时练习课）：15 道口算 + 6 道简算 + 1 道巧算。"""
    from app.services.practice_import import parse_lesson_page

    text = """第 3 课时 练习课
视频讲解　智能批改
1. 直接写出得数。（建议 2 分钟完成）
8.9 + 4.5 =
1000 − 550 =
3.32 + 2.74 =
2. 计算下面各题，能简算的要简算。（建议 6 分钟完成）
(72 ÷ 18 + 8) × 28
(13 × 125) × (3 × 8)
巧算。
2024 × 20232023 − 2023 × 20242024
月　日
RJ 五（上）
"""
    out = parse_lesson_page(text)
    assert out["lesson_no"] == 3
    assert len(out["items"]) == 6, [i["question"] for i in out["items"]]
    kinds = [i["kind"] for i in out["items"]]
    assert kinds[:3] == ["oral"] * 3
    assert kinds[3] == "step"
    # 页脚噪音不能被当成题
    assert all("RJ" not in i["question"] for i in out["items"])


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


def test_run_import_job_publishes_aligned_and_records_failures(db, monkeypatch):
    from app.models import Question, QuestionBank, PdfDocument, PracticeImportJob
    from conftest import make_account
    from app.services import practice_import as pi
    from app.database import SessionLocal

    parent = make_account(db, "pi_job", "parent")
    bank = QuestionBank(user_id=parent.id, title="卷", subject="数学")
    doc = PdfDocument(filename="b.pdf", subject="数学", storage_path="uploads/x.pdf",
                      content_kind="practice")
    db.add_all([bank, doc])
    db.commit()
    job = PracticeImportJob(
        user_id=parent.id, bank_id=bank.id, document_id=doc.id, total_pages=4,
        question_start_page=1, question_end_page=2,
        answer_start_page=3, answer_end_page=4,
    )
    db.add(job)
    db.commit()
    job_id, bank_id = job.id, bank.id
    db.close()

    pages = {
        1: "第3课时 小数乘小数\n1. 直接写出得数。\n8.9 + 4.5 =\n1000 - 550 =",
        2: "",
    }
    monkeypatch.setattr(pi, "_ocr_text", lambda path, idx, db_, **kw: pages.get(idx + 1, ""))
    monkeypatch.setattr(pi, "SessionLocal", SessionLocal, raising=False)
    # 答案由 AI 求解（不依赖答案页 OCR）
    monkeypatch.setattr(
        "app.services.practice_solve.solve_math_items",
        lambda db_, items, **kw: {i: "1" for i in range(len(items))},
    )

    pi.run_import_job(job_id)

    s = SessionLocal()
    try:
        fresh = s.get(PracticeImportJob, job_id)
        assert fresh.status == "failed"      # 第 2 页识别失败
        assert json.loads(fresh.failed_pages) == [2]
        assert s.query(Question).filter_by(bank_id=bank_id, status="published").count() == 2
        assert s.get(QuestionBank, bank_id).source == "practice_pdf"
    finally:
        s.close()


def test_run_import_job_all_ok_marks_done(db, monkeypatch):
    from app.models import PdfDocument, PracticeImportJob, QuestionBank
    from conftest import make_account
    from app.services import practice_import as pi
    from app.database import SessionLocal

    parent = make_account(db, "pi_job2", "parent")
    bank = QuestionBank(user_id=parent.id, title="卷2", subject="数学")
    doc = PdfDocument(filename="c.pdf", subject="数学", storage_path="uploads/y.pdf",
                      content_kind="practice")
    db.add_all([bank, doc])
    db.commit()
    job = PracticeImportJob(
        user_id=parent.id, bank_id=bank.id, document_id=doc.id, total_pages=2,
        question_start_page=1, question_end_page=1,
        answer_start_page=2, answer_end_page=2,
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    pages = {1: "第1课时 口算\n1. 直接写出得数。\n1 + 1 =", 2: ""}
    monkeypatch.setattr(pi, "_ocr_text", lambda path, idx, db_, **kw: pages.get(idx + 1, ""))
    monkeypatch.setattr(
        "app.services.practice_solve.solve_math_items",
        lambda db_, items, **kw: {0: "2"},
    )

    pi.run_import_job(job_id)

    s = SessionLocal()
    try:
        row = s.get(PracticeImportJob, job_id)
        assert row.status == "done"
        assert row.published_count == 1
        assert row.question_count == 1
    finally:
        s.close()


import json  # noqa: E402


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


def test_import_rejects_without_answer_pages(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import QuestionBank

    s = SessionLocal()
    p, _c, parent_h, _ch = parent_child(s, "pib2")
    bank = QuestionBank(user_id=p.id, title="卷", subject="数学", source="practice_pdf")
    s.add(bank)
    s.commit()
    bank_id = bank.id
    s.close()

    client = _client_router()
    r = client.post(f"/api/banks/{bank_id}/import-practice-pdf", headers=parent_h,
                    files={"file": ("a.pdf", b"%PDF-1.4 fake", "application/pdf")},
                    data={"answer_start_page": "", "answer_end_page": ""})
    assert r.status_code == 400
    assert "答案页" in r.json()["detail"]


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


def test_split_row_separates_columns():
    from app.services.practice_import import _split_row

    parts = _split_row("8.9＋4.5＝    1000－550＝    3.32＋2.74＝")
    assert len(parts) == 3
    assert parts[0].startswith("8.9")


def test_build_drafts_strips_answer_from_question():
    from app.services.practice_import import build_drafts

    aligned = [{"lesson_no": 1, "question_no": "1",
                "question": "8.9＋4.5＝13.4", "answer": "13.4", "kind": "oral"}]
    drafts = build_drafts(aligned, document_id=1)
    assert drafts[0].question == "8.9＋4.5 ="
    assert drafts[0].answer == "13.4"


def test_parse_answer_page_without_lesson_header():
    """答案页没有「第N课时」标题，仍要能解析出答案。"""
    from app.services.practice_import import parse_answer_page

    text = """1. 13.4
2. 450
3. 60 ÷ 5 = 12
"""
    items = parse_answer_page(text)
    assert len(items) == 3
    assert items[0]["answer"] == "13.4"
    assert items[2]["answer"] == "12"   # 带过程时取最后结果


def test_align_by_order_pairs_nth_question_with_nth_answer():
    from app.services.practice_import import align_by_order

    qs = [{"question_no": "1", "question": "a"}, {"question_no": "2", "question": "b"}]
    ans = [{"answer": "1"}, {"answer": "2"}]
    aligned, missing = align_by_order(qs, ans)
    assert len(aligned) == 2
    assert aligned[1]["answer"] == "2"
    assert missing == []


def test_align_by_order_marks_tail_as_missing():
    from app.services.practice_import import align_by_order

    qs = [{"question_no": "1"}, {"question_no": "2"}, {"question_no": "3"}]
    ans = [{"answer": "1"}]
    aligned, missing = align_by_order(qs, ans)
    assert len(aligned) == 1
    assert len(missing) == 2
