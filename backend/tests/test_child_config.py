"""孩子配置覆盖：孩子 > 全局 > 默认 三级降级。"""
from app.services.child_config import get_child_config_int, get_child_config_str
from app.models import User, ModelConfig, ChildConfig


def _child(db, grade=3):
    u = User(name="晨晨", role="child", grade=grade)
    db.add(u); db.flush()
    return u


def test_child_override_wins(setup_db, db):
    child = _child(db)
    db.add(ModelConfig(key="difficulty_语文", value="中等"))
    db.add(ChildConfig(user_id=child.id, key="difficulty_语文", value="困难"))
    db.commit()
    assert get_child_config_str(db, child.id, "difficulty_语文", "默认") == "困难"


def test_falls_back_to_global(setup_db, db):
    child = _child(db)
    db.add(ModelConfig(key="task_dictation_count_语文", value="10"))
    db.commit()
    assert get_child_config_int(db, child.id, "task_dictation_count_语文", 7) == 10


def test_falls_back_to_default(setup_db, db):
    child = _child(db)
    db.commit()
    assert get_child_config_int(db, child.id, "nope", 7) == 7
    assert get_child_config_str(db, child.id, "nope", "默认") == "默认"
