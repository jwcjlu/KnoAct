"""迁移脚本：存量孩子补年级、建桶、回填 bucket_id。"""
from app.migrate_grade_buckets import migrate
from app.models import User, SchoolYearBucket, Mistake, Point


def test_migrate_backfills_existing_children(setup_db, db):
    # 造存量数据：无年级、无桶、已有错题/积分
    child = User(name="晨晨", role="child")
    db.add(child); db.commit()
    db.add(Mistake(user_id=child.id, source_type="dictation",
                   question="听写：苹果", your_answer="苹菓", correct_answer="苹果"))
    db.add(Point(user_id=child.id, delta=20, reason="旧积分"))
    db.commit()

    migrate(db)

    got = db.get(User, child.id)
    assert got.grade == 3  # 缺省三年级
    bucket = db.query(SchoolYearBucket).filter_by(user_id=child.id).first()
    assert bucket is not None
    assert bucket.status == "active"
    m = db.query(Mistake).filter_by(user_id=child.id).first()
    assert m.bucket_id == bucket.id
    p = db.query(Point).filter_by(user_id=child.id).first()
    assert p.bucket_id == bucket.id


def test_migrate_idempotent(setup_db, db):
    child = User(name="晨晨", role="child")
    db.add(child); db.commit()
    migrate(db)
    migrate(db)  # 二次运行不应重复建桶
    buckets = db.query(SchoolYearBucket).filter_by(user_id=child.id).all()
    assert len(buckets) == 1
