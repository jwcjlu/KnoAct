from app.services.drill_rule import generate_explore_items


def test_generate_explore_fake_returns_empty(db):
    r = generate_explore_items(db, [{"primary": "周长", "secondary": "绕一圈的长度"}])
    assert r == {}


def test_generate_explore_none_db():
    r = generate_explore_items(None, [{"primary": "周长"}])
    assert r == {}


def test_generate_explore_empty_items(db):
    r = generate_explore_items(db, [])
    assert r == {}
