"""学年桶服务：当前桶解析、兜底建桶、升年级幂等。"""
from datetime import datetime

from app.services.bucket_service import (
    get_active_bucket, ensure_bucket, promote_grade, current_school_year,
)
from app.models import User, SchoolYearBucket


def _child(db, grade=3):
    u = User(name="晨晨", role="child", grade=grade)
    db.add(u); db.flush()
    return u


def test_get_active_bucket_returns_active(setup_db, db):
    child = _child(db, 3)
    b = SchoolYearBucket(user_id=child.id, grade=3, school_year="2025-2026", status="active")
    db.add(b); db.commit()
    assert get_active_bucket(db, child.id).id == b.id


def test_get_active_bucket_none_when_no_bucket(setup_db, db):
    child = _child(db, 3)
    db.commit()
    assert get_active_bucket(db, child.id) is None


def test_ensure_bucket_creates_when_missing(setup_db, db):
    child = _child(db, 3)
    db.commit()
    b = ensure_bucket(db, child.id)
    assert b is not None
    assert b.grade == 3
    assert b.status == "active"
    assert b.school_year == current_school_year()


def test_ensure_bucket_idempotent(setup_db, db):
    child = _child(db, 3)
    db.commit()
    b1 = ensure_bucket(db, child.id)
    b2 = ensure_bucket(db, child.id)
    assert b1.id == b2.id


def test_promote_grade_archives_old_and_creates_new(setup_db, db):
    child = _child(db, 3)
    db.commit()
    ensure_bucket(db, child.id)
    promote_grade(db, child.id)
    db.refresh(child)
    assert child.grade == 4
    buckets = db.query(SchoolYearBucket).filter_by(user_id=child.id).all()
    assert len(buckets) == 2
    assert sum(1 for b in buckets if b.status == "active") == 1
    active = get_active_bucket(db, child.id)
    assert active.grade == 4


def test_promote_grade_idempotent(setup_db, db):
    child = _child(db, 3)
    db.commit()
    ensure_bucket(db, child.id)
    promote_grade(db, child.id)
    promote_grade(db, child.id)  # 第二次应无效果
    db.refresh(child)
    assert child.grade == 4
    assert len(db.query(SchoolYearBucket).filter_by(user_id=child.id).all()) == 2


def test_current_school_year_september_boundary():
    sy = current_school_year()
    assert len(sy) == 9 and sy[4] == "-"
