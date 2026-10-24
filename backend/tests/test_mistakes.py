from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.mistakes import router as mistakes_router


def _client():
    app = FastAPI()
    app.include_router(mistakes_router)
    return TestClient(app)


def _seed_mistake():
    from app.models import Mistake
    from app.database import SessionLocal
    s = SessionLocal()
    m = Mistake(user_id=1, source_type="dictation", question="听写：徘徊", your_answer="排回", correct_answer="徘徊")
    s.add(m); s.commit()
    mid = m.id
    s.close()
    return mid


def test_list_mistakes(setup_db):
    _seed_mistake()
    resp = _client().get("/api/mistakes?user_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["correct_answer"] == "徘徊"


def test_mark_correct_removes_after_3(setup_db):
    mid = _seed_mistake()
    c = _client()
    for _ in range(2):
        r = c.post(f"/api/mistakes/{mid}/correct").json()
        assert r["removed"] is False
    r = c.post(f"/api/mistakes/{mid}/correct").json()
    assert r["removed"] is True
    # 已删除
    from app.database import SessionLocal
    from app.models import Mistake
    s = SessionLocal()
    assert s.query(Mistake).filter_by(id=mid).count() == 0
    s.close()


def test_mark_wrong_resets_streak(setup_db):
    mid = _seed_mistake()
    c = _client()
    c.post(f"/api/mistakes/{mid}/correct")
    r = c.post(f"/api/mistakes/{mid}/wrong").json()
    assert r["mistake_count"] == 2
    from app.database import SessionLocal
    from app.models import Mistake
    s = SessionLocal()
    m = s.query(Mistake).filter_by(id=mid).first()
    assert m.consecutive_correct == 0
    s.close()


def test_weakness_report(setup_db):
    _seed_mistake()
    resp = _client().get("/api/mistakes/report?user_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["rows"][0]["name"] == "听写"
