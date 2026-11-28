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


def test_synthesize_commercial_cached_hits_disk(db, tmp_path, monkeypatch):
    from app.services import tts as tts_mod

    monkeypatch.setattr(tts_mod, "_SYNTH_CACHE_DIR", str(tmp_path / "synth"))

    calls = {"n": 0}

    class Stub:
        name = "qwen"
        voice = "Cherry"
        model = "qwen3-tts-flash"

        def synthesize(self, text, voice="", speed=1.0):
            calls["n"] += 1
            return b"ID3" + b"\x01" * 300

    monkeypatch.setattr(tts_mod, "get_tts", lambda db, child_id=None: Stub())

    a = tts_mod.synthesize_commercial_cached(db, "你好", voice="", speed=1.0)
    b = tts_mod.synthesize_commercial_cached(db, "你好", voice="", speed=1.0)
    assert a == b and calls["n"] == 1


def test_synthesize_endpoint_uses_synth_cache(setup_db, monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.database import SessionLocal
    from app.routers import tts_router
    from app.routers.tts_router import router
    from app.services import tts as tts_mod
    from app.services.tts import TTSProvider
    from conftest import make_account, auth_headers

    monkeypatch.setattr(tts_mod, "_SYNTH_CACHE_DIR", str(tmp_path / "synth"))
    calls = {"n": 0}

    class Stub(TTSProvider):
        name = "qwen"
        model = "qwen3-tts-flash"

        def __init__(self):
            super().__init__(voice="Cherry", api_key="x")

        def synthesize(self, text, voice="", speed=1.0):
            calls["n"] += 1
            return b"ID3" + b"\x02" * 300

    monkeypatch.setattr(tts_router, "get_tts", lambda db, child_id=None: Stub())
    monkeypatch.setattr(tts_router, "word_audio", lambda text: None)
    monkeypatch.setattr(tts_mod, "get_tts", lambda db, child_id=None: Stub())

    s = SessionLocal()
    u = make_account(s, "u_synth_cache", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    r1 = c.get("/api/tts/synthesize?text=你好&real=false", headers=h)
    r2 = c.get("/api/tts/synthesize?text=你好&real=false", headers=h)
    assert r1.status_code == 200 and r2.status_code == 200
    assert calls["n"] == 1


def test_synthesize_commercial_cached_skips_fake(db, monkeypatch):
    from app.services import tts as tts_mod

    monkeypatch.setattr(tts_mod, "get_tts", lambda db, child_id=None: tts_mod.FakeTTS())
    try:
        tts_mod.synthesize_commercial_cached(db, "你好")
        assert False, "fake 应抛错让调用方走降级，且不写缓存"
    except RuntimeError as e:
        assert "fake" in str(e).lower() or "skip" in str(e).lower()