"""一次性迁移：给存量 child 补 grade、建默认 active 桶、回填学习痕迹 bucket_id。

幂等：已建桶的孩子跳过；已有 grade 的不覆盖。
运行方式：cd backend && python -m app.migrate_grade_buckets
"""
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import (User, SchoolYearBucket, Mistake, Task, Point, Goal,
                     WordMastery, KnowledgeMastery, Quiz, Question)
from .services.bucket_service import current_school_year


# 需要回填 bucket_id 的 (模型) —— 均含 user_id 列
_TRACE_MODELS = [Mistake, Task, Point, Goal, WordMastery, KnowledgeMastery, Quiz]


def migrate(db: Session) -> None:
    children = db.query(User).filter_by(role="child").all()
    for child in children:
        if child.grade is None:
            child.grade = 3  # 缺省三年级
        # 已有 active 桶则跳过
        existing = db.query(SchoolYearBucket).filter_by(user_id=child.id, status="active").first()
        if existing:
            db.commit()
            continue
        bucket = SchoolYearBucket(user_id=child.id, grade=child.grade,
                                  school_year=current_school_year(), status="active")
        db.add(bucket)
        db.flush()
        for model in _TRACE_MODELS:
            rows = db.query(model).filter_by(user_id=child.id, bucket_id=None).all()
            for r in rows:
                r.bucket_id = bucket.id
        db.commit()
    # 丢弃无归属的存量全局题目（改为按孩子生成后不再有全局题）
    db.query(Question).filter(Question.user_id.is_(None)).delete(synchronize_session=False)
    db.commit()


if __name__ == "__main__":
    db = SessionLocal()
    try:
        migrate(db)
        print("迁移完成")
    finally:
        db.close()
