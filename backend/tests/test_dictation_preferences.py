from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from datetime import date

from app.models import Task
from conftest import auth_headers, make_account, parent_child

client = TestClient(app)


def test_preferences_get_default(setup_db):
    session = SessionLocal()
    _, child, _, child_h = parent_child(session, "pref")
    session.close()
    r = client.get(f"/api/learning/preferences?user_id={child.id}", headers=child_h)
    assert r.status_code == 200
    assert r.json()["dictation_input_mode"] == "paper_photo"


def test_preferences_put_dictation_counts_child_scoped(setup_db):
    session = SessionLocal()
    parent, child, parent_h, child_h = parent_child(session, "dcnt")
    child_id = child.id
    from app.models import User
    other = User(name="other_child", role="child", parent_id=parent.id)
    session.add(other); session.commit()
    other_id = other.id
    session.close()

    r = client.put("/api/learning/preferences",
                   json={"user_id": child_id,
                         "task_dictation_count_语文": 12,
                         "task_dictation_due_cap": 0.6,
                         "task_dictation_new_floor": 0.2},
                   headers=parent_h)
    assert r.status_code == 200

    g = client.get(f"/api/learning/preferences?user_id={child_id}", headers=child_h)
    assert g.json()["task_dictation_count_语文"] == 12
    assert g.json()["task_dictation_due_cap"] == 0.6
    assert g.json()["task_dictation_new_floor"] == 0.2

    from app.services.child_config import get_child_config_int, get_child_config_float
    s = SessionLocal()
    assert get_child_config_int(s, other_id, "task_dictation_count_语文", 7) == 7
    s.close()


def test_preferences_put_rejects_invalid_count(setup_db):
    session = SessionLocal()
    _, child, parent_h, _ = parent_child(session, "badcnt")
    child_id = child.id
    session.close()
    r = client.put("/api/learning/preferences",
                   json={"user_id": child_id, "task_dictation_count_语文": 0},
                   headers=parent_h)
    assert r.status_code == 400


def test_preferences_get_returns_defaults_for_unconfigured_child(setup_db):
    session = SessionLocal()
    _, child, _, child_h = parent_child(session, "ddef")
    session.close()
    r = client.get(f"/api/learning/preferences?user_id={child.id}", headers=child_h)
    body = r.json()
    assert body["dictation_input_mode"] == "paper_photo"
    assert body["task_dictation_due_cap"] == 0.5
    assert body["task_dictation_new_floor"] == 0.3


def test_preferences_put_parent_only(setup_db):
    session = SessionLocal()
    _, child, parent_h, child_h = parent_child(session, "put")
    session.close()
    r = client.put(
        "/api/learning/preferences",
        json={"user_id": child.id, "dictation_input_mode": "on_screen"},
        headers=parent_h,
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    r2 = client.get(f"/api/learning/preferences?user_id={child.id}", headers=child_h)
    assert r2.json()["dictation_input_mode"] == "on_screen"


def test_preferences_put_invalid_mode(setup_db):
    session = SessionLocal()
    _, child, parent_h, _ = parent_child(session, "bad")
    session.close()
    r = client.put(
        "/api/learning/preferences",
        json={"user_id": child.id, "dictation_input_mode": "bogus"},
        headers=parent_h,
    )
    assert r.status_code == 400


def test_preferences_put_rejected_for_child(setup_db):
    session = SessionLocal()
    _, child, _, child_h = parent_child(session, "childput")
    session.close()
    r = client.put(
        "/api/learning/preferences",
        json={"user_id": child.id, "dictation_input_mode": "on_screen"},
        headers=child_h,
    )
    assert r.status_code == 403


def test_admin_dictation_checkins(setup_db):
    session = SessionLocal()
    admin = make_account(session, "adm_chk", "admin")
    _, child, _, _ = parent_child(session, "chk")
    session.add(Task(
        user_id=child.id,
        date=date.today(),
        subject="语文",
        task_type="dictation",
        title="桂花雨 生词听写",
        submit_status="submitted",
        photo_path="uploads/task_photos/task_1.png",
        content_status="published",
    ))
    session.commit()
    admin_h = auth_headers(admin)
    session.close()
    r = client.get("/api/admin/dictation-checkins", headers=admin_h)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "桂花雨 生词听写"


def test_admin_dictation_checkins_forbidden_for_parent(setup_db):
    session = SessionLocal()
    _, child, parent_h, _ = parent_child(session, "nop")
    session.close()
    r = client.get("/api/admin/dictation-checkins", headers=parent_h)
    assert r.status_code == 403
