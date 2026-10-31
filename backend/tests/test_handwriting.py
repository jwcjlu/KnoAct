from unittest.mock import patch

from app.database import SessionLocal
from app.services.handwriting import grade_handwriting, parse_grading_result


def test_parse_grading_result():
    raw = '{"results":[{"index":0,"written":"箩","is_correct":true},{"index":1,"written":"萝","is_correct":false}]}'
    out = parse_grading_result(raw)
    assert out == [
        {"index": 0, "written": "箩", "is_correct": True},
        {"index": 1, "written": "萝", "is_correct": False},
    ]


def test_parse_grading_result_bad_json():
    assert parse_grading_result("not json") == []
    assert parse_grading_result('{"results": "oops"}') == []


def test_parse_grading_result_strips_markdown_fences():
    raw = '```json\n{"results":[{"index":0,"written":"箩","is_correct":true}]}\n```'
    out = parse_grading_result(raw)
    assert len(out) == 1 and out[0]["is_correct"] is True


def test_grade_handwriting_empty_input_returns_empty():
    db = SessionLocal()
    assert grade_handwriting(db, b"", []) == []
    assert grade_handwriting(db, b"img", []) == []
    db.close()


def test_grade_handwriting_fake_provider_returns_empty():
    # 视觉模型未配置/异常时，返回空列表（不抛异常）
    db = SessionLocal()
    with patch("app.services.handwriting.ocr_image", side_effect=RuntimeError("no vision")):
        words = [{"index": 0, "word": "箩"}]
        out = grade_handwriting(db, b"fake-image-bytes", words)
    assert out == []
    db.close()
