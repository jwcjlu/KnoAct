"""学年桶与孩子档案字段的模型层测试。"""
from app.models import User, SchoolYearBucket, ChildConfig


def test_user_has_grade_edition_parent_fields(setup_db, db):
    parent = User(name="金爸爸", role="parent")
    db.add(parent); db.flush()
    child = User(name="晨晨", role="child", grade=3, edition="人教版", parent_id=parent.id)
    db.add(child); db.commit()
    got = db.get(User, child.id)
    assert got.grade == 3
    assert got.edition == "人教版"
    assert got.parent_id == parent.id


def test_user_grade_defaults_to_none(setup_db, db):
    u = User(name="老用户", role="child")
    db.add(u); db.commit()
    assert db.get(User, u.id).grade is None


def test_school_year_bucket_fields(setup_db, db):
    child = User(name="晨晨", role="child", grade=3)
    db.add(child); db.flush()
    b = SchoolYearBucket(user_id=child.id, grade=3, school_year="2025-2026", status="active")
    db.add(b); db.commit()
    got = db.get(SchoolYearBucket, b.id)
    assert got.user_id == child.id
    assert got.grade == 3
    assert got.school_year == "2025-2026"
    assert got.status == "active"


def test_child_config_override(setup_db, db):
    child = User(name="晨晨", role="child", grade=3)
    db.add(child); db.flush()
    c = ChildConfig(user_id=child.id, key="difficulty_语文", value="困难")
    db.add(c); db.commit()
    got = db.get(ChildConfig, c.id)
    assert got.key == "difficulty_语文"
    assert got.value == "困难"


def test_mistake_belongs_to_bucket(setup_db, db):
    from app.models import Mistake
    child = User(name="晨晨", role="child", grade=3)
    db.add(child); db.flush()
    b = SchoolYearBucket(user_id=child.id, grade=3, school_year="2025-2026")
    db.add(b); db.flush()
    m = Mistake(user_id=child.id, bucket_id=b.id, source_type="dictation",
                question="听写：苹果", your_answer="苹菓", correct_answer="苹果")
    db.add(m); db.commit()
    got = db.get(Mistake, m.id)
    assert got.bucket_id == b.id


def test_point_belongs_to_bucket(setup_db, db):
    from app.models import Point
    child = User(name="晨晨", role="child", grade=3)
    db.add(child); db.flush()
    b = SchoolYearBucket(user_id=child.id, grade=3, school_year="2025-2026")
    db.add(b); db.flush()
    p = Point(user_id=child.id, bucket_id=b.id, delta=20, reason="完成听写")
    db.add(p); db.commit()
    assert db.get(Point, p.id).bucket_id == b.id
