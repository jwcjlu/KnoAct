import pytest

from app.database import SessionLocal
from app.models import ModelConfig, ModelConnection, ModelProfile, RoleBinding
from app.services.model_config import resolve


def _clear(db):
    for m in (RoleBinding, ModelProfile, ModelConnection, ModelConfig):
        db.query(m).delete()
    db.commit()


def test_resolve_defaults_to_fake_when_nothing_configured():
    db = SessionLocal()
    _clear(db)
    r = resolve(db, "llm")
    assert r.provider == "fake"
    assert r.source == "default"
    db.close()


def test_resolve_reads_legacy_keys():
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="deepseek"))
    db.add(ModelConfig(key="ai_model", value="deepseek-chat"))
    db.add(ModelConfig(key="ai_key", value="sk-legacy"))
    db.add(ModelConfig(key="ai_base_url", value=""))
    db.commit()
    r = resolve(db, "llm")
    assert r.provider == "deepseek"
    assert r.model == "deepseek-chat"
    assert r.api_key == "sk-legacy"
    assert r.source == "legacy"
    db.close()


def test_resolve_prefers_binding_over_legacy():
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="deepseek"))
    db.add(ModelConfig(key="ai_key", value="sk-legacy"))
    conn = ModelConnection(provider="openai", name="中转站",
                           base_url="https://x/v1", api_key="sk-new")
    db.add(conn); db.flush()
    prof = ModelProfile(role="llm", connection_id=conn.id, model="gpt-4o")
    db.add(prof); db.flush()
    db.add(RoleBinding(role="llm", profile_id=prof.id))
    db.commit()

    r = resolve(db, "llm")
    assert r.provider == "openai"
    assert r.model == "gpt-4o"
    assert r.api_key == "sk-new"
    assert r.base_url == "https://x/v1"
    assert r.source == "binding"
    db.close()


def test_task_inherits_llm_by_default():
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="deepseek"))
    db.add(ModelConfig(key="ai_model", value="deepseek-chat"))
    db.commit()
    r = resolve(db, "task")
    assert r.model == "deepseek-chat"
    assert r.role == "task"
    db.close()


def test_task_reference_uses_own_profile():
    db = SessionLocal()
    _clear(db)
    conn = ModelConnection(provider="openai", name="c", api_key="sk-task")
    db.add(conn); db.flush()
    prof = ModelProfile(role="task", connection_id=conn.id, model="gpt-4o-mini")
    db.add(prof); db.flush()
    db.add(RoleBinding(role="task", profile_id=prof.id, mode="reference"))
    db.commit()
    r = resolve(db, "task")
    assert r.model == "gpt-4o-mini"
    assert r.source == "binding"
    db.close()


def test_resolve_tts_legacy_keys():
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="tts_provider", value="minimax"))
    db.add(ModelConfig(key="tts_model", value="speech-01-turbo"))
    db.add(ModelConfig(key="tts_key", value="mm-key"))
    db.add(ModelConfig(key="tts_voice", value="male-qn-qingse"))
    db.commit()
    r = resolve(db, "tts")
    assert r.provider == "minimax"
    assert r.model == "speech-01-turbo"
    assert r.options.get("voice") == "male-qn-qingse"
    db.close()


def test_llm_options_carry_vision_model_from_legacy():
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="openai"))
    db.add(ModelConfig(key="vision_model", value="qwen3-vl-plus"))
    db.commit()
    r = resolve(db, "llm")
    assert r.options.get("vision_model") == "qwen3-vl-plus"
    db.close()
