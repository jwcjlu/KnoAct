# backend/tests/test_knowledge_review.py
from app.models import KnowledgeReviewItem


def test_knowledge_review_item_columns():
    cols = {c.name for c in KnowledgeReviewItem.__table__.columns}
    for name in (
        "id", "user_id", "knowledge_point_id", "bucket_id",
        "enrolled_by", "enroll_source", "enrolled_at",
        "status", "interval_index", "next_review_at",
        "last_result", "updated_at",
    ):
        assert name in cols, f"缺列 {name}"


def test_knowledge_review_item_unique_user_kp_bucket():
    # 至少有一对 (user_id, knowledge_point_id, bucket_id) 唯一约束
    assert any(
        set(c.name for c in u.columns) >= {"user_id", "knowledge_point_id", "bucket_id"}
        for u in KnowledgeReviewItem.__table__.constraints
        if u.__class__.__name__ == "UniqueConstraint"
    )