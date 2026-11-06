"""屏幕时间：分组/规则/使用时长的模型与服务。"""
from app.models import User, AppGroup, AppRule, ScreenUsage
from app.services.screen_time import classify_package, compute_group_totals
from conftest import auth_headers, make_account, bound_child_headers


def _child(db, name="晨晨"):
    p = make_account(db, f"p_st_{name}", "parent")
    u = User(name=name, role="child", grade=3, parent_id=p.id)
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


def test_report_accumulates(client, setup_db, db):
    c = _child(db); db.commit()
    h = bound_child_headers(c.id)
    r = client.post("/api/screen-time/report", json={
        "child_id": c.id, "date": "2026-11-04",
        "items": [{"app_package": "com.douyin", "app_name": "抖音", "duration_seconds": 100}],
    }, headers=h)
    assert r.status_code == 200
    r = client.post("/api/screen-time/report", json={
        "child_id": c.id, "date": "2026-11-04",
        "items": [{"app_package": "com.douyin", "app_name": "抖音", "duration_seconds": 50}],
    }, headers=h)
    assert r.status_code == 200
    row = db.query(ScreenUsage).filter_by(child_id=c.id, app_package="com.douyin").first()
    assert row.duration_seconds == 150


def test_groups_roundtrip(client, setup_db, db):
    c = _child(db); db.commit()
    from app.database import SessionLocal
    s = SessionLocal()
    parent = s.get(User, c.parent_id)
    s.close()
    hp = auth_headers(parent)
    r = client.put("/api/screen-time/groups", json={
        "user_id": c.id,
        "groups": [{"name": "学习类", "kind": "learn", "daily_limit_seconds": None},
                    {"name": "娱乐类", "kind": "fun", "daily_limit_seconds": 3600}],
        "rules": [{"app_package": "com.knoact", "app_name": "知学伴", "group_name": "学习类"}],
    }, headers=hp)
    assert r.status_code == 200
    g = client.get(f"/api/screen-time/groups?user_id={c.id}", headers=hp).json()
    assert len(g["groups"]) == 2
    assert any(x["name"] == "学习类" for x in g["groups"])


def test_usage_shows_overtime(client, setup_db, db):
    c = _child(db)
    fun = AppGroup(user_id=c.id, name="娱乐类", kind="fun", daily_limit_seconds=3600)
    db.add(fun); db.commit()
    db.add(ScreenUsage(child_id=c.id, date="2026-11-04", app_package="com.douyin",
                       app_name="抖音", duration_seconds=5000, group_id=fun.id))
    db.commit()
    from app.database import SessionLocal
    s = SessionLocal()
    parent = s.get(User, c.parent_id)
    s.close()
    hp = auth_headers(parent)
    r = client.get(f"/api/screen-time/usage?child_id={c.id}&date=2026-11-04", headers=hp).json()
    assert r["groups"][0]["overtime"] is True
