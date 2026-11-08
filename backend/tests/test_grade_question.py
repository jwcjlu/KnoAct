from app.services.grade_question import grade_question, normalize_answer, grade_subjective_with_ai


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


def test_normalize_answer_fullwidth_to_halfwidth():
    assert normalize_answer("８") == normalize_answer("8")
    assert normalize_answer("ＡＢＣ") == normalize_answer("abc")
    assert normalize_answer("３＋５") == normalize_answer("3+5")


def test_choice_bool_not_treated_as_index():
    r = grade_question("choice", {"correct_index": 1}, {"selected_index": True})
    assert r["is_correct"] is False


def test_grade_subjective_fake_returns_pending(client, setup_db):
    # fake provider：generate 返回 "[fake] ..."，无法解析 → pending
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        r = grade_subjective_with_ai(db, {"rubric": "要点", "sample": "参考"}, {"text": "我的回答"})
    finally:
        db.close()
    assert r["is_correct"] is None
    assert r["detail"] == "pending"


def test_grade_subjective_empty_text(client, setup_db):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        r = grade_subjective_with_ai(db, {"rubric": "要点", "sample": "参考"}, {"text": ""})
    finally:
        db.close()
    assert r["is_correct"] is False
    assert r["detail"] == "empty"


def test_grade_subjective_malformed_flag_returns_pending(client, setup_db, monkeypatch):
    # is_correct 非严格布尔（如字符串 "maybe"）→ 不得硬判对/错，回落 pending
    from app.database import SessionLocal
    import app.services.ai as ai

    class _FakeNonFake:
        name = "openai"
        def generate(self, prompt="", system="", json_mode=False):
            return '{"is_correct": "maybe", "reason": "不确定"}'

    monkeypatch.setattr(ai, "get_provider", lambda db: _FakeNonFake())
    db = SessionLocal()
    try:
        r = grade_subjective_with_ai(db, {"rubric": "要点", "sample": "参考"}, {"text": "我的回答"})
    finally:
        db.close()
    assert r["is_correct"] is None
    assert r["detail"] == "pending"
