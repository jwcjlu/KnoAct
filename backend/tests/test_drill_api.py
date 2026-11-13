from conftest import parent_child


def _make_group(client, parent_h, **kw):
    body = {"source": "custom", "subject": "语文", "title": "必背古诗 20 首", "kind": "outline",
            "mastery_interval_days": 15, "interval_max_days": 60,
            "items": [{"kind": "drill_item", "primary": "床前明月光", "secondary": "李白《静夜思》",
                       "keywords": ["李白", "明月"]}]}
    body.update(kw)
    r = client.post("/api/drill/groups", json=body, headers=parent_h)
    assert r.status_code == 200, r.text
    return r.json()


def test_create_custom_group(client, db):
    parent, child, parent_h, _ = parent_child(db)
    data = _make_group(client, parent_h)
    assert "group_id" in data


def test_audit_group(client, db):
    parent, child, parent_h, _ = parent_child(db)
    gid = _make_group(client, parent_h)["group_id"]
    r = client.post(f"/api/drill/groups/{gid}/audit", data={"action": "通过"}, headers=parent_h)
    assert r.status_code == 200


def test_reactivate_group(client, db):
    parent, child, parent_h, _ = parent_child(db)
    gid = _make_group(client, parent_h)["group_id"]
    r = client.post(f"/api/drill/groups/{gid}/reactivate", headers=parent_h)
    assert r.status_code == 200


def _approved_task(client, db, parent_h, child, date="2026-11-13"):
    data = _make_group(client, parent_h)
    gid = data["group_id"]
    client.post(f"/api/drill/groups/{gid}/audit", data={"action": "通过"}, headers=parent_h)
    r = client.post("/api/drill/tasks", json={"group_id": gid, "user_id": child.id, "date": date}, headers=parent_h)
    assert r.status_code == 200, r.text
    return r.json()["task_id"]


def test_task_requires_approved(client, db):
    parent, child, parent_h, _ = parent_child(db)
    gid = _make_group(client, parent_h)["group_id"]
    r = client.post("/api/drill/tasks", json={"group_id": gid, "user_id": child.id, "date": "2026-11-13"}, headers=parent_h)
    assert r.json().get("task_id") is None


def test_task_create_and_idempotent(client, db):
    parent, child, parent_h, _ = parent_child(db)
    gid = _make_group(client, parent_h)["group_id"]
    client.post(f"/api/drill/groups/{gid}/audit", data={"action": "通过"}, headers=parent_h)
    r1 = client.post("/api/drill/tasks", json={"group_id": gid, "user_id": child.id, "date": "2026-11-13"}, headers=parent_h)
    r2 = client.post("/api/drill/tasks", json={"group_id": gid, "user_id": child.id, "date": "2026-11-13"}, headers=parent_h)
    assert r1.json()["task_id"] == r2.json()["task_id"]


def test_task_no_items_400(client, db):
    parent, child, parent_h, _ = parent_child(db)
    gid = _make_group(client, parent_h, items=[])["group_id"]
    client.post(f"/api/drill/groups/{gid}/audit", data={"action": "通过"}, headers=parent_h)
    r = client.post("/api/drill/tasks", json={"group_id": gid, "user_id": child.id, "date": "2026-11-13"}, headers=parent_h)
    assert r.status_code == 400
