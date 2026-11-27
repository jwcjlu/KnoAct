from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.pdf import router as pdf_router
from app.database import SessionLocal
from app.models import User
from conftest import auth_headers, make_account, parent_child


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
    assert "kind" in lessons[0]["words"][0]


def test_update_lesson_content_chinese_requires_kind(setup_db):
    from app.models import PdfDocument, Lesson
    s = SessionLocal()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="x")
    s.add(doc); s.flush()
    lesson = Lesson(document_id=doc.id, subject="语文", title="第 1 课", start_page=1, end_page=2,
                    extract_status="done", audit_status="approved")
    s.add(lesson); s.commit(); lid = lesson.id; s.close()
    h = _parent_headers()
    resp = _client().put(f"/api/pdf/lessons/{lid}/content", headers=h, json={
        "title": "第 1 课",
        "words": [{"word": "箩", "extra": ""}],
        "points": [],
    })
    assert resp.json().get("error")


def test_update_lesson_content_kind_change_drops_mastery(setup_db):
    from app.models import PdfDocument, Lesson, WordBank, WordMastery, User
    s = SessionLocal()
    user = User(name="孩", role="child")
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="x")
    s.add_all([user, doc]); s.flush()
    lesson = Lesson(document_id=doc.id, subject="语文", title="课", start_page=1, end_page=2,
                    extract_status="done", audit_status="approved")
    s.add(lesson); s.flush()
    row = WordBank(lesson_id=lesson.id, subject="语文", word="箩", extra="", kind="recognize")
    s.add(row); s.flush()
    mastery = WordMastery(word_bank_id=row.id, user_id=user.id, correct_count=3, mastery=0.9)
    s.add(mastery); s.commit()
    lid, wid, mid, uid = lesson.id, row.id, mastery.id, user.id
    s.close()

    h = _parent_headers()
    resp = _client().put(f"/api/pdf/lessons/{lid}/content", headers=h, json={
        "title": "课",
        "words": [{"id": wid, "word": "箩", "extra": "luó", "kind": "write"}],
        "points": [],
    })
    assert resp.json().get("ok") is True
    s = SessionLocal()
    words = s.query(WordBank).filter_by(lesson_id=lid).all()
    assert len(words) == 1
    assert words[0].kind == "write"
    assert s.get(WordMastery, mid) is None
    assert s.query(WordMastery).filter_by(word_bank_id=words[0].id, user_id=uid).count() == 0
    s.close()


def test_update_lesson_content_same_kind_keeps_mastery(setup_db):
    from app.models import PdfDocument, Lesson, WordBank, WordMastery, User
    s = SessionLocal()
    user = User(name="孩2", role="child")
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="x")
    s.add_all([user, doc]); s.flush()
    lesson = Lesson(document_id=doc.id, subject="语文", title="课", start_page=1, end_page=2,
                    extract_status="done", audit_status="approved")
    s.add(lesson); s.flush()
    row = WordBank(lesson_id=lesson.id, subject="语文", word="枚", extra="", kind="phrase")
    s.add(row); s.flush()
    mastery = WordMastery(word_bank_id=row.id, user_id=user.id, correct_count=1)
    s.add(mastery); s.commit()
    lid, wid, mid = lesson.id, row.id, mastery.id
    s.close()

    h = _parent_headers()
    resp = _client().put(f"/api/pdf/lessons/{lid}/content", headers=h, json={
        "title": "课",
        "words": [{"id": wid, "word": "一枚", "extra": "yī méi", "kind": "phrase"}],
        "points": [],
    })
    assert resp.json().get("ok") is True
    s = SessionLocal()
    assert s.get(WordBank, wid).word == "一枚"
    assert s.get(WordMastery, mid).word_bank_id == wid
    s.close()


