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
