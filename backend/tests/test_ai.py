from app.services.ai import get_provider, AIProvider, FakeProvider


def test_get_provider_returns_fake_when_no_config(db):
    p = get_provider(db)
    assert isinstance(p, AIProvider)


def test_provider_config_switch(db):
    from app.models import ModelConfig
    db.add(ModelConfig(key="ai_provider", value="glm"))
    db.add(ModelConfig(key="ai_model", value="glm-4-flash"))
    db.commit()
    p = get_provider(db)
    assert p.name == "glm"
    assert p.model == "glm-4-flash"


def test_generate_returns_string():
    p = FakeProvider()
    out = p.generate(prompt="你好", system="")
    assert isinstance(out, str) and out
