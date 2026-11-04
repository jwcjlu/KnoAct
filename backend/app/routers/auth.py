from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginReq(BaseModel):
    name: str
    role: str = "child"

@router.post("/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(name=req.name).first()
    if not user:
        user = User(name=req.name, role=req.role)
        db.add(user); db.commit(); db.refresh(user)
    return {"id": user.id, "name": user.name, "role": user.role}
