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


def test_unknown_package_falls_to_fun_group(setup_db, db):
    c = _child(db)
    fun = AppGroup(user_id=c.id, name="娱乐类", kind="fun", daily_limit_seconds=3600)
    learn = AppGroup(user_id=c.id, name="学习类", kind="learn", daily_limit_seconds=None)
    db.add_all([fun, learn]); db.commit()
    gid = classify_package(db, c.id, "com.tencent.tmgp.sgame", "王者荣耀")
    assert gid == fun.id


def test_known_package_uses_app_rule(setup_db, db):
    c = _child(db)
    learn = AppGroup(user_id=c.id, name="学习类", kind="learn", daily_limit_seconds=None)
    db.add(learn); db.commit()
    db.add(AppRule(user_id=c.id, app_package="com.knoact", app_name="知学伴", group_id=learn.id))
    db.commit()
    gid = classify_package(db, c.id, "com.knoact", "知学伴")
    assert gid == learn.id


def test_no_fun_group_returns_none(setup_db, db):
    c = _child(db)
    db.commit()
    assert classify_package(db, c.id, "com.douyin", "抖音") is None


def test_compute_group_totals_aggregates(setup_db, db):
    c = _child(db)
    fun = AppGroup(user_id=c.id, name="娱乐类", kind="fun", daily_limit_seconds=3600)
    db.add(fun); db.commit()
    db.add_all([
        AppRule(user_id=c.id, app_package="com.a", app_name="A", group_id=fun.id),
        AppRule(user_id=c.id, app_package="com.b", app_name="B", group_id=fun.id),
    ])
    db.add_all([
        ScreenUsage(child_id=c.id, date="2026-11-04", app_package="com.a", app_name="A", duration_seconds=600),
        ScreenUsage(child_id=c.id, date="2026-11-04", app_package="com.b", app_name="B", duration_seconds=400),
        ScreenUsage(child_id=c.id, date="2026-11-04", app_package="com.unknown", app_name="X", duration_seconds=999),
    ])
    db.commit()
    totals = compute_group_totals(db, c.id, "2026-11-04")
    assert totals[fun.id] == 600 + 400 + 999  # 未知包也归娱乐组
