"""学习类接口的访问控制：孩子必须绑定家长；按角色解析可访问的目标用户。

`resolve_target_user_id`：child 仅 self；parent 可代查 parent_id 指向自己的孩子；admin 任意。
越权统一 403 ``{"error": "forbidden"}``。详见 ``docs/superpowers/plans/2026-11-06-auth-p0-rollout.md``。
"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Lesson, PdfDocument, User, UserDocument
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


def ensure_user_access(user: User, target_user_id: int, db: Session) -> None:
    """与 resolve 相同规则；不允许则 403 forbidden。"""
    if target_user_id == user.id:
        return
    if user.role == "admin":
        return
    if user.role == "parent":
        target = db.get(User, target_user_id)
        if target is not None and target.parent_id == user.id:
            return
    raise HTTPException(status_code=403, detail={"error": "forbidden"})


def require_parent_or_admin(user: User = Depends(get_current_user)) -> User:
    """家长或运营管理员（管理教材/孩子档案等）。"""
    if user.role not in ("parent", "admin"):
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    return user


def ensure_lesson_document_access(actor: User, lesson_id: int, db: Session) -> Lesson:
    """教材课：仅当孩子已绑定该课的 PDF 文档时可见；家长需存在任一已绑定的孩子；admin 放行。"""
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="课程不存在")
    doc_id = lesson.document_id
    if actor.role == "admin":
        return lesson
    if actor.role == "child":
        bound = (
            db.query(UserDocument)
            .filter_by(user_id=actor.id, document_id=doc_id)
            .first()
        )
        if not bound:
            raise HTTPException(status_code=403, detail={"error": "forbidden"})
        return lesson
    if actor.role == "parent":
        kid_ids = [
            r[0]
            for r in db.query(User.id).filter_by(parent_id=actor.id, role="child").all()
        ]
        if not kid_ids:
            raise HTTPException(status_code=403, detail={"error": "forbidden"})
        ok = (
            db.query(UserDocument)
            .filter(
                UserDocument.document_id == doc_id,
                UserDocument.user_id.in_(kid_ids),
            )
            .first()
        )
        if not ok:
            raise HTTPException(status_code=403, detail={"error": "forbidden"})
        return lesson
    raise HTTPException(status_code=403, detail={"error": "forbidden"})


def ensure_pdf_document_access(actor: User, document_id: int, db: Session) -> PdfDocument:
    """教材文档可读性：孩子仅当本人已绑定该 PdfDocument；家长与管理员与旧版一致（文档存在即可，便于上传后尚未绑孩子也管理课程）。"""
    doc = db.get(PdfDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="教材不存在")
    if actor.role == "admin":
        return doc
    if actor.role == "parent":
        return doc
    if actor.role == "child":
        if actor.parent_id is None:
            raise HTTPException(status_code=403, detail={"error": "parent_required"})
        bound = (
            db.query(UserDocument)
            .filter_by(user_id=actor.id, document_id=document_id)
            .first()
        )
        if not bound:
            raise HTTPException(status_code=403, detail={"error": "forbidden"})
        return doc
    raise HTTPException(status_code=403, detail={"error": "forbidden"})


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
    if user_id is None:
        return user.id
    ensure_user_access(user, user_id, db)
    return user_id
