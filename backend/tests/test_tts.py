from app import models  # noqa: F401  ensure model tables registered before create_all
from app.services.tts import get_tts, TTSProvider, FakeTTS, tts_lang_for_text


def test_get_tts_default_fake(db):
    p = get_tts(db)
    assert isinstance(p, TTSProvider)


def test_tts_config_switch(db):
    from app.models import ModelConfig
    db.add(ModelConfig(key="tts_provider", value="xunfei"))
    db.add(ModelConfig(key="tts_voice", value="讯飞女声"))
    db.commit()
    p = get_tts(db)
    assert p.name == "xunfei"
    assert p.voice == "讯飞女声"


def test_synthesize_returns_bytes():
    p = FakeTTS()
    audio = p.synthesize("徘徊", voice="童声", speed=1.0)
    assert isinstance(audio, bytes) and audio


def test_tts_lang_for_text():
    assert tts_lang_for_text("箩") == "zh"
    assert tts_lang_for_text("糕饼") == "zh"
    assert tts_lang_for_text("hello") == "en"
    assert tts_lang_for_text("go fishing") == "en"


def test_public_tts_chunks_split_long_chinese():
    from app.services.tts import _public_tts_chunks
    parts = _public_tts_chunks("你好，这是语音合成测试")
    assert parts
    assert all(len(p) <= 2 for p in parts)
    assert parts[0] == "你好"


def test_minimax_missing_key_raises():
    from app.services.tts import MiniMaxTTS
    p = MiniMaxTTS(api_key="")
    try:
        p.synthesize("徘徊")
        assert False, "应抛出 RuntimeError"
    except RuntimeError:
        pass


def test_tts_endpoint_fake_uses_browser_when_public_fails(setup_db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import tts_router
    from app.routers.tts_router import router
    from app.database import SessionLocal
    from conftest import make_account, auth_headers

    monkeypatch.setattr(tts_router, "synthesize_public_mp3", lambda text: (_ for _ in ()).throw(RuntimeError("no_net")))
    s = SessionLocal()
    u = make_account(s, "u_tts", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    resp = TestClient(app).get("/api/tts/synthesize?text=徘徊", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["use_browser_tts"] is True
    assert body.get("configured") is False


def test_tts_endpoint_fake_returns_public_mp3(setup_db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import tts_router
    from app.routers.tts_router import router
    from app.database import SessionLocal
    from conftest import make_account, auth_headers

    fake_mp3 = b"ID3" + b"\x00" * 300
    monkeypatch.setattr(tts_router, "synthesize_public_mp3", lambda text: fake_mp3)
    s = SessionLocal()
    u = make_account(s, "u_tts_mp3", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    resp = TestClient(app).get("/api/tts/synthesize?text=箩", headers=h)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/mpeg")
    assert resp.content == fake_mp3


def test_tts_endpoint_synthesize_fail_degrades_to_public_then_browser(setup_db, monkeypatch):
    """配置了真实 provider 但合成失败时：先公开朗读，再浏览器兜底；不 502。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.models import ModelConfig
    from app.routers import tts_router
    from app.routers.tts_router import router
    from app.database import SessionLocal
    from conftest import make_account, auth_headers

    monkeypatch.setattr(tts_router, "synthesize_public_mp3", lambda text: (_ for _ in ()).throw(RuntimeError("no_net")))
    s = SessionLocal()
    s.add(ModelConfig(key="tts_provider", value="xunfei"))
    s.add(ModelConfig(key="tts_key", value="dummy"))
    u = make_account(s, "u_tts_xf", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    resp = TestClient(app).get("/api/tts/synthesize?text=算", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("use_browser_tts") is True
    assert body.get("provider") == "fake"
    assert body.get("configured") is True
