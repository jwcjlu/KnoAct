"""账号认证：注册 / 密码登录 / 短信 OTP / 重置密码 / 个人资料。"""
import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..database import get_db
from ..models import OtpCode, RefreshToken, User
from ..services.otp import issue_otp, verify_otp
from ..services.security import create_access_token, hash_password, verify_password
from ..services.user_factory import (
    DuplicateLoginName,
    UserFactoryError,
    create_child_user,
    create_user,
    validate_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_TTL = timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", "30")))
_BIRTH_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_PHONE_RE = re.compile(r"^\+?\d{6,20}$")
_GENDERS = {"male", "female", "unknown"}


# ---------- helpers ----------

def _legacy_enabled() -> bool:
    return os.environ.get("KNOACT_LEGACY_NAME_LOGIN") == "1"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_tokens(db: Session, user: User) -> dict:
    access = create_access_token({"sub": str(user.id), "role": user.role})
    refresh = secrets.token_urlsafe(32)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(refresh),
        expires_at=datetime.utcnow() + REFRESH_TTL,
    ))
    db.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": _user_out(user),
    }


def _user_out(user: User) -> dict:
    return {
        "id": user.id,
        "login_name": user.login_name,
        "name": user.name,
        "display_name": user.display_name or user.name,
        "role": user.role,
        "grade": user.grade,
        "edition": user.edition or "",
        "birth_month": user.birth_month,
        "gender": user.gender or "unknown",
        "interests": user.interests or "",
        "phone": user.phone or "",
        "phone_verified": bool(user.phone_verified),
        "email": user.email or "",
        "email_verified": bool(user.email_verified),
        "parent_bound": user.role == "child" and user.parent_id is not None,
    }


def _bad_request(code: str, status: int = 400):
    return HTTPException(status_code=status, detail={"error": code})


def _find_active(db: Session, login_name: str) -> User | None:
    return db.query(User).filter_by(login_name=login_name).first()


def _check_status(user: User):
    if user.status == "archived":
        raise HTTPException(status_code=403, detail={"error": "archived"})


def _clear_otps(db: Session, user_id: int, purpose: str):
    db.query(OtpCode).filter_by(user_id=user_id, purpose=purpose).delete()
    db.commit()


# ---------- schemas ----------

class RegisterReq(BaseModel):
    login_name: str
    password: str
    role: Literal["child", "parent"] = "child"


class LoginReq(BaseModel):
    login_name: str | None = None
    password: str | None = None
    # 旧版 student-app Web 仅传 name；见 login() 兼容逻辑
    name: str | None = None
    role: str = "child"


class OtpSendReq(BaseModel):
    login_name: str
    purpose: Literal["login", "reset_password"] = "login"


class OtpLoginReq(BaseModel):
    login_name: str
    code: str


class PasswordResetReq(BaseModel):
    login_name: str
    code: str
    new_password: str


class RefreshReq(BaseModel):
    refresh_token: str


class ProfileReq(BaseModel):
    display_name: str | None = None
    birth_month: str | None = None
    gender: str | None = None
    interests: str | list[str] | None = None
    grade: int | None = None
    edition: str | None = None


class CredentialsReq(BaseModel):
    old_password: str | None = None
    new_password: str | None = None
    phone: str | None = None
    code: str | None = None


class PhoneSendReq(BaseModel):
    phone: str


# ---------- endpoints ----------

@router.post("/register")
def register(req: RegisterReq, db: Session = Depends(get_db)):
    if req.role not in ("child", "parent"):
        raise _bad_request("invalid_role")
    try:
        if req.role == "child":
            user = create_child_user(db, req.login_name, req.password)
        else:
            user = create_user(db, req.login_name, req.password, "parent")
    except DuplicateLoginName:
        raise _bad_request("login_name_taken", 409)
    except UserFactoryError as e:
        raise _bad_request(str(e.args[0]))
    return _issue_tokens(db, user)


def _normalize_login_req(req: LoginReq) -> LoginReq:
    """旧 Web 包只传 name → 映射 login_name，并尝试迁移默认密码。"""
    login_name = (req.login_name or req.name or "").strip()
    password = req.password
    if login_name and password is None and req.name and not req.login_name:
        password = os.environ.get("KNOACT_LEGACY_DEFAULT_PASSWORD", "ChangeMe123")
    if login_name != req.login_name or password != req.password:
        return LoginReq(login_name=login_name or None, password=password, name=req.name, role=req.role)
    return req


