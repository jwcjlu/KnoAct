"""表达练习（孩子讲一遍）的模型层测试。

本表刻意不含 verdict / score / ai_* —— 见 spec 的「五轮失败记录」。
"""
from sqlalchemy import inspect as sa_inspect

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