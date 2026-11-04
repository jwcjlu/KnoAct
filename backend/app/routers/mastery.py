"""精通之路：掌握度总览与记录。"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import KnowledgeMastery, KnowledgePoint
from ..services.mastery import record_attempt as _record
from ..services.bucket_guard import resolve_bucket_id

router = APIRouter(prefix="/api/mastery", tags=["mastery"])


class RecordReq(BaseModel):
    user_id: int
    target_type: str   # 'knowledge' | 'word'
    target_id: int
    is_correct: bool


@router.get("/overview")
def overview(user_id: int, subject: str = "", bucket_id: int | None = None,
             db: Session = Depends(get_db)):
    bid = resolve_bucket_id(db, user_id, bucket_id)
    q = (db.query(KnowledgeMastery, KnowledgePoint)
         .join(KnowledgePoint, KnowledgeMastery.knowledge_point_id == KnowledgePoint.id)
         .filter(KnowledgeMastery.user_id == user_id))
    if bid is not None:
        q = q.filter(KnowledgeMastery.bucket_id == bid)
    if subject:
        q = q.filter(KnowledgePoint.subject == subject)
    rows = q.all()
    return [{
        "knowledge_point_id": kp.id,
        "title": kp.content,
        "category": kp.category,
        "mastery": km.mastery,
        "mastered": km.mastered,
        "due": km.next_review_at is not None and km.next_review_at <= datetime.utcnow(),
    } for km, kp in rows]


@router.post("/record")
def record(req: RecordReq, db: Session = Depends(get_db)):
    bid = resolve_bucket_id(db, req.user_id, None)
    mastery = _record(db, req.user_id, req.target_type, req.target_id,
                      req.is_correct, bucket_id=bid)
    return {"mastery": mastery}


@router.get("/report")
def report(user_id: int, subject: str = "", bucket_id: int | None = None,
           db: Session = Depends(get_db)):
    """掌握度报告：已掌握 / 薄弱 / 总数。"""
    bid = resolve_bucket_id(db, user_id, bucket_id)
    kp_q = db.query(KnowledgePoint)
    if subject:
        kp_q = kp_q.filter(KnowledgePoint.subject == subject)
    all_kps = kp_q.all()
    total = len(all_kps)

    rows = []
    mastered = 0
    weak = 0
    for kp in all_kps:
        km = (db.query(KnowledgeMastery)
              .filter_by(user_id=user_id, knowledge_point_id=kp.id,
                         bucket_id=bid).first())
        if km is None:
            continue  # 未答过，不计入 weak
        attempts = json.loads(km.attempts or "[]")
        rows.append({
            "knowledge_point_id": kp.id,
            "title": kp.content,
            "category": kp.category,
            "mastery": km.mastery,
            "mastered": km.mastered,
            "attempts_count": len(attempts),
        })
        if km.mastered:
            mastered += 1
        else:
            weak += 1
    rows.sort(key=lambda r: r["mastery"])
    return {"mastered": mastered, "weak": weak, "total": total, "rows": rows}
