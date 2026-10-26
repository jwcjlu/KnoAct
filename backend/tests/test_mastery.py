from pytest import approx

from app.services.mastery import compute_mastery, grade_answer, is_mastered, GATE


def test_compute_mastery_empty_is_zero():
    assert compute_mastery([]) == 0.0


def test_compute_mastery_single_correct_is_capped_at_half():
    assert compute_mastery([True]) == 0.5


def test_compute_mastery_two_correct_capped_at_point_eight():
    assert compute_mastery([True, True]) == 0.8


def test_compute_mastery_recovers_after_mistakes():
    assert compute_mastery([False, True, True, True]) == approx(0.8)


def test_compute_mastery_three_plus_correct_reaches_gate():
    assert compute_mastery([True, True, True]) >= GATE


def test_grade_answer_choice_normalized():
    assert grade_answer("A", "A", "choice") is True
    assert grade_answer("a b", "ab", "choice") is True
    assert grade_answer("A", "B", "choice") is False


def test_grade_answer_short_exact_or_clearly_wrong():
    assert grade_answer("白鹭", "白鹭", "short") is True
    assert grade_answer("完全不同的答案", "白鹭", "short") is False
