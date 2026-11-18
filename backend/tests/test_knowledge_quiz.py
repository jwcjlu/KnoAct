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


def test_grade_exact_standard_answer_wins_over_bad_keywords():
    """标准答案原样提交必须判对：关键词若是整段拼盘，子串匹配会全 miss。"""
    answer = (
        "把“1”平均分成10份，其中1份是1/10，写成0.1；"
        "平均分成100份，其中1份是1/100，写成0.01；"
        "平均分成1000份，其中1份是1/1000，写成0.001。"
    )
    keywords = ["平均分成10份、100份、1000份", "1/10，0.1", "1/100，0.01", "1/1000，0.001"]
    ok, used_ai = grade_knowledge_answer(answer, keywords, answer)
    assert ok is True and used_ai is False


def test_grade_exact_answer_ignores_surrounding_whitespace():
    ok, used_ai = grade_knowledge_answer("  周长=π×直径  ", keywords=["完全无关"], answer="周长=π×直径")
    assert ok is True and used_ai is False
