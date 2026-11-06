"""管理员用户管理：搜索 / 创建 / 编辑 / 重置密码 / 归档。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access
from ..core.deps import get_current_user, require_role
from ..database import get_db
from ..models import RefreshToken, User
from ..services.bucket_service import ensure_bucket
from ..services.security import hash_password
from ..services.user_factory import (
    DuplicateLoginName, UserFactoryError, create_child_user, create_user,
    validate_password,
)

router = APIRouter(
    prefix="/api/admin", tags=["admin"],
    dependencies=[Depends(require_role("admin"))],
)

CREATABLE_ROLES = ("child", "parent")


def _err(status: int, code: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": code})


def _out(u: User) -> dict:
    return {
        "id": u.id, "login_name": u.login_name, "name": u.name,
        "display_name": u.display_name, "role": u.role, "grade": u.grade,
        "edition": u.edition, "parent_id": u.parent_id, "phone": u.phone,
        "email": u.email, "status": u.status,
    }


def _check_parent(db: Session, parent_id: int) -> None:
    p = db.get(User, parent_id)
    if p is None or p.role != "parent":
        raise _err(400, "invalid_parent")


def _get_user(db: Session, user_id: int) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise _err(404, "user_not_found")
    return u


@router.get("/users")
def list_users(role: str | None = None, q: str | None = None,
               db: Session = Depends(get_db)):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            User.login_name.like(like), User.display_name.like(like),
            User.phone.like(like),
        ))
    return [_out(u) for u in query.order_by(User.id).all()]


class CreateUserReq(BaseModel):
    login_name: str
    password: str
    role: str
    parent_id: int | None = None
    display_name: str = ""
    grade: int | None = None
    edition: str = ""
    phone: str = ""


@router.post("/users")
def create_user_api(req: CreateUserReq, db: Session = Depends(get_db)):
    if req.role not in CREATABLE_ROLES:
        raise _err(400, "invalid_role")
    if req.parent_id is not None:
        if req.role != "child":
            raise _err(400, "invalid_parent")
        _check_parent(db, req.parent_id)
    profile = {"display_name": req.display_name, "edition": req.edition,
               "phone": req.phone}
    if req.grade is not None:
        profile["grade"] = req.grade
    if req.parent_id is not None:
        profile["parent_id"] = req.parent_id
    try:
        if req.role == "child":
            user = create_child_user(db, req.login_name, req.password, **profile)
        else:
            user = create_user(db, req.login_name, req.password, "parent", **profile)
    except DuplicateLoginName as e:
        raise _err(409, str(e.args[0]))
    except UserFactoryError as e:
        raise _err(400, str(e.args[0]))
    return _out(user)


class PatchUserReq(BaseModel):
    display_name: str | None = None
    grade: int | None = None
    edition: str | None = None
    phone: str | None = None
    email: str | None = None
    gender: str | None = None
    birth_month: str | None = None
    interests: str | None = None
    parent_id: int | None = None


@router.patch("/users/{user_id}")
def patch_user(user_id: int, req: PatchUserReq, db: Session = Depends(get_db)):
    user = _get_user(db, user_id)
    fields = req.model_dump(exclude_unset=True)
    if "parent_id" in fields:
        pid = fields["parent_id"]
        if pid is not None:
            if user.role != "child":
                raise _err(400, "invalid_parent")
            _check_parent(db, pid)
        user.parent_id = pid
    for key in ("display_name", "grade", "edition", "phone", "email",
                "gender", "birth_month", "interests"):
        if key in fields and fields[key] is not None:
            setattr(user, key, fields[key])
    if fields.get("display_name"):
        user.name = fields["display_name"]
    db.commit()
    if user.role == "child" and fields.get("grade") is not None:
        ensure_bucket(db, user.id)
    db.refresh(user)
    return _out(user)


class ResetPasswordReq(BaseModel):
    password: str


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, req: ResetPasswordReq, db: Session = Depends(get_db)):
    user = _get_user(db, user_id)
    try:
        validate_password(req.password)
    except UserFactoryError as e:
        raise _err(400, str(e.args[0]))
    user.password_hash = hash_password(req.password)
    db.query(RefreshToken).filter_by(user_id=user.id, revoked=False).update({"revoked": True})
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/archive")
def archive(user_id: int, db: Session = Depends(get_db),
            actor: User = Depends(get_current_user)):
    """不能直接调 ``users.archive_child``：其签名为 FastAPI 依赖，位置传参会错位。"""
    if actor.role != "admin":
        raise _err(403, "forbidden")
    _get_user(db, user_id)
    child = db.get(User, user_id)
    if not child:
        return {"error": "not found"}
    ensure_user_access(actor, user_id, db)
    child.status = "archived"
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/unarchive")
def unarchive(user_id: int, db: Session = Depends(get_db),
              actor: User = Depends(get_current_user)):
    if actor.role != "admin":
        raise _err(403, "forbidden")
    _get_user(db, user_id)
    child = db.get(User, user_id)
    if not child:
        return {"error": "not found"}
    ensure_user_access(actor, user_id, db)
    child.status = "active"
    db.commit()
    return {"ok": True}
