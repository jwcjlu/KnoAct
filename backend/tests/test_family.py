"""家庭绑定 API：邀请码 / 绑定 / 申请审批 / 解绑。"""
from datetime import datetime, timedelta

from conftest import auth_headers, make_account
from app.models import FamilyBindRequest, FamilyInvite, User


def _invite(client, parent):
    r = client.post("/api/family/invite", headers=auth_headers(parent))
    assert r.status_code == 200
    return r.json()


def test_invite_requires_parent(setup_db, client, db):
    child = make_account(db, "kid_one", "child")
    assert client.post("/api/family/invite").status_code == 401
    assert client.post("/api/family/invite", headers=auth_headers(child)).status_code == 403


def test_invite_and_bind_flow(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    child = make_account(db, "kid_one", "child")
    body = _invite(client, parent)
    assert body["code"] and body["expires_at"]
    row = db.query(FamilyInvite).filter_by(code=body["code"]).one()
    assert row.parent_id == parent.id
    assert timedelta(hours=23) < row.expires_at - datetime.utcnow() <= timedelta(hours=24)

    r = client.post("/api/family/bind", json={"code": body["code"]}, headers=auth_headers(child))
    assert r.status_code == 200 and r.json()["parent_id"] == parent.id
    db.expire_all()
    assert db.get(User, child.id).parent_id == parent.id
    assert db.query(FamilyInvite).filter_by(code=body["code"]).one().used_by_child_id == child.id


def test_bind_code_single_use(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    c1 = make_account(db, "kid_one", "child")
    c2 = make_account(db, "kid_two", "child")
    code = _invite(client, parent)["code"]
    assert client.post("/api/family/bind", json={"code": code}, headers=auth_headers(c1)).status_code == 200
    r = client.post("/api/family/bind", json={"code": code}, headers=auth_headers(c2))
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "code_used"


def test_bind_invalid_and_expired_code(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    child = make_account(db, "kid_one", "child")
    h = auth_headers(child)
    assert client.post("/api/family/bind", json={"code": "NOPE"}, headers=h).status_code == 404
    code = _invite(client, parent)["code"]
    inv = db.query(FamilyInvite).filter_by(code=code).one()
    inv.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    r = client.post("/api/family/bind", json={"code": code}, headers=h)
    assert r.status_code == 400 and r.json()["detail"]["error"] == "code_expired"
    db.expire_all()
    assert db.get(User, child.id).parent_id is None


def test_bind_requires_child(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    other = make_account(db, "mama_two", "parent")
    code = _invite(client, parent)["code"]
    r = client.post("/api/family/bind", json={"code": code}, headers=auth_headers(other))
    assert r.status_code == 403


def test_bind_already_bound(setup_db, client, db):
    p1 = make_account(db, "mama_one", "parent")
    p2 = make_account(db, "mama_two", "parent")
    child = make_account(db, "kid_one", "child", parent=p1)
    code = _invite(client, p2)["code"]
    r = client.post("/api/family/bind", json={"code": code}, headers=auth_headers(child))
    assert r.status_code == 409 and r.json()["detail"]["error"] == "already_bound"


def test_request_approve_flow(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    child = make_account(db, "kid_one", "child")
    r = client.post("/api/family/request", json={"parent_login_name": "mama_one"},
                    headers=auth_headers(child))
    assert r.status_code == 200 and r.json()["status"] == "pending"
    rid = r.json()["id"]
    # 重复申请幂等
    again = client.post("/api/family/request", json={"parent_login_name": "mama_one"},
                        headers=auth_headers(child))
    assert again.json()["id"] == rid

    lst = client.get("/api/family/requests", headers=auth_headers(parent)).json()
    assert [x["id"] for x in lst] == [rid]
    assert lst[0]["child_id"] == child.id and lst[0]["child_login_name"] == "kid_one"

    ok = client.post(f"/api/family/requests/{rid}/approve", headers=auth_headers(parent))
    assert ok.status_code == 200
    db.expire_all()
    assert db.get(User, child.id).parent_id == parent.id
    assert db.get(FamilyBindRequest, rid).status == "approved"
    assert client.get("/api/family/requests", headers=auth_headers(parent)).json() == []
    # 已处理不可再批
    assert client.post(f"/api/family/requests/{rid}/approve",
                       headers=auth_headers(parent)).status_code == 409


def test_request_reject_flow(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    child = make_account(db, "kid_one", "child")
    rid = client.post("/api/family/request", json={"parent_login_name": "mama_one"},
                      headers=auth_headers(child)).json()["id"]
    r = client.post(f"/api/family/requests/{rid}/reject", headers=auth_headers(parent))
    assert r.status_code == 200
    db.expire_all()
    assert db.get(User, child.id).parent_id is None
    assert db.get(FamilyBindRequest, rid).status == "rejected"
    assert client.get("/api/family/requests", headers=auth_headers(parent)).json() == []


def test_request_unknown_parent_or_wrong_role(setup_db, client, db):
    make_account(db, "kid_two", "child")
    child = make_account(db, "kid_one", "child")
    h = auth_headers(child)
    # 不存在的家长 / 目标不是家长
    assert client.post("/api/family/request", json={"parent_login_name": "ghost"},
                       headers=h).status_code == 404
    assert client.post("/api/family/request", json={"parent_login_name": "kid_two"},
                       headers=h).status_code == 404


def test_other_parent_cannot_handle_request(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    other = make_account(db, "mama_two", "parent")
    child = make_account(db, "kid_one", "child")
    rid = client.post("/api/family/request", json={"parent_login_name": "mama_one"},
                      headers=auth_headers(child)).json()["id"]
    assert client.get("/api/family/requests", headers=auth_headers(other)).json() == []
    assert client.post(f"/api/family/requests/{rid}/approve",
                       headers=auth_headers(other)).status_code == 404
    assert client.post(f"/api/family/requests/{rid}/reject",
                       headers=auth_headers(child)).status_code == 403
    assert client.get("/api/family/requests", headers=auth_headers(child)).status_code == 403


def test_unbind(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    other = make_account(db, "mama_two", "parent")
    child = make_account(db, "kid_one", "child", parent=parent)
    # 别的家长不能解绑
    r = client.post("/api/family/unbind", json={"child_id": child.id}, headers=auth_headers(other))
    assert r.status_code == 404
    db.expire_all()
    assert db.get(User, child.id).parent_id == parent.id
    # 孩子自己不能解绑
    assert client.post("/api/family/unbind", json={"child_id": child.id},
                       headers=auth_headers(child)).status_code == 403
    r = client.post("/api/family/unbind", json={"child_id": child.id}, headers=auth_headers(parent))
    assert r.status_code == 200
    db.expire_all()
    assert db.get(User, child.id).parent_id is None
