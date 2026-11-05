"""学习类接口的访问控制：孩子必须绑定家长；按角色解析可访问的目标用户。"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from .deps import get_current_user


def child_has_parent(user: User) -> bool:
    """孩子账号是否已绑定家长（非孩子角色视为 False）。"""
    return user.role == "child" and user.parent_id is not None


def require_learning_access(user: User) -> None:
    """未绑定家长的孩子不得使用学习功能 → 403 parent_required。家长 / 管理员放行。"""
    if user.role == "child" and user.parent_id is None:
        raise HTTPException(status_code=403, detail={"error": "parent_required"})


def require_learning_user(user: User = Depends(get_current_user)) -> User:
    """FastAPI 依赖：get_current_user + 孩子必须已绑定家长。"""
    require_learning_access(user)
    return user


def resolve_target_user_id(
    user_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> int:
    """解析本次请求实际操作的用户 id（query 参数 user_id）。

    - child：只能是自己（缺省为自己）
    - parent：自己，或 parent_id 指向自己的孩子
    - admin：任意
    越权 → 403 forbidden。
    """
    if user_id is None or user_id == user.id:
        return user.id
    if user.role == "admin":
        return user_id
    if user.role == "parent":
        target = db.get(User, user_id)
        if target is not None and target.parent_id == user.id:
            return user_id
    raise HTTPException(status_code=403, detail={"error": "forbidden"})
