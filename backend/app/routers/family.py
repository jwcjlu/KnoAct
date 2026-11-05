"""家庭绑定：家长邀请码 / 孩子绑定 / 孩子申请 + 家长审批 / 解绑。"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..database import get_db
from ..models import FamilyBindRequest, FamilyInvite, User

router = APIRouter(prefix="/api/family", tags=["family"])

INVITE_TTL = timedelta(hours=24)
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉易混淆字符


def _err(status: int, code: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": code})


def _require_role(user: User, role: str) -> None:
    if user.role != role:
        raise _err(403, "forbidden")


def _new_code(db: Session) -> str:
    for _ in range(10):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        if not db.query(FamilyInvite).filter_by(code=code).first():
            return code
    raise _err(500, "code_generation_failed")


class BindReq(BaseModel):
    code: str


class RequestReq(BaseModel):
    parent_login_name: str


class UnbindReq(BaseModel):
    child_id: int


@router.post("/invite")
def create_invite(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_role(user, "parent")
    inv = FamilyInvite(parent_id=user.id, code=_new_code(db),
                       expires_at=datetime.utcnow() + INVITE_TTL)
    db.add(inv)
    db.commit()
    return {"code": inv.code, "expires_at": inv.expires_at.isoformat()}


@router.post("/bind")
def bind(req: BindReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_role(user, "child")
    inv = db.query(FamilyInvite).filter_by(code=req.code.strip().upper()).first()
    if inv is None:
        raise _err(404, "invalid_code")
    if inv.used_by_child_id is not None:
        raise _err(409, "code_used")
    if inv.expires_at < datetime.utcnow():
        raise _err(400, "code_expired")
    if user.parent_id is not None:
        raise _err(409, "already_bound")
    user.parent_id = inv.parent_id
    inv.used_by_child_id = user.id
    db.commit()
    return {"ok": True, "parent_id": user.parent_id}


@router.post("/request")
def request_bind(req: RequestReq, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _require_role(user, "child")
    if user.parent_id is not None:
        raise _err(409, "already_bound")
    parent = db.query(User).filter_by(login_name=req.parent_login_name, role="parent").first()
    if parent is None or parent.status == "archived":
        raise _err(404, "parent_not_found")
    existing = db.query(FamilyBindRequest).filter_by(
        child_id=user.id, parent_id=parent.id, status="pending").first()
    if existing is not None:
        return {"id": existing.id, "status": existing.status}
    row = FamilyBindRequest(child_id=user.id, parent_id=parent.id, status="pending")
    db.add(row)
    db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/requests")
def list_requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_role(user, "parent")
    rows = (db.query(FamilyBindRequest)
            .filter_by(parent_id=user.id, status="pending")
            .order_by(FamilyBindRequest.id).all())
    out = []
    for r in rows:
        child = db.get(User, r.child_id)
        out.append({
            "id": r.id,
            "child_id": r.child_id,
            "child_login_name": child.login_name if child else None,
            "child_name": (child.display_name or child.name) if child else "",
            "status": r.status,
        })
    return out


def _get_pending(db: Session, user: User, request_id: int) -> FamilyBindRequest:
    _require_role(user, "parent")
    row = db.get(FamilyBindRequest, request_id)
    if row is None or row.parent_id != user.id:
        raise _err(404, "request_not_found")
    if row.status != "pending":
        raise _err(409, "request_not_pending")
    return row


@router.post("/requests/{request_id}/approve")
def approve_request(request_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    row = _get_pending(db, user, request_id)
    child = db.get(User, row.child_id)
    if child is None or child.role != "child":
        raise _err(404, "request_not_found")
    if child.parent_id is not None and child.parent_id != user.id:
        raise _err(409, "already_bound")
    child.parent_id = user.id
    row.status = "approved"
    db.commit()
    return {"ok": True, "status": "approved"}


@router.post("/requests/{request_id}/reject")
def reject_request(request_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    row = _get_pending(db, user, request_id)
    row.status = "rejected"
    db.commit()
    return {"ok": True, "status": "rejected"}


@router.post("/unbind")
def unbind(req: UnbindReq, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    _require_role(user, "parent")
    child = db.get(User, req.child_id)
    if child is None or child.parent_id != user.id:
        raise _err(404, "child_not_found")
    child.parent_id = None
    db.commit()
    return {"ok": True}
