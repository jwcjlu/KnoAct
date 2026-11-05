from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.deps import require_role
from ..database import get_db
from ..models import User

router = APIRouter(prefix="/api/users", tags=["users"])

# 孩子档案端点：挂在 /api/children 下（前端/测试直接调用此路径）。
children_router = APIRouter(prefix="/api/children", tags=["children"])


@router.get("")
def list_users(role: str | None = None, parent_id: int | None = None,
               include_archived: int = 0, db: Session = Depends(get_db)):
    """用户列表（家长端选择孩子用）：可按 role / parent_id 过滤，按 id 升序。"""
    q = db.query(User)
    if role:
        q = q.filter_by(role=role)
    if parent_id is not None:
        q = q.filter_by(parent_id=parent_id)
    if not include_archived:
        q = q.filter(User.status != "archived")
    return [{"id": u.id, "name": u.name, "role": u.role, "grade": u.grade, "edition": u.edition, "status": u.status}
            for u in q.order_by(User.id).all()]


class CreateChildReq(BaseModel):
    parent_id: int
    name: str
    grade: int
    edition: str = ""


@children_router.post("")
def create_child(req: CreateChildReq, user: User = Depends(require_role("parent")),
                 db: Session = Depends(get_db)):
    from ..services.bucket_service import ensure_bucket
    if req.parent_id != user.id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    child = User(name=req.name, role="child", grade=req.grade,
                 edition=req.edition, parent_id=req.parent_id)
    db.add(child); db.commit(); db.refresh(child)
    ensure_bucket(db, child.id)
    return {"id": child.id, "name": child.name, "role": child.role,
            "grade": child.grade, "edition": child.edition}


@children_router.post("/{child_id}/promote")
def promote_child(child_id: int, db: Session = Depends(get_db)):
    from ..services.bucket_service import promote_grade
    promote_grade(db, child_id)
    child = db.get(User, child_id)
    return {"id": child.id, "grade": child.grade}


class UpdateChildReq(BaseModel):
    name: str | None = None
    grade: int | None = None
    edition: str | None = None


@children_router.put("/{child_id}")
def update_child(child_id: int, req: UpdateChildReq, db: Session = Depends(get_db)):
    child = db.get(User, child_id)
    if not child:
        return {"error": "not found"}
    if req.name is not None:
        child.name = req.name
    if req.edition is not None:
        child.edition = req.edition
    if req.grade is not None:
        child.grade = req.grade
        db.commit()
        from ..services.bucket_service import ensure_bucket
        ensure_bucket(db, child_id)
    db.commit()
    db.refresh(child)
    return {"id": child.id, "name": child.name, "grade": child.grade, "edition": child.edition}


@children_router.post("/{child_id}/archive")
def archive_child(child_id: int, db: Session = Depends(get_db)):
    child = db.get(User, child_id)
    if not child:
        return {"error": "not found"}
    child.status = "archived"
    db.commit()
    return {"ok": True}


@children_router.post("/{child_id}/unarchive")
def unarchive_child(child_id: int, db: Session = Depends(get_db)):
    child = db.get(User, child_id)
    if not child:
        return {"error": "not found"}
    child.status = "active"
    db.commit()
    return {"ok": True}


@children_router.get("/{child_id}/documents")
def child_documents(child_id: int, db: Session = Depends(get_db)):
    from ..models import UserDocument, PdfDocument
    bound = db.query(UserDocument.document_id).filter_by(user_id=child_id)
    docs = db.query(PdfDocument).filter(PdfDocument.id.in_(bound)).all()
    return {"documents": [
        {"id": d.id, "filename": d.filename, "subject": d.subject,
         "grade": d.grade, "edition": d.edition}
        for d in docs
    ]}
