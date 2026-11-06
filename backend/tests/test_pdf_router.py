from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.pdf import router as pdf_router
from app.database import SessionLocal
from app.models import User
from conftest import auth_headers, make_account


def _client():
    app = FastAPI()
    app.include_router(pdf_router)
    return TestClient(app)


def _parent_headers():
    s = SessionLocal()
    p = make_account(s, "p_pdf", "parent")
    s.commit()
    h = auth_headers(p)
    s.close()
    return h


def _make_doc_with_lessons():
    from app.models import PdfDocument, Lesson, WordBank
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
    h = _parent_headers()
    resp = _client().get("/api/pdf/documents", headers=h)
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) == 1
    assert docs[0]["id"] == did
    assert docs[0]["lesson_count"] == 2
    assert docs[0]["audited_count"] == 1


def test_list_document_lessons_includes_words(setup_db):
    did = _make_doc_with_lessons()
    h = _parent_headers()
    resp = _client().get(f"/api/pdf/documents/{did}/lessons", headers=h)
    assert resp.status_code == 200
    lessons = resp.json()
    assert len(lessons) == 2
    # 按 start_page 升序：第 1 课在前
    assert lessons[0]["title"] == "第 1 课"
    assert lessons[0]["audit_status"] == "approved"
    assert lessons[0]["words"][0]["word"] == "水波"


def test_audit_lesson_approve(setup_db):
    did = _make_doc_with_lessons()
    h = _parent_headers()
    lessons = _client().get(f"/api/pdf/documents/{did}/lessons", headers=h).json()
    lid = lessons[1]["id"]
    resp = _client().post(f"/api/pdf/lessons/{lid}/audit", data={"action": "通过"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["audit_status"] == "approved"


def test_extract_document_missing_file_marks_done(setup_db):
    """无真实 PDF 时提取：源文件不存在 → 返回 error，lesson 保持 pending（不启动后台任务）。"""
    from app.models import PdfDocument, Lesson
    s = SessionLocal()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="uploads/不存在.pdf")
    s.add(doc); s.flush()
    s.add(Lesson(document_id=doc.id, subject="语文", title="第 1 课", start_page=1, end_page=1, extract_status="pending", audit_status="pending"))
    s.commit()
    did = doc.id
    s.close()
    h = _parent_headers()
    resp = _client().post(f"/api/pdf/documents/{did}/extract", headers=h)
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
    s = SessionLocal()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="uploads/语文.pdf",
                      created_at=datetime(2026, 11, 4, 0, 0, 0))
    s.add(doc); s.flush()
    s.add(Lesson(document_id=doc.id, subject="语文", title="第 1 课", start_page=1, end_page=1,
                 extract_status="done", audit_status="approved"))
    s.commit()
    did = doc.id
    s.close()
    h = _parent_headers()
    lessons = _client().get(f"/api/pdf/documents/{did}/lessons", headers=h).json()
    assert lessons[0]["document_version"] == int(datetime(2026, 11, 4).timestamp() * 1000)


def test_list_lessons_version_autopopulated(setup_db):
    """未显式设 created_at 时，ORM default 自动填充，document_version 为非零时间戳。"""
    did = _make_doc_with_lessons()
    h = _parent_headers()
    lessons = _client().get(f"/api/pdf/documents/{did}/lessons", headers=h).json()
    assert lessons[0]["document_version"] > 0


def test_user_document_unique(setup_db):
    """UserDocument 唯一约束：同一孩子对同一教材只能绑定一次（Task 1）。

    注意：list 返回 grade/edition 标签的断言留给 Task 2（list_documents 尚未加这些字段）。
    """
    from app.models import PdfDocument, UserDocument
    s = SessionLocal()
    c1 = User(name="晨晨", role="child", grade=3, edition="人教")
    d = PdfDocument(filename="语文.pdf", subject="语文", storage_path="x", grade=3, edition="人教")
    s.add_all([c1, d])
    s.flush()
    s.add(UserDocument(user_id=c1.id, document_id=d.id))
    s.commit()
    # 重复绑定被唯一约束拒绝
    try:
        s.add(UserDocument(user_id=c1.id, document_id=d.id))
        s.commit()
        dup_rejected = False
    except Exception:
        s.rollback()
        dup_rejected = True
    s.close()
    assert dup_rejected is True


def test_bind_unbind_and_filter(setup_db):
    from app.models import PdfDocument
    s = SessionLocal()
    parent = make_account(s, "p_bu", "parent")
    c1 = User(name="晨晨", role="child", grade=3, parent_id=parent.id)
    c2 = User(name="乐乐", role="child", grade=4, parent_id=parent.id)
    d = PdfDocument(filename="语文.pdf", subject="语文", storage_path="x", grade=3, edition="人教")
    s.add_all([c1, c2, d]); s.flush()
    c1id, c2id, did = c1.id, c2.id, d.id
    s.commit()
    h = auth_headers(parent)

    c = _client()
    # 绑定
    r = c.post(f"/api/pdf/documents/{did}/bind", json={"user_id": c1id}, headers=h)
    assert r.status_code == 200
    # 幂等再绑
    c.post(f"/api/pdf/documents/{did}/bind", json={"user_id": c1id}, headers=h)
    # bound-users
    r = c.get(f"/api/pdf/documents/{did}/bound-users", headers=h).json()
    assert c1id in r["user_ids"]
    # 列表过滤：c1 能看到，c2 看不到
    r = c.get(f"/api/pdf/documents?user_id={c1id}", headers=h).json()
    assert len(r) == 1
    r = c.get(f"/api/pdf/documents?user_id={c2id}", headers=h).json()
    assert len(r) == 0
    # 解绑
    c.delete(f"/api/pdf/documents/{did}/bind?user_id={c1id}", headers=h)
    r = c.get(f"/api/pdf/documents?user_id={c1id}", headers=h).json()
    assert len(r) == 0


def test_list_documents_returns_tags(setup_db):
    from app.models import PdfDocument
    s = SessionLocal()
    d = PdfDocument(filename="数学.pdf", subject="数学", storage_path="y", grade=5, edition="北师大")
    s.add(d); s.commit(); did = d.id; s.close()
    h = _parent_headers()
    docs = _client().get("/api/pdf/documents", headers=h).json()
    assert any(x["id"] == did and x["grade"] == 5 and x["edition"] == "北师大" for x in docs)


def test_delete_document_cleans_bindings(setup_db):
    from app.models import PdfDocument, UserDocument
    s = SessionLocal()
    parent = make_account(s, "p_del", "parent")
    c1 = User(name="晨晨", role="child", grade=3, parent_id=parent.id)
    d = PdfDocument(filename="语文.pdf", subject="语文", storage_path="uploads/none.pdf", grade=3, edition="")
    s.add_all([c1, d]); s.flush()
    s.add(UserDocument(user_id=c1.id, document_id=d.id))
    s.commit(); did = d.id; pid = parent.id
    s.close()
    s = SessionLocal()
    h = auth_headers(s.get(User, pid))
    s.close()
    c = _client()
    c.delete(f"/api/pdf/documents/{did}", headers=h)
    s = SessionLocal()
    assert s.query(UserDocument).count() == 0
    s.close()
