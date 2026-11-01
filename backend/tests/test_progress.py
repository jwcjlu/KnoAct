from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.progress import router as progress_router
from conftest import make_user, make_lesson


def _client():
    app = FastAPI()
    app.include_router(progress_router)
    return TestClient(app)


def test_advance_requires_60_percent(setup_db):
    from app.models import User, Lesson
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(User(name="晨晨", role="child")); s.commit()
    uid = s.query(User).filter_by(name="晨晨").first().id
    make_lesson(s, audit_status="approved")
    s.commit(); s.close()
    # 正确率 33% → 不推进
    resp = _client().post("/api/progress/advance", json={"user_id": uid, "correct": 1, "total": 3})
    assert resp.json()["passed"] is False
    # 正确率 100% → 推进
    resp = _client().post("/api/progress/advance", json={"user_id": uid, "correct": 3, "total": 3})
    assert resp.json()["passed"] is True


def test_parent_adjust_progress(setup_db):
    from app.database import SessionLocal
    s = SessionLocal()
    uid = make_user(s).id
    target = make_lesson(s).id
    s.commit(); s.close()
    resp = _client().post("/api/progress/adjust", json={"user_id": uid, "lesson_id": target})
    assert resp.status_code == 200
    assert resp.json()["current_lesson_id"] == target
