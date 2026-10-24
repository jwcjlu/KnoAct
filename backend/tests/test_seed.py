from app.seed import seed


def test_seed_creates_data(setup_db):
    seed()
    from app.models import User, Lesson, WordBank, KnowledgePoint, Text, ModelConfig
    from app.database import SessionLocal
    s = SessionLocal()
    assert s.query(User).count() == 2  # 一个孩子 + 一个家长
    assert s.query(Lesson).count() == 1
    assert s.query(WordBank).count() == 5
    assert s.query(KnowledgePoint).count() == 2
    assert s.query(Text).count() == 1
    assert s.query(ModelConfig).count() == 2
    s.close()


def test_seed_is_idempotent(setup_db):
    seed()
    seed()
    from app.models import User, Lesson
    from app.database import SessionLocal
    s = SessionLocal()
    assert s.query(User).count() == 2  # 不重复
    assert s.query(Lesson).count() == 1
    s.close()
