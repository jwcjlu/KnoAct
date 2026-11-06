from fastapi.testclient import TestClient
from app.database import SessionLocal
from conftest import auth_headers, make_account


def _client():
    from app.main import app
    return TestClient(app)


def test_list_children_filters_by_role_and_sorts_by_id(setup_db):
    s = SessionLocal()
    pa = make_account(s, "p_ul", "parent")
    make_account(s, "金同学", "child", parent=pa)
    make_account(s, "林晨", "child", parent=pa)
    s.commit()
    hp = auth_headers(pa)
    s.close()
    resp = _client().get("/api/users?role=child", headers=hp)
    assert resp.status_code == 200
    data = resp.json()
    assert [u["name"] for u in data] == ["金同学", "林晨"]
    assert all(set(u) == {"id", "name", "role", "grade", "edition", "status"} for u in data)
    assert data[0]["id"] < data[1]["id"]


def test_list_users_without_role_returns_all(setup_db):
    s = SessionLocal()
    pa = make_account(s, "p_u2", "parent")
    make_account(s, "金同学", "child", parent=pa)
    s.commit()
    hp = auth_headers(pa)
    s.close()
    data = _client().get("/api/users", headers=hp).json()
    # 无 role 时家长默认只看名下孩子
    assert len(data) == 1
    assert data[0]["name"] == "金同学"


def test_list_users_empty(setup_db):
    s = SessionLocal()
    pa = make_account(s, "p_empty", "parent")
    s.commit()
    hp = auth_headers(pa)
    s.close()
    assert _client().get("/api/users?role=child", headers=hp).json() == []
