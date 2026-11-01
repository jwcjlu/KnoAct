from app.models import Annotation
from conftest import make_lesson, make_user


def _saved(db, annotation_id):
    db.rollback()  # 结束测试会话的读事务，才能看到接口里提交的新行
    return db.get(Annotation, annotation_id)


def test_add_annotation_defaults_to_first_child(client, db):
    make_user(db, name="家长", role="parent")
    child = make_user(db, name="金同学")
    lesson = make_lesson(db)
    db.commit()
    child_id, lesson_id = child.id, lesson.id
    r = client.post("/api/annotations", json={"lesson_id": lesson_id, "quote": "桂花"}).json()
    assert r["quote"] == "桂花"
    assert _saved(db, r["id"]).user_id == child_id


def test_add_annotation_uses_given_user(client, db):
    make_user(db, name="金同学")
    other = make_user(db, name="李同学")
    lesson = make_lesson(db)
    db.commit()
    other_id, lesson_id = other.id, lesson.id
    r = client.post("/api/annotations", json={"lesson_id": lesson_id, "quote": "桂花", "user_id": other_id}).json()
    assert _saved(db, r["id"]).user_id == other_id


def test_add_annotation_without_child_reports_error(client, db):
    lesson = make_lesson(db)
    db.commit()
    r = client.post("/api/annotations", json={"lesson_id": lesson.id, "quote": "桂花"}).json()
    assert "error" in r
    db.rollback()
    assert db.query(Annotation).count() == 0


def test_glossary_saves_annotation_for_child(client, db):
    child = make_user(db, name="金同学")
    lesson = make_lesson(db)
    db.commit()
    child_id, lesson_id = child.id, lesson.id
    r = client.post("/api/annotations/glossary", json={"lesson_id": lesson_id, "quote": "糕饼"}).json()
    a = _saved(db, r["id"])
    assert a.kind == "glossary" and a.user_id == child_id
