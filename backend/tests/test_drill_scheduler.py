from app.services.drill_scheduler import grade, is_mastered, next_review_at_after


def test_correct_no_hint_doubles():
    ni, lapse, hinted = grade(1, False, True, 60)
    assert (ni, lapse, hinted) == (2, 0, False)


def test_correct_with_hint_keeps_and_flags():
    ni, lapse, hinted = grade(4, True, True, 60)
    assert (ni, lapse, hinted) == (4, 0, True)


def test_wrong_resets_and_increments_lapse():
    ni, lapse, hinted = grade(15, False, False, 60)
    assert (ni, lapse, hinted) == (1, 1, False)


def test_capped_at_max():
    ni, _, _ = grade(30, False, True, 60)
    assert ni == 60


def test_is_mastered_threshold_and_hint():
    assert is_mastered(15, False, 15) is True
    assert is_mastered(7, False, 15) is False
    assert is_mastered(15, True, 15) is False
    assert is_mastered(7, False, 7) is True


def test_next_review_at_after_days():
    from datetime import datetime
    now = datetime(2026, 11, 13, 10, 0, 0)
    assert next_review_at_after(2, now) == datetime(2026, 11, 15, 10, 0, 0)
