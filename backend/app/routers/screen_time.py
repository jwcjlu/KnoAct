"""屏幕时间：上报、分组/规则管理、使用情况查询。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AppGroup, AppRule, ScreenUsage
from ..services.screen_time import classify_package, compute_group_totals

router = APIRouter(prefix="/api/screen-time", tags=["screen-time"])


class UsageItem(BaseModel):
    app_package: str
    app_name: str = ""
    duration_seconds: int = 0


class ReportReq(BaseModel):
    child_id: int
    date: str
    items: list[UsageItem]


class GroupIn(BaseModel):
    id: int | None = None
    name: str
    kind: str = "custom"
    daily_limit_seconds: int | None = None


class RuleIn(BaseModel):
    app_package: str
    app_name: str = ""
    group_name: str  # 按组名关联，避免前端先知道 group_id


class GroupsReq(BaseModel):
    user_id: int
    groups: list[GroupIn]
    rules: list[RuleIn] = []


@router.post("/report")
def report(req: ReportReq, db: Session = Depends(get_db)):
    for it in req.items:
        row = (db.query(ScreenUsage)
               .filter_by(child_id=req.child_id, date=req.date, app_package=it.app_package)
               .first())
        if row:
            row.duration_seconds += it.duration_seconds
            if it.app_name:
                row.app_name = it.app_name
        else:
            gid = classify_package(db, req.child_id, it.app_package, it.app_name)
            db.add(ScreenUsage(child_id=req.child_id, date=req.date,
                               app_package=it.app_package, app_name=it.app_name,
                               duration_seconds=it.duration_seconds, group_id=gid))
    db.commit()
    return {"ok": True}


@router.get("/groups")
def get_groups(user_id: int, db: Session = Depends(get_db)):
    groups = [{"id": g.id, "name": g.name, "kind": g.kind,
               "daily_limit_seconds": g.daily_limit_seconds}
              for g in db.query(AppGroup).filter_by(user_id=user_id).all()]
    rules = [{"app_package": r.app_package, "app_name": r.app_name, "group_id": r.group_id}
             for r in db.query(AppRule).filter_by(user_id=user_id).all()]
    return {"groups": groups, "rules": rules}


@router.put("/groups")
def put_groups(req: GroupsReq, db: Session = Depends(get_db)):
    # 按名字 upsert 分组，记录 name -> id 映射
    name_to_id = {}
    for g in req.groups:
        row = (db.query(AppGroup)
               .filter_by(user_id=req.user_id, name=g.name).first())
        if row:
            row.kind = g.kind
            row.daily_limit_seconds = g.daily_limit_seconds
        else:
            row = AppGroup(user_id=req.user_id, name=g.name, kind=g.kind,
                           daily_limit_seconds=g.daily_limit_seconds)
            db.add(row); db.flush()
        name_to_id[g.name] = row.id
    for r in req.rules:
        gid = name_to_id.get(r.group_name)
        if gid is None:
            continue
        rule = (db.query(AppRule)
                .filter_by(user_id=req.user_id, app_package=r.app_package).first())
        if rule:
            rule.group_id = gid
            rule.app_name = r.app_name
        else:
            db.add(AppRule(user_id=req.user_id, app_package=r.app_package,
                           app_name=r.app_name, group_id=gid))
    db.commit()
    return {"ok": True}


@router.get("/usage")
def usage(child_id: int, date: str, db: Session = Depends(get_db)):
    totals = compute_group_totals(db, child_id, date)
    groups = db.query(AppGroup).filter_by(user_id=child_id).all()
    out = []
    for g in groups:
        secs = totals.get(g.id, 0)
        limit = g.daily_limit_seconds
        overtime = (limit is not None) and (secs > limit)
        out.append({"group_id": g.id, "name": g.name, "kind": g.kind,
                    "duration_seconds": secs,
                    "daily_limit_seconds": limit, "overtime": overtime})
    return {"date": date, "groups": out}
