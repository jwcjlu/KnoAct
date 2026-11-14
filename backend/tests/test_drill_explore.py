from app.services.drill_rule import generate_explore_items, classify_items


def test_generate_explore_fake_returns_empty(db):
    r = generate_explore_items(db, [{"primary": "周长", "secondary": "绕一圈的长度"}])
    assert r == {}


def test_generate_explore_none_db():
    r = generate_explore_items(None, [{"primary": "周长"}])
    assert r == {}


def test_generate_explore_empty_items(db):
    r = generate_explore_items(db, [])
    assert r == {}


def test_classify_items_fake_returns_empty(db):
    r = classify_items(db, "语文", [{"primary": "床前明月光"}])
    assert r == {}


def test_classify_items_none_db():
    r = classify_items(None, "语文", [{"primary": "床前明月光"}])
    assert r == {}


def test_classify_items_empty(db):
    r = classify_items(db, "语文", [])
    assert r == {}


def test_generate_explore_guide_structure(db, monkeypatch):
    """非 fake 时返回 guide 键（前选择后填空），无 compare/formula。"""
    from app.services import ai, drill_rule

    class FakeP:
        name = "openai"
        def generate(self, prompt, system="", json_mode=False):
            import json as _j
            return _j.dumps({"items": [{
                "primary": "比喻",
                "guide": [
                    {"prompt": "共同点？", "samples": ["月亮像小船"],
                     "options": ["都有像", "都写月亮"], "answer_index": 0,
                     "reveal": "对，都有像。"},
                    {"prompt": "总结：比喻=本体+比喻词+___", "answer": "喻体", "reveal": "太棒了"}
                ],
                "classify": {"items": ["a"], "boxes": ["比喻"], "answers": {"a": "比喻"}},
                "trap": {"question": "q", "answer": "a", "explain": "e"},
            }]})
    monkeypatch.setattr(ai, "get_provider", lambda db: FakeP())
    r = drill_rule.generate_explore_items(db, [{"primary": "比喻", "secondary": "x"}])
    assert "比喻" in r
    assert "guide" in r["比喻"]
    assert len(r["比喻"]["guide"]) == 2
    assert "options" not in r["比喻"]["guide"][1]  # 最后一轮是填空
    assert r["比喻"]["guide"][1]["answer"] == "喻体"
    assert "compare" not in r["比喻"]
    assert "formula" not in r["比喻"]
