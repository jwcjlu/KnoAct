from app.services.drill_review import review_group_items


def test_review_fake_returns_empty(db):
    r = review_group_items(db, "英语", "phrase", [{"primary": "look after", "secondary": "照顾"}])
    assert r == []


def test_review_none_db_returns_empty():
    r = review_group_items(None, "英语", "phrase", [{"primary": "look after"}])
    assert r == []


def test_review_empty_items_returns_empty(db):
    r = review_group_items(db, "英语", "phrase", [])
    assert r == []
