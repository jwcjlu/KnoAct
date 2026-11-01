import os
# 默认用临时 SQLite；设 KNOACT_TEST_DATABASE_URL 可对 MySQL 等真实库跑同一套测试（会清空该库的表）
os.environ["DATABASE_URL"] = os.getenv("KNOACT_TEST_DATABASE_URL", "sqlite:///./test.db")
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import close_all_sessions
from app.database import Base, engine, get_db, SessionLocal
from app.main import app


if engine.url.get_backend_name() == "sqlite":
    # SQLite 默认不校验外键；测试里打开，与 MySQL 行为一致
    @event.listens_for(engine, "connect")
    def _sqlite_fk_on(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def _reset_connections():
    # MySQL 上未结束的事务持有元数据锁，DROP TABLE 会一直等待；建删表前先收回所有会话与连接
    close_all_sessions()
    engine.dispose()


@pytest.fixture(autouse=True)
def setup_db():
    _reset_connections()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    _reset_connections()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


# 外键父行工具：测试里 `from conftest import make_user, make_lesson`
def make_user(session, name="晨晨", role="child"):
    from app.models import User
    u = User(name=name, role=role)
    session.add(u); session.flush()
    return u


def make_document(session, subject="语文", filename="教材.pdf", storage_path=""):
    from app.models import PdfDocument
    doc = PdfDocument(filename=filename, subject=subject, storage_path=storage_path)
    session.add(doc); session.flush()
    return doc


def make_lesson(session, subject="语文", title="第1课", start_page=1, end_page=3, document=None, **kw):
    """建课程；未给 document 时顺带建一份 PdfDocument。"""
    from app.models import Lesson
    if document is None:
        document = make_document(session, subject=subject)
    lesson = Lesson(document_id=document.id, subject=subject, title=title,
                    start_page=start_page, end_page=end_page, **kw)
    session.add(lesson); session.flush()
    return lesson
