"""孩子档案与学年桶 API 测试。"""
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User
from conftest import auth_headers


def _client():
    return TestClient(app)


def _add_user(name, role, **kw):
    s = SessionLocal()
    u = User(name=name, role=role, **kw)
    s.add(u); s.commit(); s.flush()
    uid = u.id
    s.close()
    return uid


def test_list_children_filters_by_parent(setup_db):
    parent = _add_user("金爸爸", "parent")
    c1 = _add_user("晨晨", "child", parent_id=parent, grade=3)
    _add_user("林晨", "child", grade=4)  # 别的家长的孩子
    resp = _client().get(f"/api/users?role=child&parent_id={parent}")
    data = resp.json()
    assert [u["id"] for u in data] == [c1]


def test_create_child_builds_bucket(setup_db):
    parent = _add_user("金爸爸", "parent")
    s = SessionLocal()
    headers = auth_headers(s.get(User, parent))
    s.close()
    resp = _client().post("/api/children", json={
        "parent_id": parent, "name": "新孩子", "grade": 2, "edition": "苏教版",
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["grade"] == 2
    buckets = _client().get(f"/api/buckets?user_id={data['id']}").json()
    assert any(b["status"] == "active" and b["grade"] == 2 for b in buckets)


def test_create_child_requires_own_parent_token(setup_db, client, db):
    from conftest import auth_headers as ah
    p1 = User(name="p1", role="parent"); p2 = User(name="p2", role="parent")
    kid = User(name="k", role="child"); admin = User(name="a", role="admin")
    db.add_all([p1, p2, kid, admin]); db.commit()
    body = {"parent_id": p1.id, "name": "新孩子", "grade": 2}
    assert client.post("/api/children", json=body).status_code == 401
    for u in (kid, admin):
        assert client.post("/api/children", json=body, headers=ah(u)).status_code == 403
    # 家长不能替别的家长建孩子
    r = client.post("/api/children", json=body, headers=ah(p2))
    assert r.status_code == 403 and r.json()["detail"] == {"error": "forbidden"}
    assert client.post("/api/children", json=body, headers=ah(p1)).status_code == 200


def test_promote_grade_endpoint(setup_db):
    child = _add_user("晨晨", "child", grade=3)
    # 真实流程中孩子必有 active 桶（create_child 会 ensure_bucket）；这里补齐前置状态。
    from app.services.bucket_service import ensure_bucket
    s = SessionLocal()
    ensure_bucket(s, child)
    s.close()
    resp = _client().post(f"/api/children/{child}/promote")
    assert resp.status_code == 200
    assert resp.json()["grade"] == 4
    buckets = _client().get(f"/api/buckets?user_id={child}").json()
    assert any(b["status"] == "archived" and b["grade"] == 3 for b in buckets)
    assert any(b["status"] == "active" and b["grade"] == 4 for b in buckets)


def test_archived_child_login_rejected(setup_db, client, db, monkeypatch):
    monkeypatch.setenv("KNOACT_LEGACY_NAME_LOGIN", "1")
    c = User(name="晨晨", role="child", status="archived")
    db.add(c); db.commit()
    r = client.post("/api/auth/login", json={"name": "晨晨"})
    assert r.status_code == 403


def test_edit_child_updates_fields(setup_db, client, db):
    c = User(name="晨晨", role="child", grade=3, edition="人教")
    db.add(c); db.commit()
    r = client.put(f"/api/children/{c.id}", json={"name": "晨晨2", "grade": 5, "edition": "北师大"})
    assert r.status_code == 200
    assert r.json()["grade"] == 5
    assert r.json()["edition"] == "北师大"
    assert r.json()["name"] == "晨晨2"


def test_archive_unarchive_idempotent(setup_db, client, db):
    c = User(name="晨晨", role="child", grade=3)
    db.add(c); db.commit()
    assert client.post(f"/api/children/{c.id}/archive").json() == {"ok": True}
    assert client.post(f"/api/children/{c.id}/archive").json() == {"ok": True}
    db.expire_all()
    assert db.get(User, c.id).status == "archived"
    assert client.post(f"/api/children/{c.id}/unarchive").json() == {"ok": True}
    db.expire_all()
    assert db.get(User, c.id).status == "active"


def test_child_documents_listing(setup_db, client, db):
    from app.models import PdfDocument, UserDocument
    c = User(name="晨晨", role="child", grade=3)
    d = PdfDocument(filename="语文.pdf", subject="语文", storage_path="", grade=3, edition="人教")
    db.add_all([c, d]); db.flush()
    db.add(UserDocument(user_id=c.id, document_id=d.id))
    db.commit()
    r = client.get(f"/api/children/{c.id}/documents").json()
    assert len(r["documents"]) == 1
    assert r["documents"][0]["filename"] == "语文.pdf"


def test_users_include_archived(setup_db, client, db):
    db.add(User(name="活跃", role="child", status="active"))
    db.add(User(name="归档", role="child", status="archived"))
    db.commit()
    active = client.get("/api/users?role=child").json()
    assert all(u["name"] != "归档" for u in active)
    allu = client.get("/api/users?role=child&include_archived=1").json()
    assert any(u["name"] == "归档" for u in allu)


def test_archived_child_excluded_from_daily_tasks(setup_db, db):
    from app.models import PdfDocument, Lesson, UserDocument, WordBank, KnowledgePoint, Text, Task
    from app.services.task_gen import generate_daily_tasks
    from datetime import date
    c = User(name="归档孩子", role="child", status="archived")
    db.add(c); db.flush()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l = Lesson(document_id=doc.id, subject="语文", title="第1课", start_page=1, end_page=1, extract_status="done", audit_status="approved")
    db.add(l); db.flush()
    db.add(WordBank(lesson_id=l.id, subject="语文", word="白鹭", extra="x"))
    db.add(KnowledgePoint(subject="语文", category="字词", content="形近字", lesson_id=l.id))
    db.add(Text(lesson_id=l.id, content="白鹭是一首精巧的诗。"))
    db.add(UserDocument(user_id=c.id, document_id=doc.id))
    db.commit()
    generate_daily_tasks(db, date.today())
    assert db.query(Task).filter_by(user_id=c.id, date=date.today()).count() == 0
