"""存量库补列与索引（练习册导入用）。

`schema_sync` 只补列不补索引，`create_all` 又不改老表，所以这里显式做。
每步独立 try/except，保证幂等（列/索引已存在时跳过）。
"""
import logging

from sqlalchemy import text

from .database import engine

_log = logging.getLogger("uvicorn.error")

_STATEMENTS: list[tuple[str, str]] = [
    ("lesson_no", "ALTER TABLE questions ADD COLUMN lesson_no INTEGER"),
    ("lesson_title", "ALTER TABLE questions ADD COLUMN lesson_title VARCHAR(64)"),
    ("question_no", "ALTER TABLE questions ADD COLUMN question_no VARCHAR(16)"),
    (
        "source_document_id",
        "ALTER TABLE questions ADD COLUMN source_document_id INTEGER",
    ),
    ("image_path", "ALTER TABLE questions ADD COLUMN image_path VARCHAR(512)"),
    (
        "ix_questions_bank_lesson",
        "CREATE INDEX ix_questions_bank_lesson ON questions (bank_id, lesson_no)",
    ),
]


def migrate() -> None:
    for name, sql in _STATEMENTS:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception as exc:  # noqa: BLE001
            # 已存在（SQLite/MySQL 报错文案不同）或权限不足：记一条日志继续
            _log.info("练习册导入迁移跳过 %s: %s", name, str(exc)[:120])


if __name__ == "__main__":
    migrate()
    print("练习册导入迁移完成")
