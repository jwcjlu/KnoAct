"""存量库补列与索引（练习册题组两级模型）。

新表由 `main.py` 启动时的 `schema_sync(engine, Base.metadata)` 创建；
`schema_sync` 只补列不补索引，所以这里显式建索引。
每步独立 try/except，保证幂等（列/索引已存在时跳过）。

⚠️ 本迁移**只做 schema 变更，绝不删数据**。
`DELETE FROM questions WHERE source_document_id IS NOT NULL` 这类清理若写进
启动迁移，每次重启都会清空练习册题目。清旧数据是一次性动作，由家长端
「重新导入」按钮显式触发。
"""
import logging

from sqlalchemy import text

from .database import engine

_log = logging.getLogger("uvicorn.error")

_STATEMENTS: list[tuple[str, str]] = [
    ("group_id", "ALTER TABLE questions ADD COLUMN group_id INTEGER"),
    ("seq_in_group", "ALTER TABLE questions ADD COLUMN seq_in_group INTEGER DEFAULT 0"),
    ("is_example", "ALTER TABLE questions ADD COLUMN is_example BOOLEAN DEFAULT 0"),
    ("work_mode", "ALTER TABLE questions ADD COLUMN work_mode VARCHAR(24) DEFAULT ''"),
    (
        "ix_questions_group",
        "CREATE INDEX ix_questions_group ON questions (group_id, seq_in_group)",
    ),
    (
        "ix_pqg_bank",
        "CREATE INDEX ix_pqg_bank ON practice_question_groups (bank_id)",
    ),
]


def migrate() -> None:
    for name, sql in _STATEMENTS:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception as exc:  # noqa: BLE001
            # 已存在（SQLite/MySQL 报错文案不同）或表还没建：记日志继续
            _log.info("题组迁移跳过 %s: %s", name, str(exc)[:120])


if __name__ == "__main__":
    migrate()
    print("练习册题组迁移完成")
