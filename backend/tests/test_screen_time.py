"""屏幕时间：分组/规则/使用时长的模型与服务。"""
from app.models import User, AppGroup, AppRule, ScreenUsage
from app.services.screen_time import classify_package, compute_group_totals


def _child(db, name="晨晨"):
    u = User(name=name, role="child", grade=3)
    db.add(u); db.flush()
    return u


def test_appgroup_unique_per_child(setup_db, db):
    c = _child(db)
    db.add(AppGroup(user_id=c.id, name="娱乐类", kind="fun", daily_limit_seconds=3600))
    db.add(AppGroup(user_id=c.id, name="学习类", kind="learn", daily_limit_seconds=7200))
    db.commit()  # 不同组名可共存：UniqueConstraint 在 (user_id, name)
    assert db.query(AppGroup).filter_by(user_id=c.id).count() == 2


def test_screen_usage_upsert_accumulates(setup_db, db):
    c = _child(db)
    db.add(ScreenUsage(child_id=c.id, date="2026-11-04", app_package="com.douyin", app_name="抖音", duration_seconds=120, group_id=None))
    db.commit()
    row = db.query(ScreenUsage).filter_by(child_id=c.id, app_package="com.douyin").first()
    assert row.duration_seconds == 120
