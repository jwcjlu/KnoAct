"""表达练习（孩子讲一遍）的模型层测试。

本表刻意不含 verdict / score / ai_* —— 见 spec 的「五轮失败记录」。
"""
from app.models import ExpressionNote


def _cols() -> set[str]:
    return {c.name for c in ExpressionNote.__table__.columns}


def test_expression_note_has_no_judgement_columns():
    """表里不能有判定类字段：判不出「讲得好不好」，就不给位置。"""
    cols = _cols()
    forbidden = {"verdict", "score", "passed", "grade", "ai_verdict", "ai_score"}
    assert not (cols & forbidden), f"不该有判定字段：{cols & forbidden}"
    assert not any(c.startswith("ai_") for c in cols), f"不该有 AI 字段：{cols}"


def test_expression_note_required_columns_exist():
    cols = _cols()
    for name in ("id", "user_id", "bucket_id", "knowledge_point_id", "item_id",
                 "title", "text", "created_at"):
        assert name in cols, f"缺列 {name}"


def test_expression_note_fk_ondelete_set_null():
    """知识点被删除时必须 SET NULL，否则 cleanup 删课会撞外键。"""
    for fk_col in (ExpressionNote.__table__.c.knowledge_point_id,
                   ExpressionNote.__table__.c.item_id):
        fks = list(fk_col.foreign_keys)
        assert len(fks) == 1, f"{fk_col.name} 应恰好有 1 个外键"
        assert fks[0].ondelete == "SET NULL", f"{fk_col.name} 应为 SET NULL"


from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import auth_headers, bound_child_headers, make_account


def _client():
    from app.routers.expression import router as expression_router
    app = FastAPI()
    app.include_router(expression_router)
    return TestClient(app)


def _seed_child(grade=4, prefix="expr"):
    """建家长 + 孩子，返回 (child_id, headers)。"""
    from app.database import SessionLocal
    from app.models import User
    s = SessionLocal()
    p = make_account(s, f"p_{prefix}", "parent")
    u = make_account(s, f"k_{prefix}", "child", parent=p)
    u.grade = grade
    s.commit()
    uid = u.id
    s.close()
    return uid, bound_child_headers(uid)


def _seed_kp_with_mastery(user_id, content="比喻", prefix="kp"):
    """建一课 + 一个知识点 + 该孩子的 KnowledgeMastery，返回 knowledge_point_id。"""
    from app.database import SessionLocal
    from app.models import KnowledgeMastery, KnowledgePoint, Lesson, PdfDocument
    from app.services.bucket_service import ensure_bucket
    s = SessionLocal()
    bucket = ensure_bucket(s, user_id)
    doc = PdfDocument(filename=f"{prefix}.pdf", subject="语文", storage_path="")
    s.add(doc); s.flush()
    lesson = Lesson(document_id=doc.id, subject="语文", title=f"{prefix}课",
                    start_page=1, end_page=1, audit_status="approved")
    s.add(lesson); s.flush()
    kp = KnowledgePoint(lesson_id=lesson.id, subject="语文", category="修辞", content=content)
    s.add(kp); s.flush()
    s.add(KnowledgeMastery(user_id=user_id, bucket_id=bucket.id,
                           knowledge_point_id=kp.id, attempts="[]"))
    s.commit()
    kp_id = kp.id
    s.close()
    return kp_id


def test_topics_returns_knowledge_points_with_mastery():
    uid, h = _seed_child()
    kp_id = _seed_kp_with_mastery(uid, "比喻")
    r = _client().get(f"/api/expression/topics?user_id={uid}", headers=h)
    assert r.status_code == 200
    topics = r.json()["topics"]
    assert any(t["kind"] == "knowledge_point" and t["id"] == kp_id for t in topics)
    assert any(t["title"] == "比喻" for t in topics)


def test_topics_excludes_kp_without_mastery():
    from app.database import SessionLocal
    from app.models import KnowledgePoint, Lesson, PdfDocument
    uid, h = _seed_child(prefix="expr2")
    s = SessionLocal()
    doc = PdfDocument(filename="x.pdf", subject="语文", storage_path="")
    s.add(doc); s.flush()
    lesson = Lesson(document_id=doc.id, subject="语文", title="x课",
                    start_page=1, end_page=1, audit_status="approved")
    s.add(lesson); s.flush()
    kp = KnowledgePoint(lesson_id=lesson.id, subject="语文", category="修辞", content="没用过的")
    s.add(kp); s.commit()
    kp_id = kp.id
    s.close()

    r = _client().get(f"/api/expression/topics?user_id={uid}", headers=h)
    assert r.status_code == 200
    assert not any(t["id"] == kp_id and t["kind"] == "knowledge_point"
                   for t in r.json()["topics"])


