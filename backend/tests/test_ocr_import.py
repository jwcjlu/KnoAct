from app.services.ocr_import import structure_questions_from_text


def test_structure_fake_returns_empty(client, setup_db):
    # fake provider 返回 "[fake] ..."，解析失败 → 空列表（不抛异常）
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        drafts = structure_questions_from_text(db, "这是一张卷子")
    finally:
        db.close()
    assert drafts == []


def test_structure_parses_json_list():
    from app.services.ocr_import import _parse_questions
    import json
    raw = json.dumps({"questions": [{"qtype": "single_choice", "question": "1+1=?", "options": [{"label": "2", "value": 0}], "answer_json": {"correct_index": 0}}]}, ensure_ascii=False)
    items = _parse_questions(raw)
    assert len(items) == 1
    assert items[0]["question"] == "1+1=?"
