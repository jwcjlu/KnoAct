from app.models import Annotation
from conftest import make_lesson, make_user, auth_headers
from app.database import SessionLocal


def _saved(db, annotation_id):
    db.rollback()  # 结束测试会话的读事务，才能看到接口里提交的新行
    return db.get(Annotation, annotation_id)


def _child_and_headers():
    s = SessionLocal()
    parent = make_user(s, name="家长", role="parent")
    child = make_user(s, name="金同学")
    child.parent_id = parent.id
    lesson = make_lesson(s)
    from app.models import UserDocument
    s.add(UserDocument(user_id=child.id, document_id=lesson.document_id))
    s.commit()
    h = auth_headers(child)
    lid, cid = lesson.id, child.id
    s.close()
    return lid, cid, h


def test_add_annotation_for_bound_child(client, db):
    lid, child_id, h = _child_and_headers()
    r = client.post("/api/annotations", json={"lesson_id": lid, "quote": "桂花"}, headers=h).json()
    assert r["quote"] == "桂花"
    assert _saved(db, r["id"]).user_id == child_id


def test_add_annotation_parent_for_child(client, db):
    s = SessionLocal()
    parent = make_user(s, name="家长2", role="parent")
    a = make_user(s, name="孩子甲")
    b = make_user(s, name="孩子乙")
    a.parent_id = parent.id
    b.parent_id = parent.id
    lesson = make_lesson(s)
    from app.models import UserDocument
    for cid in (a.id, b.id):
        s.add(UserDocument(user_id=cid, document_id=lesson.document_id))
    s.commit()
    hp = auth_headers(parent)
    lid, other_id = lesson.id, b.id
    s.close()
    r = client.post(
        "/api/annotations",
        json={"lesson_id": lid, "quote": "桂花", "user_id": other_id},
        headers=hp,
    ).json()
    assert _saved(db, r["id"]).user_id == other_id


def test_add_annotation_without_bind_403(client, db):
    s = SessionLocal()
    child = make_user(s, name="未绑孩子")
    parent = make_user(s, name="父", role="parent")
    child.parent_id = parent.id
    lesson = make_lesson(s)
    s.commit()
    h = auth_headers(child)
    lid = lesson.id
    s.close()
    r = client.post("/api/annotations", json={"lesson_id": lid, "quote": "桂花"}, headers=h)
    assert r.status_code == 403
    db.rollback()
    assert db.query(Annotation).count() == 0


def test_glossary_saves_annotation_for_child(client, db):
    lid, child_id, h = _child_and_headers()
    r = client.post("/api/annotations/glossary", json={"lesson_id": lid, "quote": "糕饼"}, headers=h).json()
    a = _saved(db, r["id"])
    assert a.kind == "glossary" and a.user_id == child_id