def test_topics_returns_explore_items_only():
    """只有 kind='explore' 的条目能讲；drill_item 不返回。"""
    from app.database import SessionLocal
    from app.models import TrainingGroup, TrainingItem, User
    uid, h = _seed_child(prefix="expr3")
    s = SessionLocal()
    parent_id = s.get(User, uid).parent_id
    g = TrainingGroup(owner_id=parent_id, subject="语文", title="组", source="custom", kind="explore")
    s.add(g); s.flush()
    ex = TrainingItem(group_id=g.id, kind="explore", primary="比喻的规律")
    di = TrainingItem(group_id=g.id, kind="drill_item", primary="不该出现")
    s.add_all([ex, di]); s.commit()
    ex_id, di_id = ex.id, di.id
    s.close()

    topics = _client().get(f"/api/expression/topics?user_id={uid}", headers=h).json()["topics"]
    ids = {t["id"] for t in topics if t["kind"] == "training_item"}
    assert ex_id in ids
    assert di_id not in ids


def test_topics_rejects_grade_below_3():
    uid, h = _seed_child(grade=2, prefix="expr4")
    r = _client().get(f"/api/expression/topics?user_id={uid}", headers=h)
    assert r.status_code == 403


def test_topics_allows_grade_none():
    """grade is None 视为 3，放行（与 bucket_service 的 grade or 3 一致）。"""
    uid, h = _seed_child(grade=None, prefix="expr5")
    r = _client().get(f"/api/expression/topics?user_id={uid}", headers=h)
    assert r.status_code == 200


def test_topics_does_not_leak_across_buckets():
    """旧学年桶里的知识点不该出现在当前可讲列表里。"""
    from app.database import SessionLocal
    from app.models import KnowledgeMastery
    from app.services.bucket_service import ensure_bucket

    uid, h = _seed_child(prefix="bkt")
    kp_id = _seed_kp_with_mastery(uid, "旧桶的知识点", prefix="bkt")

    s = SessionLocal()
    old = ensure_bucket(s, uid)
    m = (s.query(KnowledgeMastery)
         .filter_by(user_id=uid, knowledge_point_id=kp_id)
         .first())
    m.bucket_id = old.id
    old.status = "archived"
    old.ended_at = old.started_at
    s.commit()
    s.close()

    topics = _client().get(
        f"/api/expression/topics?user_id={uid}", headers=h
    ).json()["topics"]
    assert not any(
        t["kind"] == "knowledge_point" and t["id"] == kp_id
        for t in topics
    )


def test_create_note_with_knowledge_point():
    uid, h = _seed_child(prefix="n1")
    kp_id = _seed_kp_with_mastery(uid, "比喻", prefix="n1")
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id,
        "text": "比喻就是把一个东西说成另一个东西，但要有相似点",
    }, headers=h)
    assert r.status_code == 200
    assert r.json()["id"] > 0


def test_create_note_snapshots_title():
    uid, h = _seed_child(prefix="n2")
    kp_id = _seed_kp_with_mastery(uid, "拟人", prefix="n2")
    _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "拟人是把东西写成人"
    }, headers=h)
    notes = _client().get(f"/api/expression/notes?user_id={uid}", headers=h).json()["notes"]
    assert notes[0]["title"] == "拟人"


def test_create_note_rejects_empty_text():
    uid, h = _seed_child(prefix="n3")
    kp_id = _seed_kp_with_mastery(uid, "排比", prefix="n3")
    for bad in ("", "   ", "\n\n"):
        r = _client().post("/api/expression/notes", json={
            "user_id": uid, "knowledge_point_id": kp_id, "text": bad
        }, headers=h)
        assert r.status_code == 400, f"{bad!r} 应被拒"


def test_create_note_rejects_too_long():
    uid, h = _seed_child(prefix="n4")
    kp_id = _seed_kp_with_mastery(uid, "夸张", prefix="n4")
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "字" * 5001
    }, headers=h)
    assert r.status_code == 400


def test_create_note_requires_exactly_one_target():
    uid, h = _seed_child(prefix="n5")
    kp_id = _seed_kp_with_mastery(uid, "反问", prefix="n5")
    r = _client().post("/api/expression/notes",
                       json={"user_id": uid, "text": "讲讲"}, headers=h)
    assert r.status_code == 400
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "item_id": 1, "text": "讲讲"
    }, headers=h)
    assert r.status_code == 400


