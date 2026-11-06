"""回看切换：查询按桶过滤；历史桶只读。"""
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User, SchoolYearBucket, Point
from app.services.bucket_service import ensure_bucket, promote_grade
from conftest import bound_child_headers


def _client():
    return TestClient(app)


def _child_with_two_buckets():
    s = SessionLocal()
    parent = User(name="p_br", role="parent")
    s.add(parent); s.flush()
    u = User(name="晨晨", role="child", grade=3, parent_id=parent.id)
    s.add(u); s.commit()
    b3 = ensure_bucket(s, u.id)
    s.add(Point(user_id=u.id, bucket_id=b3.id, delta=30, reason="三年级"))
    s.commit()
    promote_grade(s, u.id)  # 升到四年级
    b4 = ensure_bucket(s, u.id)
    s.add(Point(user_id=u.id, bucket_id=b4.id, delta=10, reason="四年级"))
    s.commit()
    uid = u.id
    s.close()
    return uid


def test_points_balance_defaults_to_active_bucket(setup_db):
    uid = _child_with_two_buckets()
    resp = _client().get(f"/api/points/balance?user_id={uid}", headers=bound_child_headers(uid))
    assert resp.json()["balance"] == 10  # 只算四年级（当前 active）桶


def test_points_balance_can_view_old_bucket(setup_db):
    uid = _child_with_two_buckets()
    s = SessionLocal()
    b3 = s.query(SchoolYearBucket).filter_by(user_id=uid, grade=3).first()
    s.close()
    resp = _client().get(f"/api/points/balance?user_id={uid}&bucket_id={b3.id}",
                         headers=bound_child_headers(uid))
    assert resp.json()["balance"] == 30  # 回看三年级桶
