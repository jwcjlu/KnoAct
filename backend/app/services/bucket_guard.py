"""桶只读守卫：写操作前校验目标桶是否为当前 active 桶。"""
from sqlalchemy.orm import Session
from ..models import SchoolYearBucket
from .bucket_service import get_active_bucket


def resolve_bucket_id(db: Session, user_id: int, bucket_id: int | None) -> int | None:
    """解析查询用的桶：显式 bucket_id 优先，否则当前 active 桶；都没有返回 None。"""
    if bucket_id is not None:
        return bucket_id
    active = get_active_bucket(db, user_id)
    return active.id if active else None


def assert_writable(db: Session, user_id: int, bucket_id: int | None = None) -> None:
    """写操作守卫：bucket_id 未指定时默认写 active 桶（允许）；指定了历史桶则拒绝。"""
    if bucket_id is None:
        return
    active = get_active_bucket(db, user_id)
    if active is None or active.id != bucket_id:
        raise PermissionError("历史学年只读，不能修改")
