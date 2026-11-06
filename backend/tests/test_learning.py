from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.learning import router as learning_router
from conftest import make_account, make_user, make_lesson, bound_child_headers


def _client():
    app = FastAPI()
    app.include_router(learning_router)
    return TestClient(app)


def _h(uid):
    return bound_child_headers(uid)


def _seed_user():
    from app.database import SessionLocal
    s = SessionLocal()
    p = make_account(s, "p_lr", "parent")
    uid = make_account(s, "k_lr", "child", parent=p).id
    s.commit(); s.close()
    return uid


def _seed_two_lessons(s):
    """孩子 + 同一教材的两课（已审核），进度停在第 1 课。返回 (uid, l1_id, l2_id)。"""
    from app.models import LearningProgress, PdfDocument, UserDocument
    p = make_account(s, "p_2l", "parent")
    uid = make_account(s, "k_2l", "child", parent=p).id
    l1 = make_lesson(s, audit_status="approved")
    l2 = make_lesson(s, title="第2课", start_page=4, end_page=6, audit_status="approved",
                     document=s.get(PdfDocument, l1.document_id))
    s.add(UserDocument(user_id=uid, document_id=l1.document_id))
    s.add(LearningProgress(user_id=uid, subject="语文", current_lesson_id=l1.id))
    s.commit()
    return uid, l1.id, l2.id


def test_dictation_pick_words(setup_db):
    from app.models import Lesson, WordBank
    from app.database import SessionLocal
    s = SessionLocal()
    from app.models import Lesson, UserDocument
    p = make_account(s, "p_pick", "parent")
    uid = make_account(s, "k_pick", "child", parent=p).id
    lid = make_lesson(s, audit_status="approved").id
    s.add(UserDocument(user_id=uid, document_id=s.get(Lesson, lid).document_id))
    s.add(WordBank(lesson_id=lid, subject="语文", word="徘徊", extra="pái huái"))
    s.add(WordBank(lesson_id=lid, subject="语文", word="矗立", extra="chù lì"))
    s.commit(); s.close()
    resp = _client().get(f"/api/dictation/words?user_id={uid}", headers=bound_child_headers(uid))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_dictation_grade(setup_db):
    uid = _seed_user()
    c = _client()
    h = _h(uid)
    resp = c.post("/api/dictation/grade", json={"word": "徘徊", "answer": "徘徊"}, headers=h)
    assert resp.json()["correct"] is True
    resp = c.post("/api/dictation/grade", json={"word": "徘徊", "answer": "排回"}, headers=h)
    assert resp.json()["correct"] is False


def test_dictation_complete_awards_points(setup_db):
    uid = _seed_user()
    resp = _client().post("/api/dictation/complete", json={"user_id": uid, "correct": 5, "wrong": 1},
                          headers=_h(uid))
    assert resp.status_code == 200
    assert resp.json()["points_awarded"] > 0


def test_review_generate_questions(setup_db):
    from app.models import KnowledgePoint
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(KnowledgePoint(subject="英语", category="语法", content="动词第三人称单数加 s"))
    s.commit(); s.close()
    uid = _seed_user()
    resp = _client().get("/api/review/questions?subject=英语", headers=_h(uid))
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_review_wrong_to_mistake(setup_db):
    uid = _seed_user()
    resp = _client().post("/api/review/submit", json={"user_id": uid, "question": "go 的第三人称单数", "your_answer": "gos", "correct_answer": "goes", "source_type": "review"},
                          headers=_h(uid))
    assert resp.status_code == 200
    from app.models import Mistake
    from app.database import SessionLocal
    s = SessionLocal()
    assert s.query(Mistake).count() >= 1
    s.close()


def test_review_wrong_to_mistake_scoped_to_bucket(setup_db):
    from app.services.bucket_service import ensure_bucket
    from app.models import Mistake
    from app.database import SessionLocal
    s = SessionLocal()
    p = make_account(s, "p_rw", "parent")
    uid = make_account(s, "k_rw", "child", parent=p).id
    s.commit()
    b = ensure_bucket(s, uid)
    b_id = b.id
    s.close()

    resp = _client().post("/api/review/submit", json={
        "user_id": uid, "question": "go 的第三人称单数",
        "your_answer": "gos", "correct_answer": "goes", "source_type": "review",
    }, headers=_h(uid))
    assert resp.status_code == 200
    s = SessionLocal()
    m = s.query(Mistake).filter_by(user_id=uid).first()
    assert m is not None
    assert m.bucket_id == b_id  # 错题挂在 active 桶，而非 NULL 命名空间
    s.close()


