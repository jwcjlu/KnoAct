"""一次性迁移：WordBank.kind 默认值、去重、唯一索引。

create_all / schema_sync 会给新库加列；存量库需 UPDATE + 去重后才能安全建
`(lesson_id, kind, word)` 唯一约束。

幂等：重复运行跳过已有索引；已唯一的行不改动。

运行：cd backend && python -m app.migrate_word_kind
"""
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from .database import engine, SessionLocal
from .models import Mistake, WordBank, WordMastery
from .services import word_kinds as wk

_INDEX = "uq_word_banks_lesson_kind_word"


def migrate(db: Session) -> None:
    insp = inspect(engine)
    if "word_banks" not in insp.get_table_names():
        return

    cols = {c["name"] for c in insp.get_columns("word_banks")}
    if "kind" not in cols:
        db.execute(text("ALTER TABLE word_banks ADD COLUMN kind VARCHAR(16) DEFAULT 'phrase'"))
        db.commit()

    db.execute(
        text(
            "UPDATE word_banks SET kind = :phrase "
            "WHERE subject = '语文' AND (kind IS NULL OR kind = '')"
        ),
        {"phrase": wk.KIND_PHRASE},
    )
    db.execute(
        text(
            "UPDATE word_banks SET kind = :word "
            "WHERE subject != '语文' AND (kind IS NULL OR kind = '')"
        ),
        {"word": wk.KIND_WORD},
    )
    db.commit()

    dup_groups = (
        db.query(
            WordBank.lesson_id,
            WordBank.kind,
            WordBank.word,
            func.min(WordBank.id).label("keep_id"),
        )
        .group_by(WordBank.lesson_id, WordBank.kind, WordBank.word)
        .having(func.count() > 1)
        .all()
    )
    for lesson_id, kind, word, keep_id in dup_groups:
        drop_ids = [
            wid
            for (wid,) in db.query(WordBank.id)
            .filter_by(lesson_id=lesson_id, kind=kind, word=word)
            .filter(WordBank.id != keep_id)
            .all()
        ]
        for drop_id in drop_ids:
            db.query(WordMastery).filter_by(word_bank_id=drop_id).update(
                {WordMastery.word_bank_id: keep_id}, synchronize_session=False
            )
            db.query(Mistake).filter_by(word_bank_id=drop_id).update(
                {Mistake.word_bank_id: keep_id}, synchronize_session=False
            )
            db.query(WordBank).filter_by(id=drop_id).delete(synchronize_session=False)
    if dup_groups:
        db.commit()

    existing = {i["name"] for i in insp.get_indexes("word_banks")}
    if _INDEX in existing:
        return

    if engine.url.get_backend_name() == "mysql":
        db.execute(
            text(f"CREATE UNIQUE INDEX {_INDEX} ON word_banks (lesson_id, kind, word)")
        )
    else:
        db.execute(
            text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {_INDEX} "
                f"ON word_banks (lesson_id, kind, word)"
            )
        )
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