def test_create_note_rejects_unowned_knowledge_point():
    uid, h = _seed_child(prefix="n6")
    other_uid, _oh = _seed_child(prefix="n6b")
    kp_id = _seed_kp_with_mastery(other_uid, "别人的知识点", prefix="n6b")
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "我讲讲"
    }, headers=h)
    assert r.status_code == 403


def test_parent_cannot_create_note():
    from app.database import SessionLocal
    from app.models import User
    uid, _h = _seed_child(prefix="n7")
    kp_id = _seed_kp_with_mastery(uid, "借代", prefix="n7")
    s = SessionLocal()
    parent_h = auth_headers(s.get(User, s.get(User, uid).parent_id))
    s.close()
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "家长代写"
    }, headers=parent_h)
    assert r.status_code == 403


def test_parent_can_read_child_notes():
    from app.database import SessionLocal
    from app.models import User
    uid, h = _seed_child(prefix="n8")
    kp_id = _seed_kp_with_mastery(uid, "设问", prefix="n8")
    _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "孩子写的"
    }, headers=h)

    s = SessionLocal()
    parent_h = auth_headers(s.get(User, s.get(User, uid).parent_id))
    s.close()
    r = _client().get(f"/api/expression/notes?user_id={uid}", headers=parent_h)
    assert r.status_code == 200
    assert r.json()["notes"][0]["text"] == "孩子写的"


def test_cannot_read_other_child_notes():
    uid, h = _seed_child(prefix="n9")
    other_uid, _oh = _seed_child(prefix="n9b")
    r = _client().get(f"/api/expression/notes?user_id={other_uid}", headers=h)
    assert r.status_code == 403


def test_delete_note():
    uid, h = _seed_child(prefix="n10")
    kp_id = _seed_kp_with_mastery(uid, "对偶", prefix="n10")
    note_id = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "删掉我"
    }, headers=h).json()["id"]
    r = _client().delete(f"/api/expression/notes/{note_id}", headers=h)
    assert r.status_code == 200
    assert _client().get(f"/api/expression/notes?user_id={uid}", headers=h).json()["notes"] == []


def test_cannot_delete_other_child_note():
    uid, h = _seed_child(prefix="n11")
    other_uid, other_h = _seed_child(prefix="n11b")
    kp_id = _seed_kp_with_mastery(other_uid, "对比", prefix="n11b")
    note_id = _client().post("/api/expression/notes", json={
        "user_id": other_uid, "knowledge_point_id": kp_id, "text": "别人的"
    }, headers=other_h).json()["id"]
    r = _client().delete(f"/api/expression/notes/{note_id}", headers=h)
    assert r.status_code == 403


def test_note_survives_knowledge_point_deletion():
    """知识点被删后，记录仍可读（title 快照 + FK SET NULL）。"""
    from app.database import SessionLocal
    from app.models import KnowledgeMastery, KnowledgePoint
    uid, h = _seed_child(prefix="n12")
    kp_id = _seed_kp_with_mastery(uid, "被删掉的知识点", prefix="n12")
    _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "我讲过了"
    }, headers=h)

    s = SessionLocal()
    # knowledge_points 被 KnowledgeMastery 引用，先清掉后者再删前者
    s.query(KnowledgeMastery).filter_by(knowledge_point_id=kp_id).delete(synchronize_session=False)
    s.query(KnowledgePoint).filter_by(id=kp_id).delete(synchronize_session=False)
    s.commit()
    s.close()

    notes = _client().get(f"/api/expression/notes?user_id={uid}", headers=h).json()["notes"]
    assert len(notes) == 1
    assert notes[0]["title"] == "被删掉的知识点"
    assert notes[0]["text"] == "我讲过了"


def test_create_note_rejects_knowledge_point_from_archived_bucket():
    """旧学年桶里的知识点不能用于新建表达记录。"""
    from app.database import SessionLocal
    from app.models import KnowledgeMastery
    from app.services.bucket_service import ensure_bucket

    uid, h = _seed_child(prefix="archived_post")
    kp_id = _seed_kp_with_mastery(
        uid, "旧桶的知识点", prefix="archived_post")

    s = SessionLocal()
    old = ensure_bucket(s, uid)
    mastery = (s.query(KnowledgeMastery)
               .filter_by(user_id=uid, knowledge_point_id=kp_id)
               .first())
    mastery.bucket_id = old.id
    old.status = "archived"
    old.ended_at = old.started_at
    s.commit()
    s.close()

    r = _client().post("/api/expression/notes", json={
        "user_id": uid,
        "knowledge_point_id": kp_id,
        "text": "这是旧学年学过的",
    }, headers=h)
    assert r.status_code == 403


