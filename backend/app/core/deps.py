"""FastAPI 依赖：当前登录用户（Bearer JWT）。"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..services.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """解析 Bearer JWT（sub=用户 id）。缺失/无效 → 401；已归档 → 403。"""
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail={"error": "not_authenticated"})
    try:
        payload = decode_access_token(creds.credentials)
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail={"error": "invalid_token"})
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail={"error": "invalid_token"})
    if user.status == "archived":
        raise HTTPException(status_code=403, detail={"error": "archived"})
    return user
