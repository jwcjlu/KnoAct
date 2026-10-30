import json
from app.database import SessionLocal
from app.services.assignment import generate_assignment, DIFFICULTY_PROMPT, FALLBACK_ASSIGNMENT


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
