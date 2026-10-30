from app.database import SessionLocal
from app.services.knowledge_quiz import generate_knowledge_questions, grade_knowledge_answer


def test_generate_fake_provider_returns_fallback():
    db = SessionLocal()
    pts = [{"id": 1, "content": "圆的周长公式", "category": "公式"}]
    out = generate_knowledge_questions(db, pts, subject="数学")
    assert isinstance(out, list) and len(out) == 1
    assert out[0]["id"] == 1
    assert "content" in out[0]
    assert "question" in out[0] and "answer" in out[0] and "keywords" in out[0]
    db.close()


def test_grade_keyword_full_match():
    ok, used_ai = grade_knowledge_answer("周长等于π乘以直径", keywords=["π", "直径", "周长"], answer="周长=π×直径")
    assert ok is True and used_ai is False


def test_grade_keyword_none_match():
    ok, used_ai = grade_knowledge_answer("不知道", keywords=["π", "直径"], answer="周长=π×直径")
    assert ok is False and used_ai is False


def test_grade_empty_answer():
    ok, used_ai = grade_knowledge_answer("", keywords=["π"], answer="周长=π×直径")
    assert ok is False and used_ai is False
