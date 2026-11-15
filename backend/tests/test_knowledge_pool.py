import json
from conftest import parent_child


def _mk_point(db, owner, subject="英语", content="look after", extra=None):
    from app.models import KnowledgePointPool
    p = KnowledgePointPool(owner_id=owner.id, subject=subject, content=content,
                           category="短语", source="manual",
                           extra=json.dumps(extra or {"释义": "照顾"}, ensure_ascii=False))
    db.add(p); db.flush()
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
