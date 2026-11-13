from app.services.drill_rule import generate_group_content


def test_fake_returns_empty_structures(db):
    items = [{"primary": "床前明月光", "secondary": "李白"}]
    r = generate_group_content(db, "语文", "outline", items)
    assert r["intro"] == {"situation": "", "goal": "", "route": ""}
    assert r["group_rule"] == {"examples": [], "question": "", "reveal": ""}
    assert r["common_mistakes"] == {}


def test_structure_keys_present(db):
    items = [{"primary": "x", "secondary": "y"}]
    r = generate_group_content(db, "英语", "phrase", items)
    assert set(r.keys()) >= {"intro", "group_rule", "common_mistakes"}


def test_none_db_returns_empty():
    r = generate_group_content(None, "语文", "outline", [{"primary": "a", "secondary": "b"}])
    assert r["group_rule"]["reveal"] == ""
