from app.services.quiz import evidence_key, grade_answers


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
