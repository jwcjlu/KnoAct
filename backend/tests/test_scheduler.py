from datetime import datetime, timedelta
from app.services.scheduler import next_review_after, select_words


def test_next_review_first_learning():
    now = datetime(2026, 10, 24, 10, 0, 0)
    nxt = next_review_after(correct_streak=0, now=now)
    assert nxt == now + timedelta(days=1)


def test_next_review_interval_grows():
    now = datetime(2026, 10, 24, 10, 0, 0)
    intervals = [1, 2, 4, 7, 15, 30, 60]
    for streak, days in enumerate(intervals):
        nxt = next_review_after(correct_streak=streak, now=now)
        assert nxt == now + timedelta(days=days)


def test_select_words_weakness_priority():
    words = [
        {"id": 1, "word": "徘徊", "mistake_count": 3, "next_review_at": None},
        {"id": 2, "word": "矗立", "mistake_count": 0, "next_review_at": None},
        {"id": 3, "word": "拟人", "mistake_count": 5, "next_review_at": None},
    ]
    picked = select_words(words, limit=2)
    assert picked[0]["id"] == 3
    assert picked[1]["id"] == 1


def test_select_words_due_review_first():
    now = datetime(2026, 10, 24)
    words = [
        {"id": 1, "word": "a", "mistake_count": 0, "next_review_at": now - timedelta(days=1)},
        {"id": 2, "word": "b", "mistake_count": 0, "next_review_at": now + timedelta(days=5)},
    ]
    picked = select_words(words, limit=1)
    assert picked[0]["id"] == 1
