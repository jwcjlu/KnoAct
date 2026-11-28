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


import io
import wave


def _pcm_wav(pcm: bytes, *, rate=24000, channels=1, sampwidth=2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def test_merge_wav_segments():
    from app.services.qwen_tts import merge_audio_segments

    a = _pcm_wav(b"\x00\x01" * 100)
    b = _pcm_wav(b"\x02\x03" * 50)
    merged = merge_audio_segments([a, b])
    assert merged[:4] == b"RIFF"
    with wave.open(io.BytesIO(merged), "rb") as w:
        assert w.getnframes() == 100 + 50


def test_merge_single_passthrough():
    from app.services.qwen_tts import merge_audio_segments

    a = _pcm_wav(b"\x00\x01" * 10)
    assert merge_audio_segments([a]) == a


def test_merge_fmt_mismatch_raises():
    from app.services.qwen_tts import merge_audio_segments

    a = _pcm_wav(b"\x00\x01" * 10, rate=24000)
    b = _pcm_wav(b"\x00\x01" * 10, rate=16000)
    try:
        merge_audio_segments([a, b])
        assert False, "应因 fmt 不一致失败"
    except RuntimeError:
        pass