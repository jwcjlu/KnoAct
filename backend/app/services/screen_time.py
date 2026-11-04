"""屏幕时间：App 分组归类与超时计算（纯函数）。"""
from sqlalchemy.orm import Session
from ..models import AppGroup, AppRule, ScreenUsage


def classify_package(db: Session, user_id: int, app_package: str, app_name: str):
    """返回该包名应归入的 group_id。

    优先级：AppRule 显式映射 > 未知包归「娱乐类」> 无娱乐组则 None。
    """
    rule = (db.query(AppRule)
            .filter_by(user_id=user_id, app_package=app_package)
            .first())
    if rule:
        return rule.group_id
    fun = (db.query(AppGroup)
           .filter_by(user_id=user_id, kind="fun")
           .first())
    return fun.id if fun else None


def compute_group_totals(db: Session, child_id: int, date: str):
    """返回 {group_id: 总秒数}。未归类（group_id 为 None 且无规则）的使用时长计入娱乐组。"""
    rows = (db.query(ScreenUsage)
            .filter_by(child_id=child_id, date=date)
            .all())
    totals = {}
    for r in rows:
        gid = r.group_id if r.group_id is not None else classify_package(db, child_id, r.app_package, r.app_name)
        if gid is None:
            continue
        totals[gid] = totals.get(gid, 0) + r.duration_seconds
    return totals
