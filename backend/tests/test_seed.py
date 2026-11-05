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


def test_migrate_multi_student_columns_idempotent(setup_db):
    """陈旧库补列迁移：给 users/pdf_documents 补 grade/edition/parent_id，幂等、数据不丢。"""
    import sqlite3
    from app.database import engine
    # 造一个「缺列」的旧库形态：手动 drop 掉 users/pdf_documents 后按旧 schema 重建
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS users")
        conn.exec_driver_sql("DROP TABLE IF EXISTS pdf_documents")
        conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(64), role VARCHAR(16))")
        conn.exec_driver_sql("CREATE TABLE pdf_documents (id INTEGER PRIMARY KEY, filename VARCHAR(255), subject VARCHAR(16), storage_path VARCHAR(512))")
        conn.exec_driver_sql("INSERT INTO users (id, name, role) VALUES (1, '晨晨', 'child')")
        conn.exec_driver_sql("INSERT INTO pdf_documents (id, filename, subject, storage_path) VALUES (1, '语文.pdf', '语文', 'uploads/语文.pdf')")

    from app.seed import _migrate_multi_student_columns
    _migrate_multi_student_columns()
    _migrate_multi_student_columns()  # 幂等：再跑不报错

    with engine.connect() as conn:
        ucols = {r[1] for r in conn.exec_driver_sql("PRAGMA table_info(users)")}
        dcols = {r[1] for r in conn.exec_driver_sql("PRAGMA table_info(pdf_documents)")}
    assert {"grade", "edition", "parent_id"} <= ucols
    assert {"edition", "grade"} <= dcols

    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM users").scalar() == 1
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM pdf_documents").scalar() == 1


def test_migrate_bucket_columns_idempotent(setup_db):
    """陈旧库补 bucket_id 迁移：给业务表补可空 bucket_id，幂等、不丢数据。"""
    from app.database import engine
    from app.seed import _migrate_bucket_columns
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS tasks")
        conn.exec_driver_sql("CREATE TABLE tasks (id INTEGER PRIMARY KEY, user_id INTEGER, subject VARCHAR(16), date DATE, task_type VARCHAR(16), title VARCHAR(255))")
        conn.exec_driver_sql("INSERT INTO tasks (id, user_id, subject, date, task_type, title) VALUES (1, 1, '语文', '2026-11-05', 'dictation', '听写')")

    _migrate_bucket_columns()
    _migrate_bucket_columns()  # 幂等

    with engine.connect() as conn:
        cols = {r[1] for r in conn.exec_driver_sql("PRAGMA table_info(tasks)")}
        cnt = conn.exec_driver_sql("SELECT COUNT(*) FROM tasks").scalar()
    assert "bucket_id" in cols
    assert cnt == 1  # 数据未丢
