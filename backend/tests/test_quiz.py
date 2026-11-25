from app.services.quiz import (
    VERDICT_CONFIRMED,
    VERDICT_EXPRESSION_WEAK,
    VERDICT_LUCKY,
    VERDICT_NOT_UNDERSTOOD,
    VERDICT_UNKNOWN,
    evidence_key,
    grade_answers,
    grade_verdict,
    quiz_system_prompt,
)


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
from app.models import User, PdfDocument, Lesson, Text, Quiz, ModelConfig, UserDocument
from conftest import make_account, bound_child_headers

client = TestClient(app)


def _seed_lesson():
    db = SessionLocal()
    for m in (Quiz, Text, Lesson, PdfDocument, User, ModelConfig):
        db.query(m).delete()
    db.commit()
    p = make_account(db, "p_qz", "parent")
    u = make_account(db, "孩子", "child", parent=p)
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l = Lesson(document_id=doc.id, subject="语文", title="第1课",
               start_page=1, end_page=2, extract_status="done", audit_status="approved")
    db.add(l); db.flush()
    db.add(Text(lesson_id=l.id, content="白鹭是一首精巧的诗。色素的配合，身段的大小，一切都很适宜。"))
    db.add(UserDocument(user_id=u.id, document_id=doc.id))
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit()
    return l.id, u.id


def test_generate_quiz_returns_503_when_ai_unconfigured(setup_db):
    lid, uid = _seed_lesson()
    h = bound_child_headers(uid)
    r = client.post("/api/quiz/generate", json={"lesson_id": lid}, headers=h)
    assert r.status_code == 503


def test_submit_quiz_expired_returns_409(setup_db):
    _, uid = _seed_lesson()
    h = bound_child_headers(uid)
    r = client.post("/api/quiz/submit", json={"quiz_id": 999999, "answers": []}, headers=h)
    assert r.status_code == 409


def test_submit_quiz_ignores_unknown_knowledge_point(setup_db):
    """AI 编造/已删除的知识点 id 不能落进外键列：错题照收，只是不关联知识点。"""
    from app.models import KnowledgeMastery, Mistake
    lid, uid = _seed_lesson()
    db = SessionLocal()
    q = {"id": "q1", "prompt": "白鹭像什么？", "choices": ["诗", "画", "歌", "书"],
         "correct_index": 0, "evidence": "白鹭是一首精巧的诗", "knowledge_point_id": 999}
    quiz = Quiz(lesson_id=lid, user_id=uid, questions=json.dumps([q], ensure_ascii=False))
    db.add(quiz); db.commit(); qid = quiz.id
    db.close()

    h = bound_child_headers(uid)
    r = client.post("/api/quiz/submit", json={"quiz_id": qid, "answers": [{"question_id": "q1", "selected_index": 1}]},
                    headers=h)
    assert r.status_code == 200
    assert r.json()["score"] == 0
    db = SessionLocal()
    assert db.query(KnowledgeMastery).count() == 0
    m = db.query(Mistake).filter_by(user_id=uid).one()
    assert m.knowledge_point_id is None and m.your_answer == "画"
    db.close()


def test_grade_verdict_confirmed_when_answer_and_evidence_correct():
    # 答案对、指出的句子就是支持答案的原文
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="弯弯的月亮像一条小船",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == VERDICT_CONFIRMED


def test_grade_verdict_lucky_when_answer_right_but_evidence_wrong():
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="小鸟在枝头唱歌",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == VERDICT_LUCKY


def test_grade_verdict_expression_weak_when_answer_wrong_but_evidence_right():
    # 这是最要紧的一态：理解到位、表达没到位
    assert grade_verdict(
        answer_correct=False,
        chosen_evidence="弯弯的月亮像一条小船。",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == VERDICT_EXPRESSION_WEAK


def test_grade_verdict_not_understood_when_both_wrong():
    assert grade_verdict(
        answer_correct=False,
        chosen_evidence="小鸟在枝头唱歌",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == VERDICT_NOT_UNDERSTOOD


def test_grade_verdict_unknown_when_no_evidence_provided():
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == VERDICT_UNKNOWN


def test_grade_verdict_unknown_when_question_has_no_evidence():
    # 题库题可能没 evidence，此时无法判出处
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="随便一句",
        correct_evidence="",
    ) == VERDICT_UNKNOWN


def test_grade_verdict_evidence_match_ignores_whitespace_and_punctuation_spacing():
    # 归一化后比较：换行、行号都不影响
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="弯弯的月亮\n像一条小船",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == VERDICT_CONFIRMED


def test_grade_verdict_evidence_match_allows_partial_sentence():
    # 孩子可能只点到句中的短语，只要归一化后是子串就算对
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="像一条小船",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == VERDICT_CONFIRMED


def test_grade_verdict_evidence_match_allows_chosen_longer_than_evidence():
    # 孩子点的句子比 evidence 片段更长，也算找对了地方
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="弯弯的月亮像一条小船，静静地停在夜空中。",
        correct_evidence="弯弯的月亮像一条小船",
    ) == VERDICT_CONFIRMED


def test_grade_verdict_unknown_when_evidence_normalizes_to_empty():
    # 只由空白与连字符组成的“出处”无法判定，应记未决而不是判错
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence=" - - ",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == VERDICT_UNKNOWN
