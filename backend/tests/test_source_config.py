from app.models import ModelConfig
from app.services.source_config import save_sources, xuekubao_adapter


def test_xuekubao_db_overrides_env(db, monkeypatch):
    monkeypatch.setenv("XUEKUBAO_ACCESS_KEY", "env-key")
    db.add(ModelConfig(key="xuekubao_access_key", value="db-key"))
    db.add(ModelConfig(key="xuekubao_api_base", value="https://api.example.test"))
    db.commit()
    a = xuekubao_adapter(db)
    assert a.access_key == "db-key"
    assert a.base_url == "https://api.example.test"
    assert a.configured()


def test_save_sources_keeps_secret_when_empty(db):
    db.add(ModelConfig(key="xuekubao_access_key", value="keep-me"))
    db.commit()
    save_sources(db, {"xuekubao_api_base": "https://api.xuekubao.com", "xuekubao_access_key": ""})
    row = db.query(ModelConfig).filter_by(key="xuekubao_access_key").first()
    assert row.value == "keep-me"
