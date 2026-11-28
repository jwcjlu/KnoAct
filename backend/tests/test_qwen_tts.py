from app.services.provider_registry import REGISTRY, find
from app.services.qwen_tts import map_language_type, split_for_qwen, _MAX_CHARS


def test_qwen_in_tts_not_in_llm():
    ids = {s.id for s in REGISTRY["tts"]}
    assert "qwen" in ids
    assert "qwen" not in {s.id for s in REGISTRY["llm"]}
    spec = find("qwen", "tts")
    assert spec.id == "qwen"
    assert spec.default_model == "qwen3-tts-flash"
    assert spec.needs_base_url is False


def test_map_language_type():
    # tts_lang_for_text：含汉字→zh，否则 en；故数字/英文都映射为 English（Auto 仅作兜底，当前不可达）
    assert map_language_type("箩") == "Chinese"
    assert map_language_type("hello") == "English"
    assert map_language_type("123") == "English"


def test_split_short_unchanged():
    assert split_for_qwen("今天学习小数") == ["今天学习小数"]


def test_split_long_by_sentence_and_hard_cut():
    sentence = "同学们好，我们开始上课。"  # 12 字
    text = sentence * 60  # 720 字
    parts = split_for_qwen(text)
    assert len(parts) > 1
    assert all(len(p) <= _MAX_CHARS for p in parts)
    assert "".join(parts) == text

    long_one = "啊" * 650
    parts2 = split_for_qwen(long_one)
    assert len(parts2) == 2
    assert len(parts2[0]) == 600
    assert "".join(parts2) == long_one