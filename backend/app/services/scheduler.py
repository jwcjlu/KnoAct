from datetime import datetime, timedelta

# 艾宾浩斯遗忘曲线复习间隔（天）：第 n 次复习后的间隔
INTERVALS = [1, 2, 4, 7, 15, 30, 60]

def next_review_after(correct_streak: int, now: datetime) -> datetime:
    """根据连续答对次数（streak）返回下次复习时间。streak 越界取最后一档。"""
    idx = min(correct_streak, len(INTERVALS) - 1)
    return now + timedelta(days=INTERVALS[idx])

def select_words(words: list[dict], limit: int, now: datetime | None = None) -> list[dict]:
    """从词列表中按「到期复习 > 薄弱加权 > 原顺序」排序，取前 limit 个。
    words 每项需含 id / mistake_count / next_review_at（可为 None）。"""
    now = now or datetime.utcnow()
    def key(w):
        due = 0
        if w.get("next_review_at") and w["next_review_at"] <= now:
            due = 1  # 到期优先
        # 薄弱：错得多排前面
        return (-due, -w.get("mistake_count", 0))
    ordered = sorted(words, key=key)
    return ordered[:limit]
