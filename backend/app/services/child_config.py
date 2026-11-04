"""孩子配置覆盖：读配置时按 孩子覆盖 > 全局 ModelConfig > 默认 三级降级。"""
from sqlalchemy.orm import Session
from ..models import ModelConfig, ChildConfig


def get_child_config_str(db: Session, child_id: int, key: str, fallback: str) -> str:
    row = db.query(ChildConfig).filter_by(user_id=child_id, key=key).first()
    if row and row.value:
        return row.value
    g = db.query(ModelConfig).filter_by(key=key).first()
    return g.value if g and g.value else fallback


def get_child_config_int(db: Session, child_id: int, key: str, fallback: int) -> int:
    val = get_child_config_str(db, child_id, key, "")
    try:
        return int(val) if val else fallback
    except ValueError:
        return fallback
