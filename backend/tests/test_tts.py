from app import models  # noqa: F401  ensure model tables registered before create_all
from app.services.tts import get_tts, TTSProvider, FakeTTS


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


def test_minimax_missing_key_raises():
    from app.services.tts import MiniMaxTTS
    p = MiniMaxTTS(api_key="")
    try:
        p.synthesize("徘徊")
        assert False, "应抛出 RuntimeError"
    except RuntimeError:
        pass


def test_tts_endpoint_fake_uses_browser(setup_db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.tts_router import router
    from app.database import SessionLocal
    from conftest import make_account, auth_headers
    s = SessionLocal()
    u = make_account(s, "u_tts", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    resp = TestClient(app).get("/api/tts/synthesize?text=徘徊", headers=h)
    assert resp.status_code == 200
    assert resp.json()["use_browser_tts"] is True
