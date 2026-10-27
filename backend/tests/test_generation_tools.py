from app.core.context import UnifiedContext
from app.tools.generation import generate_listening, generate_quiz_questions, generate_diagnostic_questions


def _ctx():
    return UnifiedContext(user_id=1, lesson_id=1, question="")


def test_generate_listening_returns_structure():
    result = generate_listening.run({}, _ctx())
    assert "dialogue" in result
    assert "question" in result
    assert "answer" in result


def test_generate_diagnostic_questions_returns_questions():
    result = generate_diagnostic_questions.run({"context": "白鹭是一首精巧的诗。"}, _ctx())
    assert "questions" in result
    assert isinstance(result["questions"], list)


def test_generate_listening_accepts_words_and_points():
    result = generate_listening.run(
        {"words": ["apple", "banana"], "knowledge_points": ["颜色词"]}, _ctx())
    assert "dialogue" in result
    assert "question" in result
    assert "answer" in result
