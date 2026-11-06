"""P0 SEC-01：跨用户越权矩阵（按 router 逐步补齐）。"""
from conftest import auth_headers, bound_pair, make_account


def test_points_balance_anonymous_401(setup_db, client):
    assert client.get("/api/points/balance?user_id=1").status_code == 401


def test_child_cannot_read_other_balance(setup_db, client, db):
    _, a, b, _, ha, _ = bound_pair(db, "pts")
    r = client.get(f"/api/points/balance?user_id={b.id}", headers=ha)
    assert r.status_code == 403
    assert r.json()["detail"] == {"error": "forbidden"}


def test_parent_can_read_own_child_balance(setup_db, client, db):
    _, a, _, hp, _, _ = bound_pair(db, "pts2")
    r = client.get(f"/api/points/balance?user_id={a.id}", headers=hp)
    assert r.status_code == 200
    assert "balance" in r.json()


def test_parent_cannot_read_unrelated_child_balance(setup_db, client, db):
    p1 = make_account(db, "p_own", "parent")
    p2 = make_account(db, "p_other", "parent")
    mine = make_account(db, "kid_mine", "child", parent=p1)
    theirs = make_account(db, "kid_other", "child", parent=p2)
    r = client.get(f"/api/points/balance?user_id={theirs.id}", headers=auth_headers(p1))
    assert r.status_code == 403
    assert r.json()["detail"] == {"error": "forbidden"}
