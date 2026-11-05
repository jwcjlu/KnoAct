from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models import User
from app.routers.auth import router as auth_router
from app.services.security import hash_password


def _make_client(db):
    app = FastAPI()
    app.include_router(auth_router)

    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _register(c, login_name="chenchen", password="abc12345", role="child"):
    return c.post("/api/auth/register", json={
        "login_name": login_name, "password": password, "role": role,
    })


def test_register_returns_tokens(setup_db, db):
    c = _make_client(db)
    r = _register(c)
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["role"] == "child"
    assert body["user"]["login_name"] == "chenchen"


def test_register_unique_409(setup_db, db):
    c = _make_client(db)
    assert _register(c).status_code == 200
    assert _register(c).status_code == 409


def test_register_rejects_admin_and_weak(setup_db, db):
    c = _make_client(db)
    assert _register(c, role="admin").status_code == 422
    assert _register(c, login_name="ok_name", password="short1").status_code == 400
    assert _register(c, login_name="a!", password="abc12345").status_code == 400


def test_login_password(setup_db, db):
    c = _make_client(db)
    _register(c, role="parent")
    r = c.post("/api/auth/login", json={"login_name": "chenchen", "password": "abc12345"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "parent"
    bad = c.post("/api/auth/login", json={"login_name": "chenchen", "password": "wrong123"})
    assert bad.status_code == 401


def test_login_does_not_autocreate(setup_db, db):
    c = _make_client(db)
    r = c.post("/api/auth/login", json={"login_name": "ghost_user", "password": "abc12345"})
    assert r.status_code == 401
    assert db.query(User).count() == 0


def test_login_archived_403(setup_db, db):
    c = _make_client(db)
    db.add(User(name="old", login_name="old_user", password_hash=hash_password("abc12345"),
                role="child", status="archived"))
    db.commit()
    r = c.post("/api/auth/login", json={"login_name": "old_user", "password": "abc12345"})
    assert r.status_code == 403


def test_otp_login_with_verified_phone(setup_db, db):
    c = _make_client(db)
    db.add(User(name="p", login_name="phone_user", password_hash=hash_password("abc12345"),
                role="parent", phone="13800000000", phone_verified=True))
    db.commit()
    assert c.post("/api/auth/otp/send", json={"login_name": "phone_user", "purpose": "login"}).status_code == 200
    r = c.post("/api/auth/otp/login", json={"login_name": "phone_user", "code": "123456"})
    assert r.status_code == 200
    assert r.json()["access_token"]
    # 验证码使用后失效
    again = c.post("/api/auth/otp/login", json={"login_name": "phone_user", "code": "123456"})
    assert again.status_code == 401


def test_otp_send_requires_verified_phone(setup_db, db):
    c = _make_client(db)
    _register(c)
    r = c.post("/api/auth/otp/send", json={"login_name": "chenchen", "purpose": "login"})
    assert r.status_code == 400


def test_password_reset_via_otp(setup_db, db):
    c = _make_client(db)
    db.add(User(name="p", login_name="phone_user", password_hash=hash_password("abc12345"),
                role="parent", phone="13800000000", phone_verified=True))
    db.commit()
    c.post("/api/auth/otp/send", json={"login_name": "phone_user", "purpose": "reset_password"})
    r = c.post("/api/auth/password/reset", json={
        "login_name": "phone_user", "code": "123456", "new_password": "newpass99"})
    assert r.status_code == 200
    ok = c.post("/api/auth/login", json={"login_name": "phone_user", "password": "newpass99"})
    assert ok.status_code == 200


def test_me_with_bearer(setup_db, db):
    c = _make_client(db)
    token = _register(c).json()["access_token"]
    r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["login_name"] == "chenchen"
    assert data["role"] == "child"
    assert data["parent_bound"] is False
    assert "display_name" in data


def test_me_requires_bearer(setup_db, db):
    c = _make_client(db)
    assert c.get("/api/auth/me").status_code == 401
    assert c.get("/api/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_me_parent_bound(setup_db, db):
    c = _make_client(db)
    parent_id = _register(c, "dad_user", role="parent").json()["user"]["id"]
    child = c.post("/api/auth/register", json={"login_name": "kid_user", "password": "abc12345"}).json()
    u = db.get(User, child["user"]["id"])
    u.parent_id = parent_id
    db.commit()
    r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {child['access_token']}"})
    assert r.json()["parent_bound"] is True


def test_patch_profile_and_credentials(setup_db, db):
    c = _make_client(db)
    token = _register(c).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    r = c.patch("/api/auth/me/profile", headers=h, json={
        "display_name": "晨晨", "birth_month": "2016-05", "gender": "male",
        "interests": ["画画", "恐龙"], "grade": 3, "edition": "人教版"})
    assert r.status_code == 200
    d = r.json()
    assert d["display_name"] == "晨晨" and d["grade"] == 3 and d["interests"] == "画画,恐龙"
    assert c.patch("/api/auth/me/profile", headers=h, json={"birth_month": "bad"}).status_code == 400

    bad = c.patch("/api/auth/me/credentials", headers=h, json={
        "old_password": "nope1234", "new_password": "newpass99"})
    assert bad.status_code == 403
    ok = c.patch("/api/auth/me/credentials", headers=h, json={
        "old_password": "abc12345", "new_password": "newpass99"})
    assert ok.status_code == 200
    assert c.post("/api/auth/login", json={"login_name": "chenchen", "password": "newpass99"}).status_code == 200


def test_bind_phone(setup_db, db):
    c = _make_client(db)
    token = _register(c).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert c.post("/api/auth/me/phone/send", headers=h, json={"phone": "13900000000"}).status_code == 200
    r = c.patch("/api/auth/me/credentials", headers=h, json={"phone": "13900000000", "code": "123456"})
    assert r.status_code == 200
    assert r.json()["phone_verified"] is True


def test_refresh_rotates(setup_db, db):
    c = _make_client(db)
    rt = _register(c).json()["refresh_token"]
    r = c.post("/api/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 200 and r.json()["access_token"]
    assert c.post("/api/auth/refresh", json={"refresh_token": rt}).status_code == 401


def test_legacy_name_login_default_off(setup_db, db, monkeypatch):
    c = _make_client(db)
    monkeypatch.delenv("KNOACT_LEGACY_NAME_LOGIN", raising=False)
    assert c.post("/api/auth/login", json={"name": "晨晨"}).status_code == 401
    monkeypatch.setenv("KNOACT_LEGACY_NAME_LOGIN", "1")
    r = c.post("/api/auth/login", json={"name": "晨晨"})
    assert r.status_code == 200 and r.json()["role"] == "child"
