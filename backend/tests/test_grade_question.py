from app.services.grade_question import grade_question, normalize_answer


def test_grade_single_choice():
    r = grade_question("choice", {"correct_index": 2}, {"selected_index": 2})
    assert r["is_correct"] is True


def test_grade_single_choice_wrong():
    r = grade_question("choice", {"correct_index": 2}, {"selected_index": 0})
    assert r["is_correct"] is False


def test_grade_multi_choice():
    r = grade_question("choice", {"correct_index": [0, 2]}, {"selected_index": [2, 0]})
    assert r["is_correct"] is True


def test_grade_fill_blank_normalized():
    r = grade_question("blank", {"blanks": ["春天", "播种"]}, {"blanks": [" 春天 ", "播种"]})
    assert r["is_correct"] is True


def test_grade_calculation():
    r = grade_question("blank", {"blanks": ["8"]}, {"blanks": ["8"]})
    assert r["is_correct"] is True


def test_grade_match():
    r = grade_question("match", {"pairs": [["A", "1"], ["B", "3"]]},
                       {"pairs": [["A", "1"], ["B", "3"]]})
    assert r["is_correct"] is True


def test_normalize_answer():
    assert normalize_answer("  Hello World ") == "helloworld"
    assert normalize_answer("苹果") == "苹果"
