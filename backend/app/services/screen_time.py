"""屏幕时间：App 分组归类与超时计算（纯函数）。"""


def classify_package(db, user_id: int, app_package: str, app_name: str):
    """返回该包名应归入的 group_id；未知 App 归「娱乐类」，无娱乐组则 None。"""
    raise NotImplementedError


def compute_group_totals(db, child_id: int, date: str):
    """返回 {group_id: 总秒数}，供超时判定。"""
    raise NotImplementedError
