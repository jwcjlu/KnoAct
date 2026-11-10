"""孩子配置覆盖：孩子 > 全局 > 默认 三级降级。"""
from app.services.child_config import get_child_config_int, get_child_config_str, get_child_config_float
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


def test_get_dictation_input_mode_defaults_without_row(setup_db, db):
    child = _child(db)
    db.commit()
    from app.services.child_config import get_dictation_input_mode

    assert get_dictation_input_mode(db, child.id) == "paper_photo"


def test_get_dictation_input_mode_ignores_model_config(setup_db, db):
    child = _child(db)
    db.add(ModelConfig(key="dictation_input_mode", value="on_screen"))
    db.commit()
    from app.services.child_config import get_dictation_input_mode

    assert get_dictation_input_mode(db, child.id) == "paper_photo"


def test_set_child_config_str_upsert(setup_db, db):
    child = _child(db)
    db.commit()
    from app.services.child_config import get_dictation_input_mode, set_child_config_str

    set_child_config_str(db, child.id, "dictation_input_mode", "on_screen")
    assert get_dictation_input_mode(db, child.id) == "on_screen"
    set_child_config_str(db, child.id, "dictation_input_mode", "paper_photo")
    assert get_dictation_input_mode(db, child.id) == "paper_photo"


def test_get_child_config_float_child_override(setup_db, db):
    child = _child(db)
    db.add(ModelConfig(key="task_dictation_due_cap", value="0.5"))
    db.add(ChildConfig(user_id=child.id, key="task_dictation_due_cap", value="0.3"))
    db.commit()
    assert get_child_config_float(db, child.id, "task_dictation_due_cap", 0.5) == 0.3


def test_get_child_config_float_falls_back_to_global(setup_db, db):
    child = _child(db)
    db.add(ModelConfig(key="task_dictation_new_floor", value="0.4"))
    db.commit()
    assert get_child_config_float(db, child.id, "task_dictation_new_floor", 0.3) == 0.4


def test_get_child_config_float_falls_back_to_default(setup_db, db):
    child = _child(db)
    db.commit()
    assert get_child_config_float(db, child.id, "nope_float", 0.25) == 0.25


def test_get_child_config_float_clamps_to_01(setup_db, db):
    child = _child(db)
    db.add(ChildConfig(user_id=child.id, key="task_dictation_due_cap", value="2.5"))
    db.commit()
    assert get_child_config_float(db, child.id, "task_dictation_due_cap", 0.5) == 1.0
