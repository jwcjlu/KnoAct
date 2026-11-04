"""孩子档案与学年桶 API 测试。"""
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User


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
    resp = _client().post("/api/children", json={
        "parent_id": parent, "name": "新孩子", "grade": 2, "edition": "苏教版",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["grade"] == 2
    buckets = _client().get(f"/api/buckets?user_id={data['id']}").json()
    assert any(b["status"] == "active" and b["grade"] == 2 for b in buckets)


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
