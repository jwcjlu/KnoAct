from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.access import ensure_user_access, require_learning_user, resolve_target_user_id
from ..database import get_db
from ..models import Point, Reward, User
from ..services.bucket_guard import resolve_bucket_id, assert_writable

router = APIRouter(prefix="/api/points", tags=["points"])

RATES = {"tablet": 300, "phone": 200}  # 每 30/20 分钟对应积分，简化

class RedeemReq(BaseModel):
    user_id: int
    device: str
    minutes: int

@router.get("/balance")
def balance(user_id: int = Depends(resolve_target_user_id),
            _auth: User = Depends(require_learning_user),
            bucket_id: int | None = None, db: Session = Depends(get_db)):
    bid = resolve_bucket_id(db, user_id, bucket_id)
    if bid is None:
        return {"balance": 0}
    total = sum(p.delta for p in db.query(Point).filter_by(user_id=user_id, bucket_id=bid).all())
    return {"balance": total}

@router.post("/redeem")
def redeem(req: RedeemReq, user: User = Depends(require_learning_user),
           bucket_id: int | None = None, db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    assert_writable(db, req.user_id, bucket_id)
    bid = resolve_bucket_id(db, req.user_id, bucket_id)
    if bid is None:
        return {"success": False, "reason": "积分不足"}
    cost = RATES.get(req.device, 300)
    total = sum(p.delta for p in db.query(Point).filter_by(user_id=req.user_id, bucket_id=bid).all())
    if total < cost:
        return {"success": False, "reason": "积分不足"}
    db.add(Point(user_id=req.user_id, bucket_id=bid, delta=-cost, reason=f"兑换 {req.device} {req.minutes} 分钟"))
    db.add(Reward(user_id=req.user_id, device=req.device, minutes=req.minutes, points_cost=cost))
    db.commit()
    return {"success": True, "cost": cost}
