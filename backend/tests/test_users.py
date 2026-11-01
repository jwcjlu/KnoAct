from fastapi.testclient import TestClient


def _client():
    from app.main import app
    return TestClient(app)


def _add_users(*users):
    from app.models import User
    from app.database import SessionLocal
    s = SessionLocal()
    for name, role in users:
        s.add(User(name=name, role=role))
    s.commit()
    s.close()


def test_list_children_filters_by_role_and_sorts_by_id(setup_db):
    _add_users(("金同学", "child"), ("金爸爸", "parent"), ("林晨", "child"))
    resp = _client().get("/api/users?role=child")
    assert resp.status_code == 200
    data = resp.json()
    assert [u["name"] for u in data] == ["金同学", "林晨"]
    assert all(set(u) == {"id", "name", "role"} for u in data)
    assert data[0]["id"] < data[1]["id"]


def test_list_users_without_role_returns_all(setup_db):
    _add_users(("金同学", "child"), ("金爸爸", "parent"))
    data = _client().get("/api/users").json()
    assert [u["role"] for u in data] == ["child", "parent"]


def test_list_users_empty(setup_db):
    assert _client().get("/api/users?role=child").json() == []
