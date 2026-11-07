from app.core.context import UnifiedContext
from app.tools.generation import (
    generate_diagnostic_questions,
    generate_listening,
    generate_quiz_questions,
    normalize_listening,
)


def _ctx():
    return UnifiedContext(user_id=1, lesson_id=1, question="")


def test_generate_listening_returns_structure():
    result = generate_listening.run({}, _ctx())
    assert "dialogue" in result
    assert "questions" in result
    assert isinstance(result["questions"], list)
    assert len(result["questions"]) >= 3


def test_generate_diagnostic_questions_returns_questions():
    result = generate_diagnostic_questions.run({"context": "白鹭是一首精巧的诗。"}, _ctx())
    assert "questions" in result
    assert isinstance(result["questions"], list)


def test_generate_listening_accepts_words_and_points():
    result = generate_listening.run(
        {"words": ["apple", "banana"], "knowledge_points": ["颜色词"]}, _ctx())
    assert "dialogue" in result
    assert "questions" in result
    assert len(result["questions"]) >= 3


def test_normalize_listening_requires_four_options():
    raw = {
        "dialogue": "A: Hi",
        "questions": [
            {
                "id": "q1",
                "question": "What did A say?",
                "options": ["Hi", "Bye", "Yes", "No"],
                "correct_index": 0,
            }
        ],
    }
    out = normalize_listening(raw)
    assert len(out["questions"]) >= 3
    assert all(len(q["options"]) == 4 for q in out["questions"])


def test_generate_listening_returns_mc_schema():
    result = generate_listening.run({}, _ctx())
    assert "dialogue" in result
    assert "questions" in result
    assert len(result["questions"]) >= 3
    q0 = result["questions"][0]
    assert len(q0["options"]) == 4
    assert 0 <= q0["correct_index"] <= 3
