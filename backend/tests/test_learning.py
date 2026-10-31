from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.learning import router as learning_router


def _client():
    app = FastAPI()
    app.include_router(learning_router)
    return TestClient(app)


def test_dictation_pick_words(setup_db):
    from app.models import Lesson, WordBank
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(Lesson(document_id=1, subject="语文", title="第1课", start_page=1, end_page=3, audit_status="approved"))
    s.flush()
    lid = s.query(Lesson).first().id
    s.add(WordBank(lesson_id=lid, subject="语文", word="徘徊", extra="pái huái"))
    s.add(WordBank(lesson_id=lid, subject="语文", word="矗立", extra="chù lì"))
    s.commit(); s.close()
    resp = _client().get("/api/dictation/words?user_id=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_dictation_grade(setup_db):
    c = _client()
    resp = c.post("/api/dictation/grade", json={"word": "徘徊", "answer": "徘徊"})
    assert resp.json()["correct"] is True
    resp = c.post("/api/dictation/grade", json={"word": "徘徊", "answer": "排回"})
    assert resp.json()["correct"] is False


def test_dictation_complete_awards_points(setup_db):
    from app.models import User
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(User(name="晨晨", role="child")); s.commit(); s.close()
    resp = _client().post("/api/dictation/complete", json={"user_id": 1, "correct": 5, "wrong": 1})
    assert resp.status_code == 200
    assert resp.json()["points_awarded"] > 0


def test_review_generate_questions(setup_db):
    from app.models import KnowledgePoint
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(KnowledgePoint(subject="英语", category="语法", content="动词第三人称单数加 s"))
    s.commit(); s.close()
    resp = _client().get("/api/review/questions?subject=英语")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_review_wrong_to_mistake(setup_db):
    resp = _client().post("/api/review/submit", json={"user_id": 1, "question": "go 的第三人称单数", "your_answer": "gos", "correct_answer": "goes", "source_type": "review"})
    assert resp.status_code == 200
    from app.models import Mistake
    from app.database import SessionLocal
    s = SessionLocal()
    assert s.query(Mistake).count() >= 1
    s.close()


def test_listening_material(setup_db):
    resp = _client().get("/api/listening/material?user_id=1")
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
    s.add(Task(
        user_id=1, subject="英语", date=date.today(), task_type="listening",
        title="英语听力练习", content_status="published", content="",
    ))
    s.commit(); s.close()

    resp = _client().get("/api/listening/material?user_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data and "questions" in data

    # 落库的记录应被原地更新（仍只有一条，且 content 已非空）
    s = SessionLocal()
    rows = s.query(Task).filter_by(user_id=1, subject="英语", date=date.today(), task_type="listening").all()
    assert len(rows) == 1
    assert rows[0].content
    s.close()


def test_listening_material_reads_pregenerated_task(setup_db):
    import json
    from datetime import date
    from app.models import Task
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(Task(
        user_id=1, subject="英语", date=date.today(), task_type="listening",
        title="英语听力练习", content_status="published",
        content=json.dumps({"dialogue": "A: Hi B: Hello", "question": "B 说了什么？", "answer": "Hello"}, ensure_ascii=False),
    ))
    s.commit(); s.close()

    resp = _client().get("/api/listening/material?user_id=1")
    data = resp.json()
    assert data["text"] == "A: Hi B: Hello"
    assert data["questions"][0]["answer"] == "Hello"


def test_reading_material(setup_db):
    from app.models import Text
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(Text(lesson_id=1, content="白鹭是一首精巧的诗。"))
    s.commit(); s.close()
    resp = _client().get("/api/reading/material?lesson_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data and "questions" in data


def test_dictation_grade_updates_word_mastery(setup_db):
    """答对累计 correct_count 并排到后面；答错标记薄弱。"""
    from app.models import Lesson, WordBank, WordMastery
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(Lesson(document_id=1, subject="语文", title="第1课", start_page=1, end_page=3, audit_status="approved"))
    s.flush()
    lid = s.query(Lesson).first().id
    wb = WordBank(lesson_id=lid, subject="语文", word="徘徊", extra="pái huái")
    s.add(wb); s.flush()
    wid = wb.id
    s.commit(); s.close()

    c = _client()
    # 答错：mistake_count=1, is_weak=True
    c.post("/api/dictation/grade", json={"word_id": wid, "word": "徘徊", "answer": "排回"})
    s = SessionLocal()
    m = s.query(WordMastery).filter_by(word_bank_id=wid).first()
    assert m is not None and m.mistake_count == 1 and m.is_weak is True
    # 答对两次：correct_count 累计
    c.post("/api/dictation/grade", json={"word_id": wid, "word": "徘徊", "answer": "徘徊"})
    c.post("/api/dictation/grade", json={"word_id": wid, "word": "徘徊", "answer": "徘徊"})
    s.expire_all()
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
    s.add(LearningProgress(user_id=1, subject="语文", current_lesson_id=l2_id))
    s.commit(); s.close()

    resp = _client().get("/api/learning/lessons?user_id=1&subject=语文")
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
    l1 = Lesson(document_id=1, subject="语文", title="第1课", start_page=1, end_page=3, audit_status="approved")
    l2 = Lesson(document_id=1, subject="语文", title="第2课", start_page=4, end_page=6, audit_status="approved")
    s.add_all([l1, l2]); s.flush()
    l1_id, l2_id = l1.id, l2.id
    s.add(LearningProgress(user_id=1, subject="语文", current_lesson_id=l1_id))
    s.commit(); s.close()

    # 正确率 >= 默认阈值 0.6 → 通过，推进到下一课
    resp = _client().post("/api/learning/assignment/grade",
                          json={"user_id": 1, "lesson_id": l1_id, "subject": "语文",
                                "answers": [
                                    {"knowledge_point_id": None, "is_correct": True},
                                    {"knowledge_point_id": None, "is_correct": True},
                                    {"knowledge_point_id": None, "is_correct": True},
                                    {"knowledge_point_id": None, "is_correct": True},
                                    {"knowledge_point_id": None, "is_correct": False},
                                ]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is True

    s = SessionLocal()
    prog = s.query(LearningProgress).filter_by(user_id=1, subject="语文").first()
    assert prog.current_lesson_id == l2_id
    s.close()


def test_assignment_grade_below_threshold_does_not_advance(setup_db):
    from app.models import Lesson, LearningProgress
    from app.database import SessionLocal
    s = SessionLocal()
    l1 = Lesson(document_id=1, subject="语文", title="第1课", start_page=1, end_page=3, audit_status="approved")
    l2 = Lesson(document_id=1, subject="语文", title="第2课", start_page=4, end_page=6, audit_status="approved")
    s.add_all([l1, l2]); s.flush()
    l1_id = l1.id
    s.add(LearningProgress(user_id=1, subject="语文", current_lesson_id=l1_id))
    s.commit(); s.close()

    resp = _client().post("/api/learning/assignment/grade",
                          json={"user_id": 1, "lesson_id": l1_id, "subject": "语文",
                                "answers": [
                                    {"knowledge_point_id": None, "is_correct": True},
                                    {"knowledge_point_id": None, "is_correct": False},
                                    {"knowledge_point_id": None, "is_correct": False},
                                    {"knowledge_point_id": None, "is_correct": False},
                                    {"knowledge_point_id": None, "is_correct": False},
                                ]})
    body = resp.json()
    assert body["passed"] is False

    s = SessionLocal()
    prog = s.query(LearningProgress).filter_by(user_id=1, subject="语文").first()
    assert prog.current_lesson_id == l1_id
    s.close()


def test_assignment_grade_records_knowledge_mastery(setup_db):
    """判分后对每道题的知识点落 KnowledgeMastery（无论整体通过与否）。"""
    from app.models import Lesson, LearningProgress, KnowledgePoint, KnowledgeMastery
    from app.database import SessionLocal
    s = SessionLocal()
    l1 = Lesson(document_id=1, subject="语文", title="第1课", start_page=1, end_page=3, audit_status="approved")
    s.add(l1); s.flush()
    l1_id = l1.id
    kp = KnowledgePoint(lesson_id=l1_id, subject="语文", category="修辞", content="比喻")
    s.add(kp); s.flush()
    kp_id = kp.id
    s.commit(); s.close()

    # 未达标（2/5 = 0.4 < 0.6），但知识点掌握度仍要落
    resp = _client().post("/api/learning/assignment/grade",
                          json={"user_id": 1, "lesson_id": l1_id, "subject": "语文",
                                "answers": [
                                    {"knowledge_point_id": kp_id, "is_correct": True},
                                    {"knowledge_point_id": kp_id, "is_correct": False},
                                    {"knowledge_point_id": None, "is_correct": False},
                                ]})
    body = resp.json()
    assert body["passed"] is False

    s = SessionLocal()
    m = s.query(KnowledgeMastery).filter_by(user_id=1, knowledge_point_id=kp_id).first()
    assert m is not None
    assert m.attempts == "[true, false]"
    assert m.next_review_at is not None
    s.close()


def test_assignment_returns_questions(setup_db):
    from app.models import Lesson, Text
    from app.database import SessionLocal
    s = SessionLocal()
    l = Lesson(document_id=1, subject="语文", title="第1课", start_page=1, end_page=3, audit_status="approved")
    s.add(l); s.flush()
    lid = l.id
    s.add(Text(lesson_id=lid, content="白鹭是一首精巧的诗。"))
    s.commit(); s.close()

    resp = _client().post("/api/learning/assignment",
                          json={"user_id": 1, "lesson_id": lid, "subject": "语文"})
    assert resp.status_code == 200
    data = resp.json()
    assert "questions" in data
    assert len(data["questions"]) > 0


def test_dictation_complete_records_wrong_words(setup_db):
    from app.models import User
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(User(name="晨晨", role="child")); s.commit(); s.close()
    resp = _client().post("/api/dictation/complete", json={
        "user_id": 1, "correct": 4, "wrong": 1,
        "wrong_words": [{"word": "矗立", "your_answer": "矗力"}],
    })
    assert resp.status_code == 200
    assert resp.json()["mistakes_recorded"] == 1
    from app.models import Mistake
    s = SessionLocal()
    assert s.query(Mistake).filter_by(source_type="dictation").count() == 1
    s.close()


def test_grade_handwriting_endpoint(setup_db):
    # 视觉模型未配置/mock 异常时，接口返回空 results 而非 500
    resp = _client().post("/api/dictation/grade-handwriting", json={
        "user_id": 1,
        "words": [{"index": 0, "word": "箩"}],
        "image_base64": "",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert data["results"] == []


def test_appeal_endpoint(setup_db):
    resp = _client().post("/api/dictation/appeal", json={
        "user_id": 1, "word": "矗立", "reason": "我写的是对的",
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    from app.models import Mistake
    from app.database import SessionLocal
    s = SessionLocal()
    assert s.query(Mistake).filter_by(source_type="appeal").count() == 1
    s.close()
