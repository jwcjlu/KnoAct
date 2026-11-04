"""学年桶列表：前端切换学年用。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import SchoolYearBucket

router = APIRouter(prefix="/api/buckets", tags=["buckets"])


@router.get("")
def list_buckets(user_id: int, db: Session = Depends(get_db)):
    buckets = (db.query(SchoolYearBucket)
               .filter_by(user_id=user_id)
               .order_by(SchoolYearBucket.grade.desc(), SchoolYearBucket.id.desc())
               .all())
    return [
        {"id": b.id, "grade": b.grade, "school_year": b.school_year, "status": b.status}
        for b in buckets
    ]