@router.post("/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    if _legacy_enabled() and req.name and not req.login_name:
        user = db.query(User).filter_by(name=req.name).first()
        if user:
            _check_status(user)
        else:
            user = User(name=req.name, role=req.role)
            db.add(user); db.commit(); db.refresh(user)
        return {"id": user.id, "name": user.name, "role": user.role}

    req = _normalize_login_req(req)
    if not req.login_name or req.password is None:
        raise _bad_request("invalid_credentials", 401)
    user = _find_active(db, req.login_name)
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        if req.name and not user:
            raise _bad_request("please_register", 401)
        raise _bad_request("invalid_credentials", 401)
    _check_status(user)
    return _issue_tokens(db, user)


@router.post("/otp/send")
def otp_send(req: OtpSendReq, db: Session = Depends(get_db)):
    user = _find_active(db, req.login_name)
    if not user or not user.phone or not user.phone_verified:
        raise _bad_request("phone_not_verified")
    _check_status(user)
    issue_otp(db, user.id, req.purpose)
    return {"ok": True}


@router.post("/otp/login")
def otp_login(req: OtpLoginReq, db: Session = Depends(get_db)):
    user = _find_active(db, req.login_name)
    if not user or not verify_otp(db, user.id, "login", req.code):
        raise _bad_request("invalid_code", 401)
    _check_status(user)
    _clear_otps(db, user.id, "login")
    return _issue_tokens(db, user)


@router.post("/password/reset")
def password_reset(req: PasswordResetReq, db: Session = Depends(get_db)):
    user = _find_active(db, req.login_name)
    if not user or not verify_otp(db, user.id, "reset_password", req.code):
        raise _bad_request("invalid_code", 400)
    _check_status(user)
    try:
        validate_password(req.new_password)
    except UserFactoryError as e:
        raise _bad_request(str(e.args[0]))
    user.password_hash = hash_password(req.new_password)
    # 撤销所有 refresh token
    db.query(RefreshToken).filter_by(user_id=user.id, revoked=False).update({"revoked": True})
    db.commit()
    _clear_otps(db, user.id, "reset_password")
    return {"ok": True}


@router.post("/refresh")
def refresh(req: RefreshReq, db: Session = Depends(get_db)):
    row = db.query(RefreshToken).filter_by(token_hash=_hash_token(req.refresh_token)).first()
    if not row or row.revoked or row.expires_at < datetime.utcnow():
        raise _bad_request("invalid_refresh_token", 401)
    user = db.get(User, row.user_id)
    if not user:
        raise _bad_request("invalid_refresh_token", 401)
    _check_status(user)
    row.revoked = True  # 轮换
    db.commit()
    return _issue_tokens(db, user)


@router.post("/logout")
def logout(req: RefreshReq | None = None, db: Session = Depends(get_db)):
    if req and req.refresh_token:
        row = db.query(RefreshToken).filter_by(token_hash=_hash_token(req.refresh_token)).first()
        if row:
            row.revoked = True
            db.commit()
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_out(user)


@router.patch("/me/profile")
def update_profile(req: ProfileReq, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    data = req.model_dump(exclude_unset=True)
    if "display_name" in data and data["display_name"] is not None:
        dn = data["display_name"].strip()
        if not dn or len(dn) > 64:
            raise _bad_request("invalid_display_name")
        user.display_name = dn
        user.name = dn  # 兼容旧字段
    if "birth_month" in data:
        bm = data["birth_month"]
        if bm is not None and not _BIRTH_MONTH_RE.match(bm):
            raise _bad_request("invalid_birth_month")
        user.birth_month = bm
    if data.get("gender") is not None:
        if data["gender"] not in _GENDERS:
            raise _bad_request("invalid_gender")
        user.gender = data["gender"]
    if data.get("interests") is not None:
        it = data["interests"]
        user.interests = ",".join(s.strip() for s in it if s.strip()) if isinstance(it, list) else it
    if user.role == "child":
        if data.get("grade") is not None:
            if not 1 <= data["grade"] <= 6:
                raise _bad_request("invalid_grade")
            user.grade = data["grade"]
        if data.get("edition") is not None:
            user.edition = data["edition"]
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.post("/me/phone/send")
def phone_send(req: PhoneSendReq, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """给待绑定手机号发 bind_phone 验证码（未验证前仅暂存在 user.phone）。"""
    if not _PHONE_RE.match(req.phone):
        raise _bad_request("invalid_phone")
    if user.phone_verified and user.phone != req.phone:
        raise _bad_request("phone_already_bound")
    user.phone = req.phone
    db.commit()
    issue_otp(db, user.id, "bind_phone")
    return {"ok": True}


@router.patch("/me/credentials")
def update_credentials(req: CredentialsReq, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    changed = False
    if req.new_password is not None:
        # 无密码的老用户可直接设置；否则必须校验旧密码
        if user.password_hash:
            if not req.old_password or not verify_password(req.old_password, user.password_hash):
                raise _bad_request("wrong_old_password", 403)
        try:
            validate_password(req.new_password)
        except UserFactoryError as e:
            raise _bad_request(str(e.args[0]))
        user.password_hash = hash_password(req.new_password)
        changed = True
    if req.phone is not None:
        if not _PHONE_RE.match(req.phone):
            raise _bad_request("invalid_phone")
        if not req.code or user.phone != req.phone or not verify_otp(db, user.id, "bind_phone", req.code):
            raise _bad_request("invalid_code")
        user.phone_verified = True
        _clear_otps(db, user.id, "bind_phone")
        changed = True
    if not changed:
        raise _bad_request("nothing_to_update")
    db.commit()
    db.refresh(user)
    return _user_out(user)
