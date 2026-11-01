from app.seed import seed


def test_seed_creates_data(setup_db):
    seed()
    from app.models import User, Lesson, WordBank, KnowledgePoint, Text, ModelConfig
    from app.database import SessionLocal
    s = SessionLocal()
    assert s.query(User).count() == 2  # 一个孩子 + 一个家长
    assert s.query(Lesson).count() == 1
    assert s.query(WordBank).count() == 5
    assert s.query(KnowledgePoint).filter(KnowledgePoint.lesson_id.isnot(None)).count() == 2  # 课文绑定的 2 条
    assert s.query(KnowledgePoint).filter(KnowledgePoint.lesson_id.is_(None)).count() == 28  # 基础分类目录（语文12+英语9+数学7）
    assert s.query(Text).count() == 1
    assert s.query(ModelConfig).count() == 2
    s.close()


def test_seed_renames_legacy_default_child(setup_db):
    """老库里的「金宇轩」原地改名为「金同学」，id 不变，不新增用户。"""
    from app.models import User
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(User(name="金宇轩", role="child"))
    s.commit()
    old_id = s.query(User).filter_by(name="金宇轩").first().id
    s.close()

    seed()
    seed()
    s = SessionLocal()
    assert s.query(User).filter_by(name="金宇轩").count() == 0
    assert s.query(User).filter_by(name="金同学").one().id == old_id
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
