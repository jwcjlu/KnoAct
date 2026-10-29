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
    assert all("question" in q and "answer" in q for q in out)
    db.close()


def test_generate_assignment_empty_text_returns_fallback():
    db = SessionLocal()
    out = generate_assignment(db, "", subject="语文", difficulty="中等", n=4)
    assert out == FALLBACK_ASSIGNMENT
    db.close()
