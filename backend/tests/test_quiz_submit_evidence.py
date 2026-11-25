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


def test_expression_weak_not_filed_into_mistake_book():
    """理解对、表达错不该进错题本（否则会触发「再刷同类题」）。"""
    from app.models import Mistake

    quiz_id, headers = _seed_quiz(_one_question())
    # 选错选项（1）但指对依据 → expression_weak
    client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 1, "evidence_sentence": EVIDENCE}],
    }, headers=headers)
    db = SessionLocal()
    try:
        assert db.query(Mistake).count() == 0
    finally:
        db.close()


def test_not_understood_is_filed_into_mistake_book():
    """真没懂（答案错、依据也错）仍要进错题本。"""
    from app.models import Mistake

    quiz_id, headers = _seed_quiz(_one_question())
    client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 1, "evidence_sentence": OTHER}],
    }, headers=headers)
    db = SessionLocal()
    try:
        assert db.query(Mistake).count() == 1
    finally:
        db.close()


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


def test_submit_pairs_results_by_question_id_not_submission_order():
    """客户端乱序提交时，判分必须按 question_id 对齐到题目，而不是按位置。

    旧实现用 zip(questions, results)，results 却是 req.answers 的顺序；
    乱序提交会把对错/出处写到错误的题目上。
    """
    questions = [
        {
            "id": "qa",
            "prompt": "第一题（正确答案是 A）",
            "choices": [EVIDENCE, OTHER, "云朵仿佛棉花糖。", "湖水很清很清。"],
            "correct_index": 0,
            "evidence": EVIDENCE,
        },
        {
            "id": "qb",
            "prompt": "第二题（正确答案是 B）",
            "choices": [OTHER, EVIDENCE, "云朵仿佛棉花糖。", "湖水很清很清。"],
            "correct_index": 1,
            "evidence": EVIDENCE,
        },
    ]
    quiz_id, headers = _seed_quiz(questions)
    # 按 qb、qa 的倒序提交；qa 答对且出处对，qb 答错且出处错。
    # 两题结果必须不同，否则交换两个相同结果无法暴露位置错配。
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [
            {"question_id": "qb", "selected_index": 0, "evidence_sentence": OTHER},
            {"question_id": "qa", "selected_index": 0, "evidence_sentence": EVIDENCE},
        ],
    }, headers=headers)
    assert r.status_code == 200
    assert r.json()["score"] == 1

    db = SessionLocal()
    try:
        rows = {row.question: row for row in
                db.query(AnswerRecord).filter_by(module="quiz").all()}
        assert len(rows) == 2
        assert rows["第一题（正确答案是 A）"].is_correct is True
        assert rows["第一题（正确答案是 A）"].evidence_text == EVIDENCE
        assert rows["第一题（正确答案是 A）"].evidence_ok is True
        assert rows["第二题（正确答案是 B）"].is_correct is False
        assert rows["第二题（正确答案是 B）"].evidence_text == OTHER
        assert rows["第二题（正确答案是 B）"].evidence_ok is False
    finally:
        db.close()


def test_verdict_evidence_ok_maps_each_verdict():
    from app.services.quiz import (
        VERDICT_CONFIRMED, VERDICT_EXPRESSION_WEAK, VERDICT_LUCKY,
        VERDICT_NOT_UNDERSTOOD, VERDICT_UNKNOWN, verdict_evidence_ok,
    )
    assert verdict_evidence_ok(VERDICT_CONFIRMED) is True
    assert verdict_evidence_ok(VERDICT_EXPRESSION_WEAK) is True
    assert verdict_evidence_ok(VERDICT_LUCKY) is False
    assert verdict_evidence_ok(VERDICT_NOT_UNDERSTOOD) is False
    assert verdict_evidence_ok(VERDICT_UNKNOWN) is None
