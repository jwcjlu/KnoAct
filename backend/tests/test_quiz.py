from app.services.quiz import evidence_key, grade_answers, quiz_system_prompt


def test_quiz_system_prompt_english():
    assert "English" in quiz_system_prompt("英语")
    assert "中文" in quiz_system_prompt("语文")


def test_evidence_key_strips_line_numbers_and_hyphens():
    # 抄自 DeepTutor 的行为：行号 + 连字符断词都不影响子串判定
    assert evidence_key("fall short in\n3\ndelivering") == "fallshortindelivering"


def test_evidence_key_strips_hyphen_broken_words():
    assert evidence_key("DeepTu-\n4\ntor") == "deeptutor"


def test_evidence_substring_match():
    context = evidence_key("白鹭是一首精巧的诗")
    assert evidence_key("精巧的诗") in context
    assert evidence_key("不存在的句子") not in context


def test_grade_answers_full_correct():
    questions = [
        {"id": "q1", "correct_index": 0, "choices": ["a", "b", "c", "d"]},
        {"id": "q2", "correct_index": 2, "choices": ["a", "b", "c", "d"]},
    ]
    answers = [{"question_id": "q1", "selected_index": 0},
               {"question_id": "q2", "selected_index": 2}]
    results = grade_answers(questions, answers)
    assert [r["is_correct"] for r in results] == [True, True]


def test_grade_answers_partial():
    questions = [{"id": "q1", "correct_index": 0, "choices": ["a", "b", "c", "d"]},
                 {"id": "q2", "correct_index": 1, "choices": ["a", "b", "c", "d"]}]
    answers = [{"question_id": "q1", "selected_index": 1},
               {"question_id": "q2", "selected_index": 1}]
    results = grade_answers(questions, answers)
    assert [r["is_correct"] for r in results] == [False, True]


def test_grade_answers_rejects_out_of_range_index():
    questions = [{"id": "q1", "correct_index": 0, "choices": ["a", "b", "c", "d"]}]
    answers = [{"question_id": "q1", "selected_index": 9}]
    results = grade_answers(questions, answers)
    assert results[0]["is_correct"] is False


import json
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User, PdfDocument, Lesson, Text, Quiz, ModelConfig

client = TestClient(app)


def _seed_lesson():
    db = SessionLocal()
    for m in (Quiz, Text, Lesson, PdfDocument, User, ModelConfig):
        db.query(m).delete()
    db.commit()
    u = User(name="孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l = Lesson(document_id=doc.id, subject="语文", title="第1课",
               start_page=1, end_page=2, extract_status="done", audit_status="approved")
    db.add(l); db.flush()
    db.add(Text(lesson_id=l.id, content="白鹭是一首精巧的诗。色素的配合，身段的大小，一切都很适宜。"))
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit()
    return l.id


def test_generate_quiz_returns_503_when_ai_unconfigured(setup_db):
    lid = _seed_lesson()
    r = client.post("/api/quiz/generate", json={"lesson_id": lid})
    assert r.status_code == 503


def test_submit_quiz_expired_returns_409(setup_db):
    r = client.post("/api/quiz/submit", json={"quiz_id": 999999, "answers": []})
    assert r.status_code == 409


def test_submit_quiz_ignores_unknown_knowledge_point(setup_db):
    """AI 编造/已删除的知识点 id 不能落进外键列：错题照收，只是不关联知识点。"""
    from app.models import KnowledgeMastery, Mistake
    lid = _seed_lesson()
    db = SessionLocal()
    uid = db.query(User).first().id
    q = {"id": "q1", "prompt": "白鹭像什么？", "choices": ["诗", "画", "歌", "书"],
         "correct_index": 0, "evidence": "白鹭是一首精巧的诗", "knowledge_point_id": 999}
    quiz = Quiz(lesson_id=lid, user_id=uid, questions=json.dumps([q], ensure_ascii=False))
    db.add(quiz); db.commit(); qid = quiz.id
    db.close()

    r = client.post("/api/quiz/submit", json={"quiz_id": qid, "answers": [{"question_id": "q1", "selected_index": 1}]})
    assert r.status_code == 200
    assert r.json()["score"] == 0
    db = SessionLocal()
    assert db.query(KnowledgeMastery).count() == 0
    m = db.query(Mistake).filter_by(user_id=uid).one()
    assert m.knowledge_point_id is None and m.your_answer == "画"
    db.close()
