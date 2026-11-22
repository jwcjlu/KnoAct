"""学习进度改为「孩子 + 教材」：给 learning_progress 加 document_id，
并把唯一约束从 (user_id, subject) 换成 (user_id, document_id)。

为什么要重建表：SQLite 不支持 ALTER TABLE 删约束，唯一约束只能靠
「建新表 → 拷数据 → 删旧表 → 改名」来换。MySQL 上可以 DROP INDEX + ADD UNIQUE，
所以两条路分开处理。

幂等：已经改过（存在 document_id 列且旧唯一索引已不存在）就直接返回。
只做加法：老记录的 document_id 留 NULL，由 services/learning_progress
在首次使用时「认领」到具体教材，不会丢数据。
"""
import logging

from sqlalchemy import inspect, text

from .database import engine

_log = logging.getLogger("uvicorn.error")

_OLD_UNIQUE = "uq_progress_user_subject"
_NEW_UNIQUE = "uq_progress_user_document"


def _columns(conn, table: str) -> set[str]:
    try:
        return {c["name"] for c in inspect(conn).get_columns(table)}
    except Exception:
        return set()


def _indexes(conn, table: str) -> set[str]:
    try:
        return {i["name"] for i in inspect(conn).get_indexes(table)}
    except Exception:
        return set()


def _ddl(conn, table: str = "learning_progress") -> str:
    """取建表 DDL。SQLite 上判断约束/列是否齐全靠它。"""
    try:
        row = list(conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": table}))
        return row[0][0] if row else ""
    except Exception:
        return ""


def _sqlite_rebuild(conn) -> None:
    """SQLite：重建表以换掉唯一约束。保留原有全部列（按实际表结构取交集）。"""
    cols = _columns(conn, "learning_progress")
    # 目标列（新表有的）；只拷旧表里真实存在的
    target = ["id", "user_id", "document_id", "subject", "current_lesson_id"]
    keep = [c for c in target if c in cols]
    collist = ", ".join(f'"{c}"' for c in keep)

    conn.execute(text("ALTER TABLE learning_progress RENAME TO learning_progress_old"))
    conn.execute(text(f"""
        CREATE TABLE learning_progress (
            id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            document_id INTEGER,
            subject VARCHAR(16) DEFAULT '语文',
            current_lesson_id INTEGER,
            PRIMARY KEY (id),
            CONSTRAINT {_NEW_UNIQUE} UNIQUE (user_id, document_id),
            FOREIGN KEY(user_id) REFERENCES users (id),
            FOREIGN KEY(document_id) REFERENCES pdf_documents (id),
            FOREIGN KEY(current_lesson_id) REFERENCES lessons (id)
        )
    """))
    conn.execute(text(
        f"INSERT INTO learning_progress ({collist}) "
        f"SELECT {collist} FROM learning_progress_old"))
    conn.execute(text("DROP TABLE learning_progress_old"))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_learning_progress_document_id "
        "ON learning_progress (document_id)"))
    _log.info("learning_progress 已重建（唯一约束改为 user_id+document_id）")


def _mysql_update(conn) -> None:
    """MySQL：补列 + 换索引，无需重建表。"""
    cols = _columns(conn, "learning_progress")
    if "document_id" not in cols:
        conn.execute(text(
            "ALTER TABLE learning_progress ADD COLUMN document_id INTEGER NULL"))
    idx = _indexes(conn, "learning_progress")
    if _OLD_UNIQUE in idx:
        conn.execute(text(f"ALTER TABLE learning_progress DROP INDEX {_OLD_UNIQUE}"))
    if _NEW_UNIQUE not in idx:
        conn.execute(text(
            f"ALTER TABLE learning_progress "
            f"ADD CONSTRAINT {_NEW_UNIQUE} UNIQUE (user_id, document_id)"))
    _log.info("learning_progress 已更新唯一约束（user_id+document_id）")


def migrate() -> None:
    try:
        with engine.begin() as conn:
            if not _columns(conn, "learning_progress"):
                _log.info("learning_progress 表不存在，跳过")
                return
            dialect = engine.dialect.name
            if dialect == "sqlite":
                cols = _columns(conn, "learning_progress")
                ddl = _ddl(conn)
                has_new_unique = (_NEW_UNIQUE in (ddl or "")) or bool(
                    list(conn.execute(
                        text("SELECT name FROM sqlite_master WHERE type='index' "
                             "AND tbl_name='learning_progress' AND name=:n"),
                        {"n": _NEW_UNIQUE})))
                if "document_id" in cols and has_new_unique:
                    _log.info("learning_progress 已是新结构，跳过")
                    return
                _sqlite_rebuild(conn)
            else:
                _mysql_update(conn)
    except Exception as exc:  # noqa: BLE001
        _log.warning("学习进度迁移失败: %s", str(exc)[:200])


if __name__ == "__main__":
    migrate()
    print("学习进度迁移完成")
