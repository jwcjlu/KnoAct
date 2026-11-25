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
    s = SessionLocal()
    doc = PdfDocument(filename=f"{prefix}.pdf", subject="语文", storage_path="")
    s.add(doc); s.flush()
    lesson = Lesson(document_id=doc.id, subject="语文", title=f"{prefix}课",
                    start_page=1, end_page=1, audit_status="approved")
    s.add(lesson); s.flush()
    kp = KnowledgePoint(lesson_id=lesson.id, subject="语文", category="修辞", content=content)
    s.add(kp); s.flush()
    s.add(KnowledgeMastery(user_id=user_id, knowledge_point_id=kp.id, attempts="[]"))
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