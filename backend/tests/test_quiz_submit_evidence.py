"""答 + 指：/api/quiz/submit 接收 evidence_sentence 并返回 verdict。"""
import json

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    AnswerRecord,
    Lesson,
    ModelConfig,
    PdfDocument,
    Quiz,
    Text,
    User,
    UserDocument,
)
from conftest import parent_child

client = TestClient(app)

EVIDENCE = "弯弯的月亮像一条小船。"
OTHER = "小鸟在枝头唱歌。"


def _seed_quiz(questions):
    """建一套最小可提交的测验，返回 (quiz_id, headers)。

    questions 里每题需含 id / prompt / choices / correct_index / evidence。
    """
    db = SessionLocal()
    for m in (AnswerRecord, Quiz, Text, Lesson, UserDocument, PdfDocument, User, ModelConfig):
        db.query(m).delete()
    db.commit()
    _p, u, _ph, child_h = parent_child(db, "ev")
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc)
    db.flush()
    lesson = Lesson(document_id=doc.id, subject="语文", title="第1课",
                    start_page=1, end_page=1)
    db.add(lesson)
    db.flush()
    db.add(Text(lesson_id=lesson.id, content=f"{EVIDENCE}\n{OTHER}"))
    db.add(UserDocument(user_id=u.id, document_id=doc.id))
    quiz = Quiz(lesson_id=lesson.id, user_id=u.id,
                questions=json.dumps(questions, ensure_ascii=False))
    db.add(quiz)
    db.commit()
    quiz_id = quiz.id
    db.close()
    return quiz_id, child_h


def _one_question():
    return [{
        "id": "q1",
        "prompt": "哪一句用了比喻？",
        "choices": [EVIDENCE, OTHER, "云朵仿佛棉花糖。", "湖水很清很清。"],
        "correct_index": 0,
        "evidence": EVIDENCE,
    }]


def test_submit_returns_confirmed_when_answer_and_evidence_agree():
    quiz_id, headers = _seed_quiz(_one_question())
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 0, "evidence_sentence": EVIDENCE}],
    }, headers=headers)
    assert r.status_code == 200
    row = r.json()["answers"][0]
    assert row["is_correct"] is True
    assert row["verdict"] == "confirmed"
    assert row["evidence_ok"] is True


def test_submit_returns_lucky_when_answer_right_but_evidence_wrong():
    quiz_id, headers = _seed_quiz(_one_question())
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 0, "evidence_sentence": OTHER}],
    }, headers=headers)
    assert r.status_code == 200
    row = r.json()["answers"][0]
    assert row["is_correct"] is True
    assert row["verdict"] == "lucky"
    assert row["evidence_ok"] is False


def test_submit_returns_expression_weak_when_answer_wrong_but_evidence_right():
    quiz_id, headers = _seed_quiz(_one_question())
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 1, "evidence_sentence": EVIDENCE}],
    }, headers=headers)
    assert r.status_code == 200
    row = r.json()["answers"][0]
    assert row["is_correct"] is False
    assert row["verdict"] == "expression_weak"
    assert row["evidence_ok"] is True


def test_submit_returns_not_understood_when_both_wrong():
    quiz_id, headers = _seed_quiz(_one_question())
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 1, "evidence_sentence": OTHER}],
    }, headers=headers)
    assert r.status_code == 200
    assert r.json()["answers"][0]["verdict"] == "not_understood"


def test_submit_without_evidence_still_works_and_reports_unknown():
    # 旧客户端不传 evidence_sentence，判分必须与以前完全一致
    quiz_id, headers = _seed_quiz(_one_question())
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 0}],
    }, headers=headers)
    assert r.status_code == 200
    row = r.json()["answers"][0]
    assert row["is_correct"] is True
    assert row["verdict"] == "unknown"
    assert row["evidence_ok"] is None


def test_submit_persists_evidence_to_answer_record():
    quiz_id, headers = _seed_quiz(_one_question())
    client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 0, "evidence_sentence": OTHER}],
    }, headers=headers)
    db = SessionLocal()
    try:
        row = db.query(AnswerRecord).filter_by(module="quiz").order_by(AnswerRecord.id.desc()).first()
        assert row is not None
        assert row.evidence_text == OTHER
        assert row.evidence_ok is False
    finally:
        db.close()


def test_submit_score_unchanged_by_evidence():
    # 出处不参与对错：选了正确答案就该算对
    quiz_id, headers = _seed_quiz(_one_question())
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 0, "evidence_sentence": OTHER}],
    }, headers=headers)
    assert r.json()["score"] == 1
    assert r.json()["total"] == 1
