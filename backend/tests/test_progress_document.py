"""学习进度按「孩子 + 教材」的接口测试。"""
import json

from app.database import SessionLocal
from app.models import (
    LearningProgress, Lesson, PdfDocument, User, UserDocument,
)


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.progress import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _headers(user):
    from app.services.security import create_access_token

    tok = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {tok}"}


def _setup_two_books(db):
    parent = User(name="家长", role="parent")
    db.add(parent)
    db.flush()
    child = User(name="孩子", role="child", parent_id=parent.id)
    db.add(child)
    db.flush()

    docs = []
    for name in ("语文上册.pdf", "语文下册.pdf"):
        d = PdfDocument(filename=name, subject="语文", storage_path=f"/{name}")
        db.add(d)
        db.flush()
        db.add(UserDocument(user_id=child.id, document_id=d.id))
        for i, title in enumerate(["第1课", "第2课", "第3课"], start=1):
            db.add(Lesson(document_id=d.id, subject="语文", title=title,
                          start_page=i, end_page=i, audit_status="approved"))
        docs.append(d)
    db.commit()
    return parent, child, docs


def test_overview_lists_each_bound_document(setup_db, db):
    parent, child, docs = _setup_two_books(db)
    r = _client().get(f"/api/progress/overview?user_id={child.id}",
                      headers=_headers(parent))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 2, f"两本都要列出来，实际 {len(items)}"
    names = {it["document_name"] for it in items}
    assert names == {"语文上册.pdf", "语文下册.pdf"}
    for it in items:
        assert it["total"] == 3
        assert it["current"] == 1          # 没设过进度 → 第一课
        assert len(it["lessons"]) == 3


def test_adjust_sets_progress_per_document(setup_db, db):
    """给第二本书设到第 3 课，第一本不受影响。"""
    parent, child, docs = _setup_two_books(db)
    book2 = docs[1]
    lesson3 = (db.query(Lesson).filter_by(document_id=book2.id)
               .order_by(Lesson.id).all())[2]

    r = _client().post("/api/progress/adjust", headers=_headers(parent), json={
        "user_id": child.id, "lesson_id": lesson3.id, "document_id": book2.id,
    })
    assert r.status_code == 200, r.text
    assert r.json()["current"] == 3
    assert r.json()["total"] == 3

    items = _client().get(f"/api/progress/overview?user_id={child.id}",
                          headers=_headers(parent)).json()["items"]
    by_doc = {it["document_id"]: it for it in items}
    assert by_doc[book2.id]["current"] == 3
    assert by_doc[docs[0].id]["current"] == 1, "另一本不该被改"


def test_progress_rows_are_independent(setup_db, db):
    """两本书各有自己的 LearningProgress 行。"""
    parent, child, docs = _setup_two_books(db)
    book1, book2 = docs
    l1 = db.query(Lesson).filter_by(document_id=book1.id).order_by(Lesson.id).first()
    l2 = db.query(Lesson).filter_by(document_id=book2.id).order_by(Lesson.id).all()[1]

    c = _client()
    for doc, lesson in ((book1, l1), (book2, l2)):
        r = c.post("/api/progress/adjust", headers=_headers(parent), json={
            "user_id": child.id, "lesson_id": lesson.id, "document_id": doc.id,
        })
        assert r.status_code == 200, r.text

    rows = db.query(LearningProgress).filter_by(user_id=child.id).all()
    assert len(rows) == 2, f"每本一条，实际 {len(rows)}"
    assert {r.document_id for r in rows} == {book1.id, book2.id}


def test_adjust_survives_legacy_subject_unique(setup_db, db):
    """生产库若仍留着 uq_progress_user_subject：换另一本同科教材 adjust 不得 500。"""
    from sqlalchemy import text

    parent, child, docs = _setup_two_books(db)
    book1, book2 = docs
    l1 = db.query(Lesson).filter_by(document_id=book1.id).order_by(Lesson.id).first()
    l2 = db.query(Lesson).filter_by(document_id=book2.id).order_by(Lesson.id).all()[1]
    c = _client()
    assert c.post("/api/progress/adjust", headers=_headers(parent), json={
        "user_id": child.id, "lesson_id": l1.id, "document_id": book1.id,
    }).status_code == 200

    # 模拟未迁完的 MySQL：额外挂上旧的 (user_id, subject) 唯一约束
    db.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_progress_user_subject "
        "ON learning_progress (user_id, subject)"
    ))
    db.commit()

    r = c.post("/api/progress/adjust", headers=_headers(parent), json={
        "user_id": child.id, "lesson_id": l2.id, "document_id": book2.id,
    })
    assert r.status_code == 200, r.text
    assert r.json()["document_id"] == book2.id
    assert r.json()["current"] == 2
    rows = db.query(LearningProgress).filter_by(user_id=child.id).all()
    assert any(row.document_id == book2.id and row.current_lesson_id == l2.id for row in rows)


def test_adjust_rejects_unknown_lesson(setup_db, db):
    parent, child, _docs = _setup_two_books(db)
    r = _client().post("/api/progress/adjust", headers=_headers(parent), json={
        "user_id": child.id, "lesson_id": 999999, "subject": "语文",
    })
    assert r.status_code == 404


def test_adjust_requires_access_to_child(setup_db, db):
    """别的家长不能改这个孩子的进度。"""
    _parent, child, docs = _setup_two_books(db)
    other = User(name="别的家长", role="parent")
    db.add(other)
    db.commit()
    lesson = db.query(Lesson).filter_by(document_id=docs[0].id).first()

    r = _client().post("/api/progress/adjust", headers=_headers(other), json={
        "user_id": child.id, "lesson_id": lesson.id,
    })
    assert r.status_code in (403, 404), r.text
