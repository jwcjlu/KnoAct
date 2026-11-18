"""启动时对照 SQLAlchemy 模型补齐数据库。

create_all 只会建还不存在的表，不会给老表加列。这里在它之后扫描每张已有表，
把模型里有、库里没有的列用 ALTER TABLE ADD COLUMN 补上。

只做加法：不删列、不改已有列的类型、不补索引和外键。已有数据的表上，
非空列会带上模型里的字面默认值；默认值是函数（如 utcnow）时改成可空，避免启动失败。
"""
import logging
import re

from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn
from sqlalchemy.sql.schema import ColumnDefault

_log = logging.getLogger("uvicorn.error")
_UNIQUE = re.compile(r"\s+UNIQUE\b", re.IGNORECASE)


def _literal_default(column):
    """模型上的 Python 字面默认值。函数默认（utcnow 等）返回 None。"""
    default = column.default
    if not isinstance(default, ColumnDefault) or callable(default.arg):
        return None
    return default.arg


def _sql_literal(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _column_ddl(column, dialect) -> str:
    ddl = str(CreateColumn(column).compile(dialect=dialect))
    ddl = _UNIQUE.sub("", ddl)
    if "DEFAULT" in ddl.upper():
        return ddl
    if column.nullable:
        return ddl
    literal = _literal_default(column)
    if literal is None:
        return ddl.replace(" NOT NULL", "", 1)
    return ddl.replace(" NOT NULL", f" NOT NULL DEFAULT {_sql_literal(literal)}", 1)


def sync_schema(engine, metadata) -> dict:
    """补缺失的表和列。返回 {"tables": [...], "columns": ["table.col", ...]}。"""
    insp = inspect(engine)
    before = set(insp.get_table_names())
    metadata.create_all(bind=engine)
    insp = inspect(engine)
    created = sorted(set(insp.get_table_names()) - before)
    added: list[str] = []
    dialect = engine.dialect
    quote = dialect.identifier_preparer.quote
    for table in metadata.sorted_tables:
        if table.name not in before:
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            sql = f"ALTER TABLE {quote(table.name)} ADD COLUMN {_column_ddl(column, dialect)}"
            try:
                with engine.begin() as conn:
                    conn.execute(text(sql))
            except Exception as exc:
                _log.warning("补列失败 %s.%s: %s", table.name, column.name, exc)
                continue
            added.append(f"{table.name}.{column.name}")
            _log.info("已补列 %s.%s", table.name, column.name)
    for name in created:
        _log.info("已建表 %s", name)
    return {"tables": created, "columns": added}
