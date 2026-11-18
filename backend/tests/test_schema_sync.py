"""启动时对照模型补缺失的表和列。"""
from sqlalchemy import create_engine, inspect, text

from app.models import Base
from app.schema_sync import sync_schema


def test_sync_creates_missing_table_and_adds_column_with_default(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE pdf_documents ("
            "id INTEGER PRIMARY KEY, filename VARCHAR(255), subject VARCHAR(16), storage_path VARCHAR(512))"
        ))
        conn.execute(text(
            "INSERT INTO pdf_documents (id, filename, subject, storage_path) VALUES (1, 'a.pdf', '英语', 'uploads/a.pdf')"
        ))

    result = sync_schema(engine, Base.metadata)

    assert "lesson_audios" in result["tables"]
    assert "pdf_documents.content_kind" in result["columns"]
    assert "pdf_documents.handout_kind" in result["columns"]
    insp = inspect(engine)
    assert insp.has_table("lesson_audios")
    cols = {c["name"] for c in insp.get_columns("pdf_documents")}
    assert "content_kind" in cols and "edition" in cols
    with engine.connect() as conn:
        row = conn.execute(text("SELECT content_kind, edition FROM pdf_documents WHERE id = 1")).one()
    assert row.content_kind == "textbook"
    assert row.edition == ""


def test_sync_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'full.db'}")
    first = sync_schema(engine, Base.metadata)
    second = sync_schema(engine, Base.metadata)
    assert first["tables"]
    assert second == {"tables": [], "columns": []}
