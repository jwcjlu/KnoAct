"""学年桶服务：当前桶解析、兜底建桶、升年级（幂等）。

学年定义：9 月 1 日 ~ 次年 8 月 31 日。school_year 形如 "2025-2026"。
升年级 = 封存当前 active 桶 + 新建 grade+1 的 active 桶 + 更新 User.grade。
"""
from datetime import datetime, date

from sqlalchemy.orm import Session

from ..models import User, SchoolYearBucket


def current_school_year(today: date | None = None) -> str:
    """返回当前日期的学年字符串（如 "2025-2026"）。"""
    today = today or date.today()
    if today.month >= 9:
        return f"{today.year}-{today.year + 1}"
    return f"{today.year - 1}-{today.year}"


def get_active_bucket(db: Session, user_id: int) -> SchoolYearBucket | None:
    return (db.query(SchoolYearBucket)
            .filter_by(user_id=user_id, status="active")
            .order_by(SchoolYearBucket.id.desc())
            .first())


def ensure_bucket(db: Session, user_id: int) -> SchoolYearBucket:
    """取孩子当前 active 桶；没有则按 User.grade 兜底建一个。"""
    active = get_active_bucket(db, user_id)
    if active:
        return active
    user = db.get(User, user_id)
    grade = user.grade if user and user.grade else 3  # 缺省三年级
    bucket = SchoolYearBucket(
        user_id=user_id, grade=grade,
        school_year=current_school_year(), status="active",
        started_at=datetime.utcnow(),
    )
    db.add(bucket)
    db.commit()
    db.refresh(bucket)
    return bucket


def promote_grade(db: Session, user_id: int, target_grade: int | None = None) -> SchoolYearBucket:
    """升年级（幂等）：封存当前桶、开新桶、更新 User.grade。

    target_grade 缺省 = 当前 grade + 1；可传具体值以支持跳级/留级（家长手动改）。
    幂等保证（两层）：
      1. 显式 target_grade 已等于当前 User.grade 时，直接返回现有 active 桶；
      2. 裸升（无 target）且本学年已升过一次（存在本学年已封存的桶）时，直接返回
         现有 active 桶，不再重复 +1（对齐设计「同一学年多次触发只升一次」）。
    """
    user = db.get(User, user_id)
    if not user:
        raise ValueError(f"user {user_id} not found")
    base_grade = user.grade or 3  # 与 ensure_bucket 的缺省三年级保持一致
    new_grade = target_grade if target_grade is not None else base_grade + 1
    if new_grade == user.grade:
        # 已是目标年级，确保有 active 桶即可（留级到同级视为 no-op）
        return ensure_bucket(db, user_id)
    active = get_active_bucket(db, user_id)
    if target_grade is None:
        # 幂等：本学年已升过一次（存在本学年已封存的桶），裸升 +1 不再重复
        sy = current_school_year()
        already_promoted = (db.query(SchoolYearBucket)
                            .filter_by(user_id=user_id, status="archived",
                                       school_year=sy)
                            .first() is not None)
        if already_promoted:
            return active or ensure_bucket(db, user_id)
    now = datetime.utcnow()
    if active:
        active.status = "archived"
        active.ended_at = now
    bucket = SchoolYearBucket(
        user_id=user_id, grade=new_grade,
        school_year=current_school_year(), status="active",
        started_at=now,
    )
    user.grade = new_grade
    db.add(bucket)
    db.commit()
    db.refresh(bucket)
    return bucket
