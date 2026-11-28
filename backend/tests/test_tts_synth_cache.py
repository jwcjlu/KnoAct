import os
from app.services import tts as tts_mod


def test_synth_cache_path_stable_and_sensitive(tmp_path, monkeypatch):
    monkeypatch.setattr(tts_mod, "_SYNTH_CACHE_DIR", str(tmp_path / "synth"))
    a = tts_mod._synth_cache_path("qwen", "qwen3-tts-flash", "Cherry", 1.0, "你好")
    b = tts_mod._synth_cache_path("qwen", "qwen3-tts-flash", "Cherry", 1.0, "你好")
    assert a == b
    assert "qwen_" in os.path.basename(a)
    # speed / voice / provider / model / text 任一不同 → 路径不同
    assert a != tts_mod._synth_cache_path("qwen", "qwen3-tts-flash", "Cherry", 1.2, "你好")
    assert a != tts_mod._synth_cache_path("qwen", "qwen3-tts-flash", "Ethan", 1.0, "你好")
    assert a != tts_mod._synth_cache_path("minimax", "qwen3-tts-flash", "Cherry", 1.0, "你好")
    assert a != tts_mod._synth_cache_path("qwen", "other-model", "Cherry", 1.0, "你好")
    assert a != tts_mod._synth_cache_path("qwen", "qwen3-tts-flash", "Cherry", 1.0, "你好啊")


def test_synth_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(tts_mod, "_SYNTH_CACHE_DIR", str(tmp_path / "synth"))
    data = b"ID3" + b"\x00" * 300
    tts_mod.put_synth_cache("qwen", "m", "v", 1.0, "测", data)
    assert tts_mod.find_synth_cache("qwen", "m", "v", 1.0, "测") == data
    assert tts_mod.find_synth_cache("qwen", "m", "v", 1.2, "测") is None