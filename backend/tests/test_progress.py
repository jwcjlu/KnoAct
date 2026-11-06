from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.progress import router as progress_router
from conftest import auth_headers, make_account, make_lesson, bound_child_headers


def _client():
    app = FastAPI()
    app.include_router(progress_router)
    return TestClient(app)


def test_advance_requires_60_percent(setup_db):
    from app.database import SessionLocal
    s = SessionLocal()
    p = make_account(s, "p_pr1", "parent")
    uid = make_account(s, "晨晨", "child", parent=p).id
    make_lesson(s, audit_status="approved")
    s.commit(); s.close()
    h = bound_child_headers(uid)
    # 正确率 33% → 不推进
    resp = _client().post("/api/progress/advance", json={"user_id": uid, "correct": 1, "total": 3},
                          headers=h)
    assert resp.json()["passed"] is False
    # 正确率 100% → 推进
    resp = _client().post("/api/progress/advance", json={"user_id": uid, "correct": 3, "total": 3},
                          headers=h)
    assert resp.json()["passed"] is True


def test_parent_adjust_progress(setup_db):
    from app.database import SessionLocal
    from app.models import User
    s = SessionLocal()
    parent = make_account(s, "p_adj", "parent")
    uid = make_account(s, "k_adj", "child", parent=parent).id
    target = make_lesson(s).id
    pid = parent.id
    s.commit(); s.close()
    s = SessionLocal()
    hp = auth_headers(s.get(User, pid))
    s.close()
    resp = _client().post("/api/progress/adjust", json={"user_id": uid, "lesson_id": target},
                          headers=hp)
    assert resp.status_code == 200
    assert resp.json()["current_lesson_id"] == target
