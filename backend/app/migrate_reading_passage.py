"""一次性迁移：给存量 questions 表补 passage_id。

create_all 不会给已存在的表补列。运行：cd backend && python -m app.migrate_reading_passage
幂等：列已存在则跳过。不建 FK（对齐 bank_id）。
"""
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .database import engine, SessionLocal


def migrate(db: Session) -> None:
    insp = inspect(engine)
    if "questions" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("questions")}
    if "passage_id" not in cols:
        db.execute(text("ALTER TABLE questions ADD COLUMN passage_id INTEGER"))
        db.commit()


if __name__ == "__main__":
    db = SessionLocal()
    try:
        from .models import Base
        from .database import engine as _engine
        Base.metadata.create_all(bind=_engine)
        migrate(db)
        print("迁移完成")
    finally:
        db.close()
