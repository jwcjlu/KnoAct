"""学年桶列表：前端切换学年用。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..core.access import require_learning_user, resolve_target_user_id
from ..database import get_db
from ..models import SchoolYearBucket, User

router = APIRouter(prefix="/api/buckets", tags=["buckets"])


@router.get("")
def list_buckets(user_id: int = Depends(resolve_target_user_id),
                 _auth: User = Depends(require_learning_user),
                 db: Session = Depends(get_db)):
    buckets = (db.query(SchoolYearBucket)
               .filter_by(user_id=user_id)
               .order_by(SchoolYearBucket.grade.desc(), SchoolYearBucket.id.desc())
               .all())
    return [
        {"id": b.id, "grade": b.grade, "school_year": b.school_year, "status": b.status}
        for b in buckets
    ]
