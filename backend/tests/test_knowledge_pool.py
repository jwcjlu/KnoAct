import json
from conftest import parent_child


def _mk_point(db, owner, subject="英语", content="look after", extra=None):
    from app.models import KnowledgePointPool
    p = KnowledgePointPool(owner_id=owner.id, subject=subject, content=content,
                           category="短语", source="manual",
                           extra=json.dumps(extra or {"释义": "照顾"}, ensure_ascii=False))
    db.add(p); db.commit()
    return p


def test_publish_creates_group_and_items(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p1 = _mk_point(db, parent, content="look after")
    p2 = _mk_point(db, parent, content="look for")
    r = client.post("/api/plans", json={"subject": "英语", "title": "look 短语",
                                        "point_ids": [p1.id, p2.id]}, headers=parent_h)
    plan_id = r.json()["id"]
    r2 = client.post(f"/api/plans/{plan_id}/publish", headers=parent_h)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["group_id"] and body["item_count"] == 2
    from app.models import TrainingItem
    items = db.query(TrainingItem).filter_by(group_id=body["group_id"]).order_by(TrainingItem.id).all()
    assert {it.primary for it in items} == {"look after", "look for"}
    assert all(it.point_pool_id in (p1.id, p2.id) for it in items)


def test_publish_idempotent_same_group(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p = _mk_point(db, parent)
    plan_id = client.post("/api/plans", json={"subject": "英语", "title": "t",
                                              "point_ids": [p.id]}, headers=parent_h).json()["id"]
    g1 = client.post(f"/api/plans/{plan_id}/publish", headers=parent_h).json()["group_id"]
    g2 = client.post(f"/api/plans/{plan_id}/publish", headers=parent_h).json()["group_id"]
    assert g1 == g2


def test_pool_isolated_by_parent(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p2, _, p2_h, _ = parent_child(db, prefix="other")
    _mk_point(db, parent, content="look after")
    r = client.get("/api/knowledge-pool", headers=p2_h)
    assert r.json() == []


def test_crud_and_edit(client, db):
    parent, child, parent_h, _ = parent_child(db)
    r = client.post("/api/knowledge-pool", json={"subject": "英语", "category": "短语",
                                                 "content": "give up", "extra": '{"释义":"放弃"}'},
                    headers=parent_h)
    pid = r.json()["id"]
    r2 = client.put(f"/api/knowledge-pool/{pid}", json={"content": "give in",
                                                        "extra": '{"释义":"让步"}'}, headers=parent_h)
    assert r2.json()["content"] == "give in"
    r3 = client.delete(f"/api/knowledge-pool/{pid}", headers=parent_h)
    assert r3.json()["ok"] is True


def test_delete_published_point_refused(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p = _mk_point(db, parent)
    plan_id = client.post("/api/plans", json={"subject": "英语", "title": "t",
                                              "point_ids": [p.id]}, headers=parent_h).json()["id"]
    client.post(f"/api/plans/{plan_id}/publish", headers=parent_h)
    r = client.delete(f"/api/knowledge-pool/{p.id}", headers=parent_h)
    assert r.json().get("error")


def test_delete_plan_cascades_group(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p = _mk_point(db, parent)
    plan_id = client.post("/api/plans", json={"subject": "英语", "title": "t",
                                              "point_ids": [p.id]}, headers=parent_h).json()["id"]
    gid = client.post(f"/api/plans/{plan_id}/publish", headers=parent_h).json()["group_id"]
    from app.models import TrainingGroup, TrainingItem
    client.delete(f"/api/plans/{plan_id}", headers=parent_h)
    assert db.get(TrainingGroup, gid) is None
    assert db.query(TrainingItem).filter_by(group_id=gid).count() == 0


def test_folder_tree_and_move(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p = _mk_point(db, parent, content="look after")
    r = client.post("/api/knowledge-folders", json={"name": "look 短语", "subject": "英语", "parent_id": None}, headers=parent_h)
    fid = r.json()["id"]
    r2 = client.put(f"/api/knowledge-pool/{p.id}/move", json={"folder_id": fid}, headers=parent_h)
    assert r2.json()["folder_id"] == fid
    tree = client.get("/api/knowledge-folders", headers=parent_h).json()
    root = [f for f in tree if f["id"] == fid][0]
    assert root["point_count"] == 1


def test_point_tags(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p = _mk_point(db, parent, content="give up")
    r = client.put(f"/api/knowledge-pool/{p.id}/tags", json={"tags": ["易错", "重点"]}, headers=parent_h)
    import json as _json
    assert _json.loads(r.json()["tags"]) == ["易错", "重点"]


def test_delete_folder_nonempty_refused(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p = _mk_point(db, parent, content="look after")
    fid = client.post("/api/knowledge-folders", json={"name": "f", "subject": "英语", "parent_id": None}, headers=parent_h).json()["id"]
    client.put(f"/api/knowledge-pool/{p.id}/move", json={"folder_id": fid}, headers=parent_h)
    r = client.delete(f"/api/knowledge-folders/{fid}", headers=parent_h)
    assert r.json().get("error")


def test_move_point_cross_owner_refused(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p2, _, p2_h, _ = parent_child(db, prefix="other")
    p = _mk_point(db, parent, content="look after")
    # 另一个家长建的目录
    other_fid = client.post("/api/knowledge-folders", json={"name": "other", "subject": "英语", "parent_id": None}, headers=p2_h).json()["id"]
    r = client.put(f"/api/knowledge-pool/{p.id}/move", json={"folder_id": other_fid}, headers=parent_h)
    assert r.json().get("error")
