from datetime import datetime

from app import models  # noqa: F401  确保表已注册


def test_brain_game_result_persists(db):
    from app.models import BrainGameResult, SchoolYearBucket, User

    u = User(name="游戏孩子", role="child")
    db.add(u)
    db.flush()
    bucket = SchoolYearBucket(user_id=u.id, grade=3, school_year="2026-2027", status="active")
    db.add(bucket)
    db.flush()

    db.add(BrainGameResult(
        user_id=u.id, bucket_id=bucket.id, game="sudoku", difficulty="easy",
        duration_ms=82000, moves=30, solved=True,
    ))
    db.commit()

    row = db.query(BrainGameResult).one()
    assert row.game == "sudoku"
    assert row.difficulty == "easy"
    assert row.duration_ms == 82000
    assert row.solved is True
    assert isinstance(row.created_at, datetime)


def _client_with_router():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.brain_games import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _bound_child():
    """建一个已绑定家长的孩子，返回 (child, child_headers)。"""
    from app.database import SessionLocal
    from conftest import parent_child

    s = SessionLocal()
    parent, child, parent_h, child_h = parent_child(s, "bg")
    s.close()
    return child, child_h


def test_post_result_first_solve_is_best():
    child, h = _bound_child()
    client = _client_with_router()
    r = client.post("/api/brain-games/result", headers=h, json={
        "user_id": child.id, "game": "sudoku", "difficulty": "easy",
        "duration_ms": 82000, "moves": 30, "solved": True,
    })
    assert r.status_code == 200
    assert r.json() == {"ok": True, "is_best": True}


def test_post_result_slower_is_not_best():
    child, h = _bound_child()
    client = _client_with_router()
    base = {"user_id": child.id, "game": "schulte", "difficulty": "easy",
            "duration_ms": 50000, "moves": 9, "solved": True}
    client.post("/api/brain-games/result", headers=h, json=base)
    r = client.post("/api/brain-games/result", headers=h,
                    json={**base, "duration_ms": 60000})
    assert r.json()["is_best"] is False


def test_post_result_faster_is_best():
    child, h = _bound_child()
    client = _client_with_router()
    base = {"user_id": child.id, "game": "schulte", "difficulty": "medium",
            "duration_ms": 60000, "moves": 16, "solved": True}
    client.post("/api/brain-games/result", headers=h, json=base)
    r = client.post("/api/brain-games/result", headers=h,
                    json={**base, "duration_ms": 45000})
    assert r.json()["is_best"] is True


def test_post_result_tie_is_not_best():
    child, h = _bound_child()
    client = _client_with_router()
    base = {"user_id": child.id, "game": "schulte", "difficulty": "hard",
            "duration_ms": 30000, "moves": 25, "solved": True}
    client.post("/api/brain-games/result", headers=h, json=base)
    r = client.post("/api/brain-games/result", headers=h, json=base)
    assert r.json()["is_best"] is False


def test_post_result_failed_game_is_never_best():
    child, h = _bound_child()
    client = _client_with_router()
    r = client.post("/api/brain-games/result", headers=h, json={
        "user_id": child.id, "game": "minesweeper", "difficulty": "easy",
        "duration_ms": 5000, "moves": 3, "solved": False,
    })
    assert r.status_code == 200
    assert r.json()["is_best"] is False


def test_post_result_rejects_invalid_game():
    child, h = _bound_child()
    client = _client_with_router()
    r = client.post("/api/brain-games/result", headers=h, json={
        "user_id": child.id, "game": "tetris", "difficulty": "easy",
        "duration_ms": 1000, "moves": 1, "solved": True,
    })
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_game"


def test_post_result_rejects_invalid_difficulty():
    child, h = _bound_child()
    client = _client_with_router()
    r = client.post("/api/brain-games/result", headers=h, json={
        "user_id": child.id, "game": "sudoku", "difficulty": "insane",
        "duration_ms": 1000, "moves": 1, "solved": True,
    })
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_difficulty"


def test_post_result_forbidden_for_other_family():
    child, _ = _bound_child()
    from app.database import SessionLocal
    from conftest import parent_child

    s = SessionLocal()
    _p, _c, other_parent_h, _other_child_h = parent_child(s, "bg2")
    s.close()

    client = _client_with_router()
    r = client.post("/api/brain-games/result", headers=other_parent_h, json={
        "user_id": child.id, "game": "sudoku", "difficulty": "easy",
        "duration_ms": 1000, "moves": 1, "solved": True,
    })
    assert r.status_code == 403


def _post(client, h, child_id, **kw):
    body = {"user_id": child_id, "game": "sudoku", "difficulty": "easy",
            "duration_ms": 1000, "moves": 1, "solved": True}
    body.update(kw)
    return client.post("/api/brain-games/result", headers=h, json=body)


def test_stats_aggregates_played_solved_best():
    child, h = _bound_child()
    client = _client_with_router()
    _post(client, h, child.id, duration_ms=90000)
    _post(client, h, child.id, duration_ms=70000)
    _post(client, h, child.id, duration_ms=5000, solved=False, moves=2)

    r = client.get(f"/api/brain-games/stats?user_id={child.id}", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["sudoku"]["easy"] == {"best_ms": 70000, "played": 3, "solved": 2}
    # 结构固定包含三个游戏 key
    assert set(body) == {"sudoku", "schulte", "minesweeper"}
    assert body["schulte"] == {}


def test_stats_best_is_null_when_never_solved():
    child, h = _bound_child()
    client = _client_with_router()
    _post(client, h, child.id, game="minesweeper", duration_ms=3000, solved=False, moves=2)

    r = client.get(f"/api/brain-games/stats?user_id={child.id}", headers=h)
    body = r.json()
    assert body["minesweeper"]["easy"] == {"best_ms": None, "played": 1, "solved": 0}


def test_stats_isolated_per_difficulty():
    child, h = _bound_child()
    client = _client_with_router()
    _post(client, h, child.id, difficulty="easy", duration_ms=20000)
    _post(client, h, child.id, difficulty="hard", duration_ms=120000)

    r = client.get(f"/api/brain-games/stats?user_id={child.id}", headers=h)
    body = r.json()["sudoku"]
    assert body["easy"]["best_ms"] == 20000
    assert body["hard"]["best_ms"] == 120000


def test_stats_forbidden_for_other_family():
    child, _ = _bound_child()
    from app.database import SessionLocal
    from conftest import parent_child

    s = SessionLocal()
    _p, _c, other_parent_h, _och = parent_child(s, "bg3")
    s.close()

    client = _client_with_router()
    r = client.get(f"/api/brain-games/stats?user_id={child.id}", headers=other_parent_h)
    assert r.status_code == 403


def test_stats_requires_auth():
    child, _ = _bound_child()
    client = _client_with_router()
    r = client.get(f"/api/brain-games/stats?user_id={child.id}")
    assert r.status_code == 401
