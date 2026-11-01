from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(role: str | None = None, db: Session = Depends(get_db)):
    """用户列表（家长端选择孩子用）：可按 role 过滤，按 id 升序。"""
    q = db.query(User)
    if role:
        q = q.filter_by(role=role)
    return [{"id": u.id, "name": u.name, "role": u.role} for u in q.order_by(User.id).all()]