def test_audit_lesson_approve(setup_db):
    did = _make_doc_with_lessons()
    h = _parent_headers()
    lessons = _client().get(f"/api/pdf/documents/{did}/lessons", headers=h).json()
    lid = lessons[1]["id"]
    resp = _client().post(f"/api/pdf/lessons/{lid}/audit", data={"action": "通过"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["audit_status"] == "approved"


def test_update_lesson_content_edits_words_and_keeps_mastery(setup_db):
    from app.models import PdfDocument, Lesson, WordBank, KnowledgePoint, WordMastery, User
    s = SessionLocal()
    user = User(name="晨晨", role="child")
    doc = PdfDocument(filename="英语.pdf", subject="英语", storage_path="x")
    s.add_all([user, doc]); s.flush()
    lesson = Lesson(document_id=doc.id, subject="英语", title="旧课名", start_page=1, end_page=2,
                    extract_status="done", audit_status="approved")
    s.add(lesson); s.flush()
    keep = WordBank(lesson_id=lesson.id, subject="英语", word="go jogging", extra="旧")
    drop = WordBank(lesson_id=lesson.id, subject="英语", word="gone", extra="x")
    point = KnowledgePoint(lesson_id=lesson.id, subject="英语", category="本课", content="旧知识点")
    s.add_all([keep, drop, point]); s.flush()
    mastery = WordMastery(word_bank_id=keep.id, user_id=user.id, correct_count=2, mastery=0.8)
    dropped_m = WordMastery(word_bank_id=drop.id, user_id=user.id, correct_count=1)
    s.add_all([mastery, dropped_m]); s.commit()
    lid, keep_id, point_id, mastery_id, dropped_id = lesson.id, keep.id, point.id, mastery.id, dropped_m.id
    s.close()

    h = _parent_headers()
    resp = _client().put(f"/api/pdf/lessons/{lid}/content", headers=h, json={
        "title": "新课名",
        "words": [
            {"id": keep_id, "word": "go jogging", "extra": "去慢跑"},
            {"word": "busy", "extra": "*忙碌的"},
        ],
        "points": [
            {"id": point_id, "content": "一般现在时", "category": "语法"},
            {"content": "新知识点"},
        ],
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    s = SessionLocal()
    assert s.get(Lesson, lid).title == "新课名"
    words = [(w.word, w.extra) for w in s.query(WordBank).filter_by(lesson_id=lid).order_by(WordBank.id).all()]
    assert words == [("go jogging", "去慢跑"), ("busy", "*忙碌的")]
    moved = s.get(WordMastery, mastery_id)
    assert moved.word_bank_id == keep_id and moved.correct_count == 2
    assert s.get(WordMastery, dropped_id) is None
    contents = [p.content for p in s.query(KnowledgePoint).filter_by(lesson_id=lid).all()]
    assert contents == ["一般现在时", "新知识点"] or set(contents) == {"一般现在时", "新知识点"}
    s.close()


def test_update_lesson_content_rejects_blank_title(setup_db):
    from app.models import PdfDocument, Lesson
    s = SessionLocal()
    doc = PdfDocument(filename="英语.pdf", subject="英语", storage_path="x")
    s.add(doc); s.flush()
    lesson = Lesson(document_id=doc.id, subject="英语", title="旧课名", start_page=1, end_page=2,
                    extract_status="done", audit_status="pending")
    s.add(lesson); s.commit(); lid = lesson.id; s.close()
    h = _parent_headers()
    resp = _client().put(f"/api/pdf/lessons/{lid}/content", headers=h, json={
        "title": "  ", "words": [{"word": "x" * 65}], "points": [],
    })
    assert resp.json()["error"] == "课名不能为空"
    s = SessionLocal()
    assert s.get(Lesson, lid).title == "旧课名"
    s.close()


def test_audit_withdraw_sets_pending(setup_db):
    did = _make_doc_with_lessons()
    h = _parent_headers()
    lessons = _client().get(f"/api/pdf/documents/{did}/lessons", headers=h).json()
    lid = lessons[0]["id"]
    assert lessons[0]["audit_status"] == "approved"
    resp = _client().post(f"/api/pdf/lessons/{lid}/audit", data={"action": "撤回"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["audit_status"] == "pending"


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


def test_extract_done_english_syncs_word_list(setup_db, tmp_path, monkeypatch):
    """英语课都已提取过时，再点提取会按书末 Word list 回填生词，而不是直接说没有可提取课程。"""
    from app.models import PdfDocument, Lesson
    pdf = tmp_path / "en.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    s = SessionLocal()
    doc = PdfDocument(filename="英语.pdf", subject="英语", storage_path=str(pdf))
    s.add(doc); s.flush()
    s.add(Lesson(document_id=doc.id, subject="英语", title="What do we do at the weekend?",
                 start_page=8, end_page=19, extract_status="done", audit_status="approved"))
    s.commit()
    did = doc.id
    s.close()
    called = {}

    def fake_apply(db, document_id, pdf_path):
        called["id"] = document_id
        return {"units": 1, "words": 2}

    monkeypatch.setattr("app.routers.pdf.apply_word_list", fake_apply)
    h = _parent_headers()
    resp = _client().post(f"/api/pdf/documents/{did}/extract", headers=h)
    assert resp.status_code == 200
    assert resp.json().get("word_list") is True
    assert called["id"] == did
    prog = _client().get(f"/api/pdf/documents/{did}/extract/progress", headers=h).json()
    assert prog["finished"] is True


def test_extract_done_chinese_syncs_word_tables(setup_db, tmp_path, monkeypatch):
    """语文课都已提取过时，再点提取会按册末字词表回填生词，而不是直接说没有可提取课程。"""
    from app.models import PdfDocument, Lesson
    pdf = tmp_path / "cn.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    s = SessionLocal()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path=str(pdf))
    s.add(doc); s.flush()
    s.add(Lesson(document_id=doc.id, subject="语文", title="第 1 课",
                 start_page=1, end_page=10, extract_status="done", audit_status="approved"))
    s.commit()
    did = doc.id
    s.close()
    called = {}

    def fake_apply(db, document_id, pdf_path):
        called["id"] = document_id
        return {"tables": 1, "lessons": 1, "words": 3}

    monkeypatch.setattr("app.routers.pdf.apply_chinese_word_tables", fake_apply)
    h = _parent_headers()
    resp = _client().post(f"/api/pdf/documents/{did}/extract", headers=h)
    assert resp.status_code == 200
    assert resp.json().get("chinese_word_tables") is True
    assert called["id"] == did
    prog = _client().get(f"/api/pdf/documents/{did}/extract/progress", headers=h).json()
    assert prog["finished"] is True


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


def test_child_list_documents_bound_only(setup_db):
    """学生（已绑定家长）GET /documents 仅返回本人已绑定教材；GET .../lessons 仅绑定可读。"""
    from app.models import Lesson, PdfDocument, UserDocument
    s = SessionLocal()
    parent, child, _, hc = parent_child(s, "pdf_child")
    d1 = PdfDocument(filename="a.pdf", subject="语文", storage_path="uploads/a.pdf")
    d2 = PdfDocument(filename="b.pdf", subject="数学", storage_path="uploads/b.pdf")
    s.add_all([d1, d2]); s.flush()
    s.add(Lesson(document_id=d1.id, subject="语文", title="第 1 课", start_page=1, end_page=1,
                  extract_status="done", audit_status="approved"))
    s.add(UserDocument(user_id=child.id, document_id=d1.id))
    s.commit()
    did1, did2 = d1.id, d2.id
    s.close()

    c = _client()
    docs = c.get("/api/pdf/documents", headers=hc).json()
    assert len(docs) == 1 and docs[0]["id"] == did1
    assert c.get(f"/api/pdf/documents/{did1}/lessons", headers=hc).status_code == 200
    r403 = c.get(f"/api/pdf/documents/{did2}/lessons", headers=hc)
    assert r403.status_code == 403
    assert r403.json()["detail"] == {"error": "forbidden"}


def test_child_without_parent_cannot_read_pdf(setup_db):
    from app.models import PdfDocument, User, UserDocument
    s = SessionLocal()
    child = User(name="孤儿孩", role="child", parent_id=None)
    d = PdfDocument(filename="a.pdf", subject="语文", storage_path="uploads/a.pdf")
    s.add_all([child, d]); s.flush()
    s.add(UserDocument(user_id=child.id, document_id=d.id))
    s.commit()
    hid = child.id
    did = d.id
    s.close()
    s = SessionLocal()
    h = auth_headers(s.get(User, hid))
    s.close()
    c = _client()
    assert c.get("/api/pdf/documents", headers=h).status_code == 403
    assert c.get(f"/api/pdf/documents/{did}/lessons", headers=h).status_code == 403


def test_upload_handout_skips_lesson_split(client, db, monkeypatch):
    from app.models import Lesson
    from app.routers import pdf as pdf_module
    monkeypatch.setattr(pdf_module, "render_pages", lambda *a, **k: [])
    called = {"detect": False}

    def fake_detect(*a, **k):
        called["detect"] = True
        return []

    monkeypatch.setattr(pdf_module, "detect_lessons_from_pdf", fake_detect)
    parent = make_account(db, "ph_parent", "parent")
    h = auth_headers(parent)
    files = {"file": ("h.pdf", b"%PDF-1.4 fake", "application/pdf")}
    r = client.post(
        "/api/pdf/upload",
        data={"subject": "英语", "content_kind": "handout", "handout_kind": "phrase"},
        files=files,
        headers=h,
    )
    assert r.status_code == 200
    assert called["detect"] is False
    assert db.query(Lesson).count() == 0
