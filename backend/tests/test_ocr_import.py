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


def test_parse_questions_keeps_legacy_shape():
    from app.services.ocr_import import _parse_import
    import json
    raw = json.dumps({"questions": [{"qtype": "short_answer", "question": "Q"}]})
    passages, questions = _parse_import(raw)
    assert passages == []
    assert questions[0]["question"] == "Q"


def test_parse_import_passages_shape():
    from app.services.ocr_import import _parse_import
    import json
    raw = json.dumps({
        "passages": [{
            "title": "小蝌蚪",
            "content": "小蝌蚪 **游啊游**。看见 ____。",
            "questions": [
                {"qtype": "fill_blank", "question": "看见什么？", "answer_json": {"blanks": ["鲤鱼"]}},
            ],
        }],
        "questions": [{"qtype": "short_answer", "question": "独立题"}],
    }, ensure_ascii=False)
    passages, questions = _parse_import(raw)
    assert len(passages) == 1
    assert passages[0]["title"] == "小蝌蚪"
    assert len(questions) == 1


def test_flatten_passages_onto_drafts():
    from app.services.ocr_import import _flatten_import
    passages = [{"title": "T", "content": "C", "questions": [
        {"qtype": "short_answer", "question": "子题", "answer": "A"},
    ]}]
    questions = [{"qtype": "short_answer", "question": "独立", "answer": "B"}]
    drafts = _flatten_import(passages, questions)
    assert len(drafts) == 2
    assert drafts[0].question == "子题"
    assert drafts[0].passage_title == "T"
    assert drafts[0].passage_content == "C"
    assert drafts[1].question == "独立"
    assert drafts[1].passage_content == ""
