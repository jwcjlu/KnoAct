"""学习类接口的 parent_required 与目标用户解析。"""
import pytest
from fastapi import HTTPException

from conftest import auth_headers, make_account
from app.core.access import child_has_parent, require_learning_access
from app.models import User


def test_child_has_parent_and_require_access(setup_db, db):
    parent = make_account(db, "mama_one", "parent")
    free = make_account(db, "kid_free", "child")
    bound = make_account(db, "kid_bound", "child", parent=parent)
    admin = make_account(db, "root_one", "admin")
    assert child_has_parent(bound) is True
    assert child_has_parent(free) is False
    assert child_has_parent(parent) is False
    with pytest.raises(HTTPException) as e:
        require_learning_access(free)
    assert e.value.status_code == 403 and e.value.detail == {"error": "parent_required"}
    for ok in (bound, parent, admin):
        require_learning_access(ok)  # 不抛


# ---------- 学习接口：未绑定家长的孩子 403 ----------

def _assert_parent_required(r):
    assert r.status_code == 403
    assert r.json()["detail"] == {"error": "parent_required"}


def test_home_snapshot_parent_required(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    free = make_account(db, "kid_free", "child")
    bound = make_account(db, "kid_bound", "child", parent=parent)
    _assert_parent_required(client.get("/api/home/snapshot", headers=auth_headers(free)))
    r = client.get("/api/home/snapshot", headers=auth_headers(bound))
    assert r.status_code == 200 and r.json()["user_name"] == "kid_bound"
    assert client.get("/api/home/snapshot").status_code == 401


def test_tasks_list_and_submit_parent_required(setup_db, client, db):
    from datetime import date
    from app.models import Task
    parent = make_account(db, "mama_one", "parent")
    free = make_account(db, "kid_free", "child")
    bound = make_account(db, "kid_bound", "child", parent=parent)
    t = Task(user_id=bound.id, date=date.today(), subject="语文", task_type="custom",
             title="读书", content_status="published")
    db.add(t); db.commit()

    url = f"/api/tasks?user_id={free.id}&date={date.today()}"
    _assert_parent_required(client.get(url, headers=auth_headers(free)))
    _assert_parent_required(client.post(f"/api/tasks/{t.id}/submit", headers=auth_headers(free)))

    r = client.get(f"/api/tasks?user_id={bound.id}&date={date.today()}", headers=auth_headers(bound))
    assert r.status_code == 200 and len(r.json()) == 1
    assert client.post(f"/api/tasks/{t.id}/submit", headers=auth_headers(bound)).json() == {"ok": True}
    # 家长不受 parent_required 影响
    assert client.get(f"/api/tasks?user_id={bound.id}&date={date.today()}&role=parent",
                      headers=auth_headers(parent)).status_code == 200


def test_learning_material_parent_required(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    free = make_account(db, "kid_free", "child")
    bound = make_account(db, "kid_bound", "child", parent=parent)
    _assert_parent_required(client.get(f"/api/listening/material?user_id={free.id}",
                                       headers=auth_headers(free)))
    _assert_parent_required(client.get(f"/api/dictation/words?user_id={free.id}",
                                       headers=auth_headers(free)))
    r = client.get(f"/api/listening/material?user_id={bound.id}", headers=auth_headers(bound))
    assert r.status_code == 200 and "text" in r.json()
    assert client.get(f"/api/dictation/words?user_id={bound.id}",
                      headers=auth_headers(bound)).status_code == 200
    assert client.get(f"/api/listening/material?user_id={bound.id}").status_code == 401


def test_binding_unlocks_learning(setup_db, client, db):
    """未绑定 → 403；绑定后同一 token 立即放行。"""
    parent = make_account(db, "mama_one", "parent")
    child = make_account(db, "kid_one", "child")
    h = auth_headers(child)
    _assert_parent_required(client.get("/api/home/snapshot", headers=h))
    code = client.post("/api/family/invite", headers=auth_headers(parent)).json()["code"]
    assert client.post("/api/family/bind", json={"code": code}, headers=h).status_code == 200
    assert client.get("/api/home/snapshot", headers=h).status_code == 200


# ---------- resolve_target_user_id（home snapshot 的 user_id 参数）----------

def test_snapshot_child_only_self(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    c1 = make_account(db, "kid_one", "child", parent=parent)
    c2 = make_account(db, "kid_two", "child", parent=parent)
    h = auth_headers(c1)
    # 缺省 = 自己
    assert client.get("/api/home/snapshot", headers=h).json()["user_name"] == "kid_one"
    assert client.get(f"/api/home/snapshot?user_id={c1.id}", headers=h).status_code == 200
    r = client.get(f"/api/home/snapshot?user_id={c2.id}", headers=h)
    assert r.status_code == 403 and r.json()["detail"] == {"error": "forbidden"}


def test_snapshot_parent_self_or_own_child(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    other = make_account(db, "mama_two", "parent")
    mine = make_account(db, "kid_one", "child", parent=parent)
    theirs = make_account(db, "kid_two", "child", parent=other)
    h = auth_headers(parent)
    r = client.get(f"/api/home/snapshot?user_id={mine.id}", headers=h)
    assert r.status_code == 200 and r.json()["user_name"] == "kid_one"
    assert client.get(f"/api/home/snapshot?user_id={parent.id}", headers=h).status_code == 200
    r = client.get(f"/api/home/snapshot?user_id={theirs.id}", headers=h)
    assert r.status_code == 403 and r.json()["detail"] == {"error": "forbidden"}
    assert client.get("/api/home/snapshot?user_id=99999", headers=h).status_code == 403


def test_snapshot_admin_any(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    child = make_account(db, "kid_one", "child", parent=parent)
    admin = make_account(db, "root_one", "admin")
    r = client.get(f"/api/home/snapshot?user_id={child.id}", headers=auth_headers(admin))
    assert r.status_code == 200 and r.json()["user_name"] == "kid_one"
