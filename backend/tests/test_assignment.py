import json
from app.database import SessionLocal
from app.services.assignment import generate_assignment, grade_assignment, DIFFICULTY_PROMPT, FALLBACK_ASSIGNMENT


def test_difficulty_prompt_mapping():
    assert DIFFICULTY_PROMPT["简单"] != DIFFICULTY_PROMPT["中等"] != DIFFICULTY_PROMPT["困难"]
    assert DIFFICULTY_PROMPT["中等"]  # 非空


def test_generate_assignment_fake_provider_returns_fallback():
    db = SessionLocal()
    # 未配置真实 provider 时（fake），返回兜底题，绝不抛异常
    out = generate_assignment(db, "白鹭是一首精巧的诗。", subject="语文", difficulty="中等", n=4)
    assert isinstance(out, list)
    assert len(out) > 0
    assert all("question" in q and "answer" in q and "knowledge_point_id" in q for q in out)
    db.close()


def test_generate_assignment_empty_text_returns_fallback():
    db = SessionLocal()
    out = generate_assignment(db, "", subject="语文", difficulty="中等", n=4)
    assert out == FALLBACK_ASSIGNMENT
    db.close()


def test_generate_assignment_extracts_knowledge_point_id(monkeypatch):
    """传入知识点列表时，返回题含 knowledge_point_id（int 保留，非法值置 None）。"""
    db = SessionLocal()

    class _Fake:
        name = "openai"
        def generate(self, prompt, system="", json_mode=False):
            assert "knowledge_point_id" in prompt
            import json as _j
            return _j.dumps({"questions": [
                {"question": "题1", "answer": "答1", "knowledge_point_id": 7},
                {"question": "题2", "answer": "答2", "knowledge_point_id": "x"},
                {"question": "题3", "answer": "答3"},
            ]}, ensure_ascii=False)

    monkeypatch.setattr("app.services.assignment.get_provider", lambda _db: _Fake())
    kps = [{"id": 7, "category": "修辞", "content": "比喻"},
           {"id": 8, "category": "字词", "content": "矗立"}]
    out = generate_assignment(db, "白鹭是一首精巧的诗。", subject="语文", n=4, knowledge_points=kps)
    assert out[0]["knowledge_point_id"] == 7
    assert out[1]["knowledge_point_id"] is None
    assert out[2]["knowledge_point_id"] is None
    db.close()


def test_generate_assignment_prompt_avoids_previous_and_targets_wrong(monkeypatch):
    db = SessionLocal()
    seen = {}

    class _Fake:
        name = "openai"
        def generate(self, prompt, system="", json_mode=False):
            seen["prompt"] = prompt
            return json.dumps({"questions": [{"question": "新题", "answer": "答"}]}, ensure_ascii=False)

    monkeypatch.setattr("app.services.assignment.get_provider", lambda _db: _Fake())
    generate_assignment(db, "桂花雨的课文。", n=4,
                        previous_questions=["旧题A", "旧题B"], wrong_questions=["旧题B"])
    assert "不要与它们重复" in seen["prompt"] and "旧题A" in seen["prompt"]
    assert "答错了下面这些题" in seen["prompt"]
    db.close()


def test_grade_assignment_ai_judges_by_meaning(monkeypatch):
    """AI 按意思判分；未作答的题不送 AI，直接判错。"""
    db = SessionLocal()
    sent = {}

    class _Fake:
        name = "openai"
        def generate(self, prompt, system="", json_mode=False):
            sent["prompt"] = prompt
            return json.dumps({"results": [
                {"index": 0, "is_correct": True, "feedback": "抓住了要点"},
                {"index": 1, "is_correct": False, "feedback": "意思理解错了"},
            ]}, ensure_ascii=False)

    monkeypatch.setattr("app.services.assignment.get_provider", lambda _db: _Fake())
    items = [
        {"question": "浸字好在哪里？", "answer": "写出香气浓、范围广", "student_answer": "说明桂花香很浓，到处都是"},
        {"question": "母亲为什么念叨台风？", "answer": "怕台风吹落桂花", "student_answer": "因为她喜欢台风"},
        {"question": "第三题", "answer": "答案", "student_answer": "  "},
    ]
    out = grade_assignment(db, items)
    assert [r["is_correct"] for r in out] == [True, False, False]
    assert out[0]["feedback"] == "抓住了要点"
    assert "第三题" not in sent["prompt"]
    db.close()


def test_grade_assignment_falls_back_to_rule_on_bad_ai_output(monkeypatch):
    db = SessionLocal()

    class _Fake:
        name = "openai"
        def generate(self, prompt, system="", json_mode=False):
            return "not json"

    monkeypatch.setattr("app.services.assignment.get_provider", lambda _db: _Fake())
    out = grade_assignment(db, [
        {"question": "1kg 等于多少克？", "answer": "1000克", "student_answer": "1000 克"},
        {"question": "0.6 和 0.60 相等吗？", "answer": "相等", "student_answer": "不相等"},
    ])
    assert [r["is_correct"] for r in out] == [True, False]
    db.close()


def test_grade_assignment_fake_provider_uses_rule():
    db = SessionLocal()
    out = grade_assignment(db, [
        {"question": "q", "answer": "0.5千克", "student_answer": "0.5千克。"},
        {"question": "q", "answer": "0.5千克", "student_answer": ""},
    ])
    assert [r["is_correct"] for r in out] == [True, False]
    db.close()
