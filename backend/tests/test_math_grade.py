# backend/tests/test_math_grade.py
"""按 answer_kind 分派判分：number / numeric_list / symbol / choice / photo / text。"""
import pytest

from app.services.math_grade import grade_by_answer_kind


def test_number_uses_math_answer_tolerance():
    r = grade_by_answer_kind(None, answer_kind="number", answer="13.4",
                             student_answer="13.40")
    assert r["is_correct"] is True
    r2 = grade_by_answer_kind(None, answer_kind="number", answer="13.4",
                              student_answer="13.5")
    assert r2["is_correct"] is False


def test_number_empty_answer_is_pending():
    r = grade_by_answer_kind(None, answer_kind="number", answer="",
                             student_answer="5")
    assert r["is_correct"] is None
    assert r["ai_status"] == "pending"


def test_numeric_list_requires_all_blanks():
    r = grade_by_answer_kind(
        None, answer_kind="numeric_list", answer="1.2, 1.44",
        answer_json={"blanks": ["1.2", "1.44"]},
        blanks=["1.2", "1.44"],
    )
    assert r["is_correct"] is True

    r2 = grade_by_answer_kind(
        None, answer_kind="numeric_list", answer="1.2, 1.44",
        answer_json={"blanks": ["1.2", "1.44"]},
        blanks=["1.2", "1.45"],
    )
    assert r2["is_correct"] is False


def test_numeric_list_wrong_count_is_false():
    r = grade_by_answer_kind(
        None, answer_kind="numeric_list", answer="1.2, 1.44",
        answer_json={"blanks": ["1.2", "1.44"]},
        blanks=["1.2"],
    )
    assert r["is_correct"] is False


@pytest.mark.parametrize("student", [">", "＞", " > "])
def test_symbol_normalizes_fullwidth_and_space(student):
    r = grade_by_answer_kind(None, answer_kind="symbol", answer=">",
                             student_answer=student)
    assert r["is_correct"] is True


def test_symbol_mismatch():
    r = grade_by_answer_kind(None, answer_kind="symbol", answer=">",
                             student_answer="<")
    assert r["is_correct"] is False


def test_choice_compares_index():
    r = grade_by_answer_kind(
        None, answer_kind="choice", answer="B",
        answer_json={"correct_index": 1}, student_answer="1",
    )
    assert r["is_correct"] is True


def test_text_defers_to_caller():
    """text 交给既有的主观题判分，这里返回 None 而不是瞎判。"""
    r = grade_by_answer_kind(None, answer_kind="text", answer="参考",
                             student_answer="孩子写的")
    assert r["is_correct"] is None
    assert r["ai_status"] == "pending"


def test_photo_without_bytes_is_pending():
    r = grade_by_answer_kind(None, answer_kind="photo", answer="13.4",
                             photo_bytes=None)
    assert r["is_correct"] is None
    assert r["ai_status"] == "pending"


def test_photo_uses_vision_grader(monkeypatch):
    import app.services.math_grade as mg

    monkeypatch.setattr(mg, "grade_math_work_photo", lambda db, img, q, exp: {
        "final_answer": exp, "steps_plausible": True, "confidence": 0.9,
        "reason": "步骤正确", "ai_status": "ok", "ai_correct": True,
    })
    r = mg.grade_by_answer_kind(None, answer_kind="photo", answer="13.4",
                                question="8.9+4.5", photo_bytes=b"img")
    assert r["is_correct"] is True
    assert r["steps_plausible"] is True
    assert r["final_answer"] == "13.4"


def test_unknown_answer_kind_falls_back_to_text():
    r = grade_by_answer_kind(None, answer_kind="no_such", answer="x",
                             student_answer="y")
    assert r["is_correct"] is None

def test_choice_with_non_dict_answer_json_does_not_raise():
    """answer_json 来自 DB，不保证是 dict。必须降级为待判，而不是抛异常。"""
    for bad in ("", "not-a-dict", [], 0):
        r = grade_by_answer_kind(None, answer_kind="choice", answer="B",
                                 answer_json=bad, student_answer="0")
        assert r["is_correct"] is None
        assert r["ai_status"] == "pending"


def test_photo_pending_review_is_not_a_wrong_answer(monkeypatch):
    """AI 没把握（pending_review）不能判成错，否则会污染错题本。"""
    import app.services.math_grade as mg

    monkeypatch.setattr(mg, "grade_math_work_photo", lambda db, img, q, exp: {
        "final_answer": "", "steps_plausible": False, "confidence": 0.4,
        "reason": "看不清", "ai_status": "pending_review", "ai_correct": False,
    })
    r = mg.grade_by_answer_kind(None, answer_kind="photo", answer="13.4",
                                question="8.9+4.5", photo_bytes=b"img")
    assert r["is_correct"] is None
    assert r["ai_status"] == "pending_review"


def test_photo_failed_is_not_a_wrong_answer(monkeypatch):
    import app.services.math_grade as mg

    monkeypatch.setattr(mg, "grade_math_work_photo", lambda db, img, q, exp: {
        "final_answer": "", "steps_plausible": False, "confidence": 0.0,
        "reason": "无法识别图片", "ai_status": "failed", "ai_correct": False,
    })
    r = mg.grade_by_answer_kind(None, answer_kind="photo", answer="13.4",
                                question="8.9+4.5", photo_bytes=b"img")
    assert r["is_correct"] is None
    assert r["ai_status"] == "failed"
