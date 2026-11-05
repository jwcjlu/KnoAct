"""用户创建工厂：校验登录名/密码，统一落库逻辑。"""
import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import User
from .bucket_service import ensure_bucket
from .security import hash_password

_LOGIN_NAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")

PROFILE_FIELDS = (
    "display_name", "birth_month", "gender", "interests",
    "grade", "edition", "parent_id", "phone", "email",
)


class UserFactoryError(ValueError):
    """校验失败；args[0] 为错误码。"""


class DuplicateLoginName(UserFactoryError):
    pass


def validate_login_name(login_name: str) -> str:
    if not isinstance(login_name, str) or not _LOGIN_NAME_RE.match(login_name):
        raise UserFactoryError("invalid_login_name")
    return login_name


def validate_password(password: str) -> str:
    if (
        not isinstance(password, str)
        or len(password) < 8
        or not re.search(r"[A-Za-z]", password)
        or not re.search(r"\d", password)
    ):
        raise UserFactoryError("weak_password")
    return password


def create_user(db: Session, login_name: str, password: str, role: str, **profile) -> User:
    """创建用户并提交。name 兼容旧字段：display_name 或 login_name。"""
    validate_login_name(login_name)
    validate_password(password)
    unknown = set(profile) - set(PROFILE_FIELDS)
    if unknown:
        raise TypeError(f"unknown profile fields: {sorted(unknown)}")
    if db.query(User).filter_by(login_name=login_name).first():
        raise DuplicateLoginName("login_name_taken")
    display_name = profile.pop("display_name", "") or ""
    user = User(
        login_name=login_name,
        password_hash=hash_password(password),
        role=role,
        name=display_name or login_name,
        display_name=display_name,
        **profile,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateLoginName("login_name_taken")
    db.refresh(user)
    return user


def create_child_user(db: Session, login_name: str, password: str, **profile) -> User:
    user = create_user(db, login_name, password, "child", **profile)
    ensure_bucket(db, user.id)
    db.commit()
    db.refresh(user)
    return user
