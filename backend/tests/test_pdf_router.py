from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.pdf import router as pdf_router


def _client():
    app = FastAPI()
    app.include_router(pdf_router)
    return TestClient(app)


def _make_doc_with_lessons():
    from app.models import PdfDocument, Lesson, WordBank
    from app.database import SessionLocal
    s = SessionLocal()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="uploads/语文.pdf")
    s.add(doc); s.flush()
    l1 = Lesson(document_id=doc.id, subject="语文", title="第 1 课", start_page=1, end_page=2, extract_status="done", audit_status="approved")
    l2 = Lesson(document_id=doc.id, subject="语文", title="第 2 课", start_page=3, end_page=4, extract_status="pending", audit_status="pending")
    s.add_all([l1, l2]); s.flush()
    s.add(WordBank(lesson_id=l1.id, subject="语文", word="水波", extra="shuǐ bō"))
    s.commit()
    did = doc.id
    s.close()
    return did


def test_list_documents_has_counts(setup_db):
    did = _make_doc_with_lessons()
    resp = _client().get("/api/pdf/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) == 1
    assert docs[0]["id"] == did
    assert docs[0]["lesson_count"] == 2
    assert docs[0]["audited_count"] == 1


def test_list_document_lessons_includes_words(setup_db):
    did = _make_doc_with_lessons()
    resp = _client().get(f"/api/pdf/documents/{did}/lessons")
    assert resp.status_code == 200
    lessons = resp.json()
    assert len(lessons) == 2
    # 按 start_page 升序：第 1 课在前
    assert lessons[0]["title"] == "第 1 课"
    assert lessons[0]["audit_status"] == "approved"
    assert lessons[0]["words"][0]["word"] == "水波"


def test_audit_lesson_approve(setup_db):
    did = _make_doc_with_lessons()
    lessons = _client().get(f"/api/pdf/documents/{did}/lessons").json()
    lid = lessons[1]["id"]
    resp = _client().post(f"/api/pdf/lessons/{lid}/audit", data={"action": "通过"})
    assert resp.status_code == 200
    assert resp.json()["audit_status"] == "approved"


def test_extract_document_missing_file_marks_done(setup_db):
    """无真实 PDF 时提取：源文件不存在 → 返回 error，lesson 保持 pending（不启动后台任务）。"""
    from app.models import PdfDocument, Lesson
    from app.database import SessionLocal
    s = SessionLocal()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="uploads/不存在.pdf")
    s.add(doc); s.flush()
    s.add(Lesson(document_id=doc.id, subject="语文", title="第 1 课", start_page=1, end_page=1, extract_status="pending", audit_status="pending"))
    s.commit()
    did = doc.id
    s.close()
    resp = _client().post(f"/api/pdf/documents/{did}/extract")
    assert resp.status_code == 200
    assert resp.json()["error"] == "源文件不存在"
    s = SessionLocal()
    l = s.query(Lesson).filter_by(document_id=did).first()
    assert l.extract_status == "pending"
    s.close()


def test_list_lessons_has_document_version(setup_db):
    """lesson 接口带 document_version（= document.created_at 毫秒时间戳），供前端页图缓存拼 ?v=。"""
    from datetime import datetime
    from app.models import PdfDocument, Lesson
    from app.database import SessionLocal
    s = SessionLocal()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="uploads/语文.pdf",
                      created_at=datetime(2026, 11, 4, 0, 0, 0))
    s.add(doc); s.flush()
    s.add(Lesson(document_id=doc.id, subject="语文", title="第 1 课", start_page=1, end_page=1,
                 extract_status="done", audit_status="approved"))
    s.commit()
    did = doc.id
    s.close()
    lessons = _client().get(f"/api/pdf/documents/{did}/lessons").json()
    assert lessons[0]["document_version"] == int(datetime(2026, 11, 4).timestamp() * 1000)


def test_list_lessons_version_autopopulated(setup_db):
    """未显式设 created_at 时，ORM default 自动填充，document_version 为非零时间戳。"""
    did = _make_doc_with_lessons()
    lessons = _client().get(f"/api/pdf/documents/{did}/lessons").json()
    assert lessons[0]["document_version"] > 0
