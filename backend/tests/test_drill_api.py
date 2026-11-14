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


def test_drill_step_and_complete(client, db):
    parent, child, parent_h, child_h = parent_child(db)
    tid = _approved_task(client, db, parent_h, child)
    from app.models import Task
    t = db.get(Task, tid)
    import json as _json
    snap = _json.loads(t.content)["items_snapshot"]
    primary = snap[0]["primary"]
    r = client.post(f"/api/tasks/{tid}/drill-step",
                    json={"step": "recall", "item_id": snap[0]["id"], "answer": primary, "request_hint": False},
                    headers=child_h)
    assert r.json().get("correct") is True
    r2 = client.post(f"/api/tasks/{tid}/drill-complete", json={"results": {str(snap[0]["id"]): True}}, headers=child_h)
    assert "stars" in r2.json()


def test_drill_apply_llm_fallback(client, db):
    parent, child, parent_h, child_h = parent_child(db)
    tid = _approved_task(client, db, parent_h, child)
    r = client.post(f"/api/tasks/{tid}/drill-apply", json={"item_id": 1, "sentence": "这句对吗"}, headers=child_h)
    assert r.status_code == 200 and "pass" in r.json()


def test_drill_complete_hint_blocks_interval_upgrade(client, db):
    """本次用了提示（drill-step 答错触发 hint）→ interval 不升级、last_hinted=True。"""
    parent, child, parent_h, child_h = parent_child(db)
    tid = _approved_task(client, db, parent_h, child)
    from app.models import Task, TrainingItemMastery
    import json as _json
    t = db.get(Task, tid)
    item_id = _json.loads(t.content)["items_snapshot"][0]["id"]
    # 答错 → 触发提示，hints_used[item] = 1
    client.post(f"/api/tasks/{tid}/drill-step",
                json={"step": "recall", "item_id": item_id, "answer": "错误答案", "request_hint": True},
                headers=child_h)
    # 完成时正确（但本次用过提示）→ interval 应保持 1，不翻倍
    client.post(f"/api/tasks/{tid}/drill-complete", json={"results": {str(item_id): True}}, headers=child_h)
    m = db.query(TrainingItemMastery).filter_by(user_id=child.id, item_id=item_id).first()
    assert m is not None
    assert m.interval == 1
    assert m.last_hinted is True


def test_list_groups(client, db):
    parent, child, parent_h, _ = parent_child(db)
    _make_group(client, parent_h)
    r = client.get("/api/drill/groups", headers=parent_h)
    assert r.status_code == 200
    groups = r.json()
    assert isinstance(groups, list)
    assert len(groups) >= 1
    assert "item_count" in groups[0]
    assert "audit_status" in groups[0]
