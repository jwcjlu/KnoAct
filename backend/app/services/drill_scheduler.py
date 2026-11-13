"""专项训练 SRS 间隔重复。"""
from datetime import datetime, timedelta


def next_review_at_after(interval: int, now: datetime | None = None) -> datetime:
    return (now or datetime.utcnow()) + timedelta(days=interval)


def grade(interval: int, hinted: bool, correct: bool, max_days: int = 60) -> tuple[int, int, bool]:
    """返回 (new_interval, new_lapse_delta, new_last_hinted)。

    - 答错：interval 重置 1 天，lapse 增量 1，last_hinted=False
    - 答对且有提示：interval 不变，lapse 增量 0，last_hinted=True
    - 答对且无提示：interval 翻倍（封顶 max_days），lapse 增量 0，last_hinted=False
    """
    if not correct:
        return 1, 1, False
    if hinted:
        return interval, 0, True
    return min(interval * 2, max_days), 0, False


def is_mastered(interval: int, hinted: bool, mastery_interval_days: int) -> bool:
    """真掌握：间隔达到门槛 且 最近一次通过无提示。"""
    return interval >= mastery_interval_days and not hinted
