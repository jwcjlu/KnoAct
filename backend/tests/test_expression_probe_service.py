"""expression_probe 纯函数：轮次、规范化、摘要门闩。"""
from unittest.mock import MagicMock

from app.services import expression_probe as ep


def test_normalize_rejects_more_than_max_turns():
    turns = [{"q": "a", "a": "b"}] * 4
    try:
        ep.normalize_probe_turns(turns)
        assert False, "应抛 ValueError"
    except ValueError as e:
        assert "max" in str(e).lower() or "3" in str(e)


def test_normalize_accepts_empty_and_trimmed():
    assert ep.normalize_probe_turns(None) == []
    assert ep.normalize_probe_turns([]) == []
    out = ep.normalize_probe_turns([{"q": " 问？ ", "a": " 答 "}])
    assert out == [{"q": "问？", "a": "答"}]


def test_ask_next_done_when_full():
    provider = MagicMock()
    r = ep.ask_next_question(
        provider, title="比喻", text="……", turns=[{"q": "1", "a": "a"},
                                                   {"q": "2", "a": "b"},
                                                   {"q": "3", "a": "c"}])
    assert r["done"] is True
    assert r.get("question") in (None, "")
    provider.generate.assert_not_called()


def test_ask_next_calls_generate_when_room():
    provider = MagicMock()
    provider.generate.return_value = "那『像』一定是比喻吗？"
    r = ep.ask_next_question(provider, title="比喻", text="比喻就是像", turns=[])
    assert r["done"] is False
    assert "像" in r["question"] or r["question"]
    provider.generate.assert_called_once()


def test_build_parent_hint_empty_without_turns():
    provider = MagicMock()
    assert ep.build_parent_hint(provider, title="x", text="y", turns=[]) == ""
    provider.generate.assert_not_called()


def test_build_parent_hint_scrubs_praise_and_truncates():
    provider = MagicMock()
    provider.generate.return_value = "讲得很好，可能卡在本体和喻体没分清"
    hint = ep.build_parent_hint(
        provider, title="比喻", text="……",
        turns=[{"q": "q", "a": "a"}])
    assert hint
    assert "很好" not in hint and "讲得" not in hint
    assert len(hint) <= ep.MAX_HINT_LEN