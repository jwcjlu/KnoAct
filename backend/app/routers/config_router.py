from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import ModelConfig

router = APIRouter(prefix="/api/config", tags=["config"])

class ConfigReq(BaseModel):
    key: str
    value: str

@router.post("")
def set_config(req: ConfigReq, db: Session = Depends(get_db)):
    row = db.query(ModelConfig).filter_by(key=req.key).first()
    if row:
        row.value = req.value
    else:
        db.add(ModelConfig(key=req.key, value=req.value))
    db.commit()
    return {"ok": True}

@router.get("")
def get_config(db: Session = Depends(get_db)):
    return {r.key: r.value for r in db.query(ModelConfig).all()}