def test_create_note_with_owned_explore_item_snapshots_primary():
    from app.database import SessionLocal
    from app.models import TrainingGroup, TrainingItem, User

    uid, h = _seed_child(prefix="item_ok")
    s = SessionLocal()
    parent_id = s.get(User, uid).parent_id
    group = TrainingGroup(
        owner_id=parent_id, subject="语文", title="探究组",
        source="custom", kind="explore")
    s.add(group); s.flush()
    item = TrainingItem(
        group_id=group.id, kind="explore", primary="比喻的相似关系")
    s.add(item); s.commit()
    item_id = item.id
    s.close()

    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "item_id": item_id, "text": "我来讲讲这个关系",
    }, headers=h)
    assert r.status_code == 200

    notes = _client().get(
        f"/api/expression/notes?user_id={uid}", headers=h).json()["notes"]
    assert notes[0]["title"] == "比喻的相似关系"


def test_create_note_rejects_another_familys_item():
    from app.database import SessionLocal
    from app.models import TrainingGroup, TrainingItem, User

    uid, h = _seed_child(prefix="item_family_a")
    other_uid, _ = _seed_child(prefix="item_family_b")
    s = SessionLocal()
    other_parent_id = s.get(User, other_uid).parent_id
    group = TrainingGroup(
        owner_id=other_parent_id, subject="语文", title="别家的组",
        source="custom", kind="explore")
    s.add(group); s.flush()
    item = TrainingItem(
        group_id=group.id, kind="explore", primary="别家的探究")
    s.add(item); s.commit()
    item_id = item.id
    s.close()

    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "item_id": item_id, "text": "不该能讲",
    }, headers=h)
    assert r.status_code == 403


def test_create_note_rejects_non_explore_item():
    from app.database import SessionLocal
    from app.models import TrainingGroup, TrainingItem, User

    uid, h = _seed_child(prefix="item_drill")
    s = SessionLocal()
    parent_id = s.get(User, uid).parent_id
    group = TrainingGroup(
        owner_id=parent_id, subject="语文", title="练习组",
        source="custom", kind="explore")
    s.add(group); s.flush()
    item = TrainingItem(
        group_id=group.id, kind="drill_item", primary="普通练习")
    s.add(item); s.commit()
    item_id = item.id
    s.close()

    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "item_id": item_id, "text": "不该能讲",
    }, headers=h)
    assert r.status_code == 403


def test_admin_cannot_create_note_for_child():
    from app.database import SessionLocal

    uid, _ = _seed_child(prefix="admin_write")
    kp_id = _seed_kp_with_mastery(uid, "借喻", prefix="admin_write")
    s = SessionLocal()
    admin = make_account(s, "expression_admin", "admin")
    admin_h = auth_headers(admin)
    s.close()

    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "管理员代写",
    }, headers=admin_h)
    assert r.status_code == 403


def test_list_notes_clamps_limit():
    uid, h = _seed_child(prefix="limit")
    kp_id = _seed_kp_with_mastery(uid, "排比", prefix="limit")
    for text in ("第一条", "第二条"):
        r = _client().post("/api/expression/notes", json={
            "user_id": uid, "knowledge_point_id": kp_id, "text": text,
        }, headers=h)
        assert r.status_code == 200

    low = _client().get(
        f"/api/expression/notes?user_id={uid}&limit=0", headers=h)
    assert low.status_code == 200
    assert len(low.json()["notes"]) == 1

    high = _client().get(
        f"/api/expression/notes?user_id={uid}&limit=999", headers=h)
    assert high.status_code == 200
    assert len(high.json()["notes"]) == 2


def test_purge_lesson_detaches_expression_notes():
    """删课（含知识点）时，expression_notes 的外键必须被置空，记录本身保留。"""
    from app.database import SessionLocal
    from app.models import ExpressionNote, KnowledgePoint
    from app.services.cleanup import purge_lessons

    uid, h = _seed_child(prefix="pg1")
    kp_id = _seed_kp_with_mastery(uid, "要被删的", prefix="pg1")
    _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "我讲过了"
    }, headers=h)

    s = SessionLocal()
    lesson_id = s.get(KnowledgePoint, kp_id).lesson_id
    purge_lessons(s, [lesson_id])          # 不应抛外键异常
    s.commit()
    s.close()

    # 记录仍在，但外键已置空，title 快照可读
    s = SessionLocal()
    try:
        rows = s.query(ExpressionNote).filter_by(user_id=uid).all()
        assert len(rows) == 1
        assert rows[0].knowledge_point_id is None, "外键应为 NULL"
        assert rows[0].title == "要被删的"
        assert rows[0].text == "我讲过了"
    finally:
        s.close()