def test_listening_material(setup_db):
    uid = _seed_user()
    resp = _client().get(f"/api/listening/material?user_id={uid}", headers=bound_child_headers(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data and "questions" in data


def test_listening_material_updates_empty_pregenerated_task(setup_db):
    import json
    from datetime import date
    from app.models import Task
    from app.database import SessionLocal
    # 预生成一条 content 为空的任务（模拟损坏/空数据）
    s = SessionLocal()
    p = make_account(s, "p_lm_u", "parent")
    uid = make_account(s, "k_lm_u", "child", parent=p).id
    s.add(Task(
        user_id=uid, subject="英语", date=date.today(), task_type="listening",
        title="英语听力练习", content_status="published", content="",
    ))
    s.commit(); s.close()

    resp = _client().get(f"/api/listening/material?user_id={uid}", headers=bound_child_headers(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data and "questions" in data

    # 落库的记录应被原地更新（仍只有一条，且 content 已非空）
    s = SessionLocal()
    rows = s.query(Task).filter_by(user_id=uid, subject="英语", date=date.today(), task_type="listening").all()
    assert len(rows) == 1
    assert rows[0].content
    s.close()


def test_listening_material_reads_pregenerated_task(setup_db):
    import json
    from datetime import date
    from app.models import Task
    from app.database import SessionLocal
    s = SessionLocal()
    p = make_account(s, "p_lm_r", "parent")
    uid = make_account(s, "k_lm_r", "child", parent=p).id
    s.add(Task(
        user_id=uid, subject="英语", date=date.today(), task_type="listening",
        title="英语听力练习", content_status="published",
        content=json.dumps({"dialogue": "A: Hi B: Hello", "question": "B 说了什么？", "answer": "Hello"}, ensure_ascii=False),
    ))
    s.commit(); s.close()

    resp = _client().get(f"/api/listening/material?user_id={uid}", headers=bound_child_headers(uid))
    data = resp.json()
    assert data["text"] == "A: Hi B: Hello"
    assert data["questions"][0]["answer"] == "Hello"


def test_reading_material(setup_db):
    from app.models import Text, UserDocument
    from app.database import SessionLocal
    s = SessionLocal()
    lesson = make_lesson(s)
    lid = lesson.id
    s.add(Text(lesson_id=lid, content="白鹭是一首精巧的诗。"))
    p = make_account(s, "p_rm", "parent")
    uid = make_account(s, "k_rm", "child", parent=p).id
    s.add(UserDocument(user_id=uid, document_id=lesson.document_id))
    s.commit(); s.close()
    resp = _client().get(f"/api/reading/material?lesson_id={lid}&user_id={uid}", headers=_h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data and "questions" in data


def test_dictation_grade_updates_word_mastery(setup_db):
    """答对累计 correct_count 并排到后面；答错标记薄弱。"""
    from app.models import Lesson, WordBank, WordMastery
    from app.database import SessionLocal
    s = SessionLocal()
    from app.models import Lesson as Ls, UserDocument as UD
    lid = make_lesson(s, audit_status="approved").id
    p = make_account(s, "p_wbm", "parent")
    uid = make_account(s, "k_wbm", "child", parent=p).id
    s.add(UD(user_id=uid, document_id=s.get(Ls, lid).document_id))
    wb = WordBank(lesson_id=lid, subject="语文", word="徘徊", extra="pái huái")
    s.add(wb); s.flush()
    wid = wb.id
    s.commit(); s.close()

    c = _client()
    h = _h(uid)
    # 答错：mistake_count=1, is_weak=True
    c.post("/api/dictation/grade", json={"word_id": wid, "word": "徘徊", "answer": "排回"}, headers=h)
    s = SessionLocal()
    m = s.query(WordMastery).filter_by(word_bank_id=wid).first()
    assert m is not None and m.mistake_count == 1 and m.is_weak is True
    # 答对两次：correct_count 累计
    c.post("/api/dictation/grade", json={"word_id": wid, "word": "徘徊", "answer": "徘徊"}, headers=h)
    c.post("/api/dictation/grade", json={"word_id": wid, "word": "徘徊", "answer": "徘徊"}, headers=h)
    # MySQL 默认 REPEATABLE READ：结束本会话的读快照才能看到接口写入的新值（expire_all 不够）
    s.rollback()
    m = s.query(WordMastery).filter_by(word_bank_id=wid).first()
    assert m.correct_count == 2 and m.next_review_at is not None
    s.close()


def test_learning_lessons_returns_current_flag(setup_db):
    from app.models import Lesson, LearningProgress, PdfDocument
    from app.database import SessionLocal
    s = SessionLocal()
    doc = PdfDocument(filename="语文教材.pdf", subject="语文", storage_path="/x.pdf")
    s.add(doc); s.flush()
    l1 = Lesson(document_id=doc.id, subject="语文", title="第1课", start_page=1, end_page=3, audit_status="approved")
    l2 = Lesson(document_id=doc.id, subject="语文", title="第2课", start_page=4, end_page=6, audit_status="approved")
    s.add_all([l1, l2]); s.flush()
    l1_id, l2_id = l1.id, l2.id
    p = make_account(s, "p_ll", "parent")
    uid = make_account(s, "k_ll", "child", parent=p).id
    from app.models import UserDocument
    s.add(UserDocument(user_id=uid, document_id=doc.id))
    s.add(LearningProgress(user_id=uid, subject="语文", current_lesson_id=l2_id))
    s.commit(); s.close()

    resp = _client().get(f"/api/learning/lessons?user_id={uid}&subject=语文", headers=_h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    by_id = {d["id"]: d for d in data}
    assert by_id[l1_id]["is_current"] is False
    assert by_id[l2_id]["is_current"] is True
    assert by_id[l2_id]["document_name"] == "语文教材.pdf"


def test_assignment_grade_passes_advances_progress(setup_db):
    from app.models import Lesson, LearningProgress
    from app.database import SessionLocal
    s = SessionLocal()
    uid, l1_id, l2_id = _seed_two_lessons(s)
    s.close()

    # 正确率 >= 默认阈值 0.6 → 通过，推进到下一课
    resp = _client().post("/api/learning/assignment/grade",
                          json={"user_id": uid, "lesson_id": l1_id, "subject": "语文",
                                "answers": [
                                    {"knowledge_point_id": None, "is_correct": True},
                                    {"knowledge_point_id": None, "is_correct": True},
                                    {"knowledge_point_id": None, "is_correct": True},
                                    {"knowledge_point_id": None, "is_correct": True},
                                    {"knowledge_point_id": None, "is_correct": False},
                                ]}, headers=_h(uid))
    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is True

    s = SessionLocal()
    prog = s.query(LearningProgress).filter_by(user_id=uid, subject="语文").first()
    assert prog.current_lesson_id == l2_id
    s.close()


def test_assignment_grade_below_threshold_does_not_advance(setup_db):
    from app.models import Lesson, LearningProgress
    from app.database import SessionLocal
    s = SessionLocal()
    uid, l1_id, _ = _seed_two_lessons(s)
    s.close()

    resp = _client().post("/api/learning/assignment/grade",
                          json={"user_id": uid, "lesson_id": l1_id, "subject": "语文",
                                "answers": [
                                    {"knowledge_point_id": None, "is_correct": True},
                                    {"knowledge_point_id": None, "is_correct": False},
                                    {"knowledge_point_id": None, "is_correct": False},
                                    {"knowledge_point_id": None, "is_correct": False},
                                    {"knowledge_point_id": None, "is_correct": False},
                                ]}, headers=_h(uid))
    body = resp.json()
    assert body["passed"] is False

    s = SessionLocal()
    prog = s.query(LearningProgress).filter_by(user_id=uid, subject="语文").first()
    assert prog.current_lesson_id == l1_id
    s.close()


def test_assignment_grade_records_knowledge_mastery(setup_db):
    """判分后对每道题的知识点落 KnowledgeMastery（无论整体通过与否）。"""
    from app.models import Lesson, LearningProgress, KnowledgePoint, KnowledgeMastery
    from app.database import SessionLocal
    s = SessionLocal()
    from app.models import Lesson, UserDocument
    p = make_account(s, "p_km", "parent")
    uid = make_account(s, "k_km", "child", parent=p).id
    l1_id = make_lesson(s, audit_status="approved").id
    s.add(UserDocument(user_id=uid, document_id=s.get(Lesson, l1_id).document_id))
    kp = KnowledgePoint(lesson_id=l1_id, subject="语文", category="修辞", content="比喻")
    s.add(kp); s.flush()
    kp_id = kp.id
    s.commit(); s.close()

    # 未达标（2/5 = 0.4 < 0.6），但知识点掌握度仍要落
    resp = _client().post("/api/learning/assignment/grade",
                          json={"user_id": uid, "lesson_id": l1_id, "subject": "语文",
                                "answers": [
                                    {"knowledge_point_id": kp_id, "is_correct": True},
                                    {"knowledge_point_id": kp_id, "is_correct": False},
                                    {"knowledge_point_id": None, "is_correct": False},
                                ]}, headers=_h(uid))
    body = resp.json()
    assert body["passed"] is False

    s = SessionLocal()
    m = s.query(KnowledgeMastery).filter_by(user_id=uid, knowledge_point_id=kp_id).first()
    assert m is not None
    assert m.attempts == "[true, false]"
    assert m.next_review_at is not None
    s.close()


def test_assignment_grade_with_items_returns_per_question_results(setup_db, monkeypatch):
    """传 items 时服务端判分，返回逐题对错、参考答案、讲解与阈值；未达标不推进。"""
    from app.models import Lesson, LearningProgress
    from app.database import SessionLocal
    s = SessionLocal()
    uid, l1_id, _ = _seed_two_lessons(s)
    s.close()

    monkeypatch.setattr("app.services.assignment.grade_assignment",
                        lambda db, items: [{"is_correct": i == 0, "feedback": f"讲解{i}"} for i in range(len(items))])
    items = [{"question": f"题{i}", "answer": f"答{i}", "student_answer": "x", "knowledge_point_id": None}
             for i in range(3)]
    body = _client().post("/api/learning/assignment/grade",
                          json={"user_id": uid, "lesson_id": l1_id, "subject": "语文", "items": items},
                          headers=_h(uid)).json()
    assert body["passed"] is False
    assert body["correct"] == 1 and body["total"] == 3
    assert body["threshold"] == 0.6
    assert [r["is_correct"] for r in body["results"]] == [True, False, False]
    assert body["results"][1]["answer"] == "答1" and body["results"][1]["feedback"] == "讲解1"

    s = SessionLocal()
    prog = s.query(LearningProgress).filter_by(user_id=uid, subject="语文").first()
    assert prog.current_lesson_id == l1_id
    s.close()


def test_assignment_returns_questions(setup_db):
    from app.models import Text
    from app.database import SessionLocal
    s = SessionLocal()
    from app.models import Lesson, UserDocument
    p = make_account(s, "p_aq", "parent")
    uid = make_account(s, "k_aq", "child", parent=p).id
    lid = make_lesson(s, audit_status="approved").id
    s.add(UserDocument(user_id=uid, document_id=s.get(Lesson, lid).document_id))
    s.add(Text(lesson_id=lid, content="白鹭是一首精巧的诗。"))
    s.commit(); s.close()

    resp = _client().post("/api/learning/assignment",
                          json={"user_id": uid, "lesson_id": lid, "subject": "语文"},
                          headers=_h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert "questions" in data
    assert len(data["questions"]) > 0


def test_dictation_complete_records_wrong_words(setup_db):
    from app.database import SessionLocal
    uid = _seed_user()
    resp = _client().post("/api/dictation/complete", json={
        "user_id": uid, "correct": 4, "wrong": 1,
        "wrong_words": [{"word": "矗立", "your_answer": "矗力"}],
    }, headers=_h(uid))
    assert resp.status_code == 200
    assert resp.json()["mistakes_recorded"] == 1
    from app.models import Mistake
    s = SessionLocal()
    assert s.query(Mistake).filter_by(source_type="dictation").count() == 1
    s.close()


def test_grade_handwriting_endpoint(setup_db):
    uid = _seed_user()
    # 视觉模型未配置/mock 异常时，接口返回空 results 而非 500
    resp = _client().post("/api/dictation/grade-handwriting", json={
        "user_id": uid,
        "words": [{"index": 0, "word": "箩"}],
        "image_base64": "",
    }, headers=_h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert data["results"] == []


def test_appeal_endpoint(setup_db):
    uid = _seed_user()
    resp = _client().post("/api/dictation/appeal", json={
        "user_id": uid, "word": "矗立", "reason": "我写的是对的",
    }, headers=_h(uid))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    from app.models import Mistake
    from app.database import SessionLocal
    s = SessionLocal()
    assert s.query(Mistake).filter_by(source_type="appeal").count() == 1
    s.close()
