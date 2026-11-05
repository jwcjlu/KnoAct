"""管理员用户管理 API。"""
from conftest import auth_headers, make_account
from app.models import RefreshToken, User, SchoolYearBucket


def _admin(db):
    return make_account(db, "root_one", "admin")


def test_requires_admin(setup_db, client, db):
    parent = make_account(db, "mama_one", "parent")
    assert client.get("/api/admin/users").status_code == 401
    r = client.get("/api/admin/users", headers=auth_headers(parent))
    assert r.status_code == 403 and r.json()["detail"] == {"error": "forbidden"}
    r = client.post("/api/admin/users", headers=auth_headers(parent),
                    json={"login_name": "kid_x1", "password": "abc12345", "role": "child"})
    assert r.status_code == 403


def test_create_child_with_parent_and_bucket(setup_db, client, db):
    admin = _admin(db)
    parent = make_account(db, "mama_one", "parent")
    r = client.post("/api/admin/users", headers=auth_headers(admin), json={
        "login_name": "kid_one", "password": "abc12345", "role": "child",
        "parent_id": parent.id, "grade": 3, "edition": "人教版",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["role"] == "child" and data["parent_id"] == parent.id and data["grade"] == 3
    buckets = db.query(SchoolYearBucket).filter_by(user_id=data["id"]).all()
    assert any(b.status == "active" and b.grade == 3 for b in buckets)


def test_create_validation(setup_db, client, db):
    admin = _admin(db)
    h = auth_headers(admin)
    base = {"login_name": "kid_one", "password": "abc12345", "role": "child"}
    assert client.post("/api/admin/users", headers=h, json={**base, "role": "admin"}).status_code == 400
    assert client.post("/api/admin/users", headers=h, json={**base, "password": "x"}).json()["detail"] == {"error": "weak_password"}
    assert client.post("/api/admin/users", headers=h, json={**base, "parent_id": 9999}).json()["detail"] == {"error": "invalid_parent"}
    assert client.post("/api/admin/users", headers=h, json=base).status_code == 200
    assert client.post("/api/admin/users", headers=h, json=base).status_code == 409
    r = client.post("/api/admin/users", headers=h, json={**base, "login_name": "mama_two", "role": "parent"})
    assert r.status_code == 200 and r.json()["role"] == "parent"


def test_search_users(setup_db, client, db):
    admin = _admin(db)
    h = auth_headers(admin)
    p = make_account(db, "mama_one", "parent")
    p.phone = "13800001111"
    p.display_name = "金妈妈"
    make_account(db, "kid_one", "child", parent=p)
    db.commit()
    names = lambda r: sorted(u["login_name"] for u in r.json())
    assert names(client.get("/api/admin/users?role=child", headers=h)) == ["kid_one"]
    assert names(client.get("/api/admin/users?q=mama", headers=h)) == ["mama_one"]
    assert names(client.get("/api/admin/users?q=金", headers=h)) == ["mama_one"]
    assert names(client.get("/api/admin/users?q=1380000", headers=h)) == ["mama_one"]
    assert names(client.get("/api/admin/users?role=child&q=mama", headers=h)) == []


def test_patch_user_and_parent(setup_db, client, db):
    admin = _admin(db)
    h = auth_headers(admin)
    p1 = make_account(db, "mama_one", "parent")
    p2 = make_account(db, "mama_two", "parent")
    kid = make_account(db, "kid_one", "child", parent=p1)
    r = client.patch(f"/api/admin/users/{kid.id}", headers=h,
                     json={"display_name": "晨晨", "grade": 4, "parent_id": p2.id})
    assert r.status_code == 200, r.text
    assert r.json()["parent_id"] == p2.id and r.json()["display_name"] == "晨晨"
    assert client.patch(f"/api/admin/users/{kid.id}", headers=h,
                        json={"parent_id": kid.id}).status_code == 400
    r = client.patch(f"/api/admin/users/{kid.id}", headers=h, json={"parent_id": None})
    assert r.json()["parent_id"] is None
    assert client.patch("/api/admin/users/9999", headers=h, json={}).status_code == 404


def test_reset_password(setup_db, client, db):
    admin = _admin(db)
    h = auth_headers(admin)
    kid = make_account(db, "kid_one", "child")
    db.add(RefreshToken(user_id=kid.id, token_hash="x", expires_at=__import__("datetime").datetime(2999, 1, 1)))
    db.commit()
    assert client.post(f"/api/admin/users/{kid.id}/reset-password", headers=h,
                       json={"password": "short"}).status_code == 400
    r = client.post(f"/api/admin/users/{kid.id}/reset-password", headers=h,
                    json={"password": "newpass123"})
    assert r.status_code == 200
    db.expire_all()
    assert db.query(RefreshToken).filter_by(user_id=kid.id).first().revoked is True
    r = client.post("/api/auth/login", json={"login_name": "kid_one", "password": "newpass123"})
    assert r.status_code == 200


def test_archive_unarchive(setup_db, client, db):
    admin = _admin(db)
    h = auth_headers(admin)
    kid = make_account(db, "kid_one", "child")
    assert client.post(f"/api/admin/users/{kid.id}/archive", headers=h).json() == {"ok": True}
    db.expire_all()
    assert db.get(User, kid.id).status == "archived"
    assert client.post(f"/api/admin/users/{kid.id}/unarchive", headers=h).json() == {"ok": True}
    db.expire_all()
    assert db.get(User, kid.id).status == "active"
    assert client.post("/api/admin/users/9999/archive", headers=h).status_code == 404
