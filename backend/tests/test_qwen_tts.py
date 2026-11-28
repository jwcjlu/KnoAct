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


def test_synthesize_requires_api_key():
    from app.services.qwen_tts import synthesize_qwen

    try:
        synthesize_qwen(text="你好", api_key="")
        assert False
    except RuntimeError as e:
        assert "Key" in str(e) or "key" in str(e).lower()


def test_synthesize_posts_and_downloads(monkeypatch):
    from app.services import qwen_tts as mod

    calls = {"post": 0, "get": 0}
    wav = _pcm_wav(b"\x00\x01" * 20)

    class FakeResp:
        def __init__(self, status, payload=None, content=b""):
            self.status_code = status
            self._payload = payload or {}
            self.content = content
            self.text = str(payload)

        def json(self):
            return self._payload

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post"] += 1
        assert "multimodal-generation" in url
        assert headers["Authorization"].startswith("Bearer sk-test")
        assert json["model"] == "qwen3-tts-flash"
        assert json["input"]["voice"] == "Cherry"
        assert json["input"]["language_type"] == "Chinese"
        assert "rate" not in json["input"] and "speed" not in json["input"]
        return FakeResp(200, {
            "output": {"audio": {"url": "https://example.com/a.wav"}},
            "code": "",
        })

    def fake_get(url, timeout=None):
        calls["get"] += 1
        assert url == "https://example.com/a.wav"
        return FakeResp(200, content=wav)

    monkeypatch.setattr(mod.requests, "post", fake_post)
    monkeypatch.setattr(mod.requests, "get", fake_get)

    out = mod.synthesize_qwen(text="你好", api_key="sk-test", voice="Cherry")
    assert out == wav
    assert calls["post"] == 1 and calls["get"] == 1


from app.database import SessionLocal
from app.models import (
    ChildConfig,
    ModelConfig,
    ModelConnection,
    ModelProfile,
    RoleBinding,
    User,
)
from app.services.tts import get_tts, QwenTTS


def _clear_tts_config(db):
    for m in (RoleBinding, ModelProfile, ModelConnection, ModelConfig, ChildConfig, User):
        db.query(m).delete()
    db.commit()


def test_qwen_tts_requires_key():
    p = QwenTTS(api_key="")
    try:
        p.synthesize("测")
        assert False
    except RuntimeError:
        pass


def test_get_tts_uses_qwen_binding():
    db = SessionLocal()
    _clear_tts_config(db)
    conn = ModelConnection(provider="qwen", name="qw", api_key="sk-qwen")
    db.add(conn)
    db.flush()
    prof = ModelProfile(
        role="tts",
        connection_id=conn.id,
        model="qwen3-tts-flash",
        options='{"voice":"Cherry"}',
    )
    db.add(prof)
    db.flush()
    db.add(RoleBinding(role="tts", profile_id=prof.id))
    db.commit()

    t = get_tts(db)
    assert isinstance(t, QwenTTS)
    assert t.name == "qwen"
    assert t.api_key == "sk-qwen"
    assert t.model == "qwen3-tts-flash"
    assert t.voice == "Cherry"
    db.close()


from app.services.tts import sniff_audio_media_type


def test_sniff_audio_media_type():
    assert sniff_audio_media_type(b"RIFF...." + b"\x00" * 20) == "audio/wav"
    assert sniff_audio_media_type(b"ID3" + b"\x00" * 20) == "audio/mpeg"
    assert sniff_audio_media_type(b"\xff\xfb" + b"\x00" * 20) == "audio/mpeg"
    assert sniff_audio_media_type(b"????") == "audio/mpeg"


def test_tts_endpoint_qwen_returns_wav_content_type(setup_db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.database import SessionLocal
    from app.routers import tts_router
    from app.routers.tts_router import router
    from app.services import tts as tts_mod
    from app.services.tts import TTSProvider
    from conftest import make_account, auth_headers

    wav = _pcm_wav(b"\x00\x01" * 40)

    class Stub(TTSProvider):
        name = "qwen"

        def synthesize(self, text, voice="", speed=1.0):
            return wav

    monkeypatch.setattr(tts_router, "get_tts", lambda db, child_id=None: Stub())
    monkeypatch.setattr(tts_mod, "get_tts", lambda db, child_id=None: Stub())
    monkeypatch.setattr(tts_router, "word_audio", lambda text: None)

    s = SessionLocal()
    u = make_account(s, "u_tts_qwen_wav", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    resp = TestClient(app).get("/api/tts/synthesize?text=你好", headers=h)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/wav")
    assert resp.content[:4] == b"RIFF"