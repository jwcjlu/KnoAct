from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Point, Reward

router = APIRouter(prefix="/api/points", tags=["points"])

RATES = {"tablet": 300, "phone": 200}  # 每 30/20 分钟对应积分，简化

class RedeemReq(BaseModel):
    user_id: int
    device: str
    minutes: int

@router.get("/balance")
def balance(user_id: int, db: Session = Depends(get_db)):
    total = sum(p.delta for p in db.query(Point).filter_by(user_id=user_id).all())
    return {"balance": total}

@router.post("/redeem")
def redeem(req: RedeemReq, db: Session = Depends(get_db)):
    cost = RATES.get(req.device, 300)
    total = sum(p.delta for p in db.query(Point).filter_by(user_id=req.user_id).all())
    if total < cost:
        return {"success": False, "reason": "积分不足"}
    db.add(Point(user_id=req.user_id, delta=-cost, reason=f"兑换 {req.device} {req.minutes} 分钟"))
    db.add(Reward(user_id=req.user_id, device=req.device, minutes=req.minutes, points_cost=cost))
    db.commit()
    return {"success": True, "cost": cost}
