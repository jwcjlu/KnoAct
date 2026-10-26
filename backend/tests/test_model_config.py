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


def test_task_reference_without_profile_falls_back_to_llm():
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="deepseek"))
    db.add(ModelConfig(key="ai_model", value="deepseek-chat"))
    db.add(ModelConfig(key="ai_key", value="sk-legacy"))
    db.add(RoleBinding(role="task", profile_id=None, mode="reference"))
    db.commit()

    r = resolve(db, "task")
    assert r.provider == "deepseek"
    assert r.model == "deepseek-chat"
    assert r.api_key == "sk-legacy"
    assert r.role == "task"
    db.close()


def test_task_reference_with_broken_profile_falls_back_to_llm():
    """profile 指向不存在的连接时也不能退化成 fake。"""
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="deepseek"))
    db.add(ModelConfig(key="ai_model", value="deepseek-chat"))
    conn = ModelConnection(provider="openai", name="c", api_key="sk-old")
    db.add(conn); db.flush()
    prof = ModelProfile(role="task", connection_id=conn.id, model="gpt-4o-mini")
    db.add(prof); db.flush()
    db.add(RoleBinding(role="task", profile_id=prof.id, mode="reference"))
    db.commit()

    # 删掉连接，模拟「引用的连接被删掉了」
    db.delete(conn)
    db.commit()

    r = resolve(db, "task")
    assert r.provider == "deepseek"
    assert r.model == "deepseek-chat"
    assert r.source != "binding"
    db.close()


from app.services.model_config import MASK, redact, restore


def test_redact_masks_non_empty_keys_only():
    rows = [
        {"id": 1, "api_key": "sk-secret"},
        {"id": 2, "api_key": ""},
    ]
    out = redact(rows)
    assert out[0]["api_key"] == MASK
    assert out[1]["api_key"] == ""
    # 原对象不被修改
    assert rows[0]["api_key"] == "sk-secret"


def test_restore_keeps_stored_key_when_masked():
    old = [{"id": 1, "api_key": "sk-secret"}]
    new = [{"id": 1, "api_key": MASK, "name": "改个名"}]
    out = restore(old, new)
    assert out[0]["api_key"] == "sk-secret"
    assert out[0]["name"] == "改个名"


def test_restore_clears_when_empty_string():
    old = [{"id": 1, "api_key": "sk-secret"}]
    new = [{"id": 1, "api_key": ""}]
    assert restore(old, new)[0]["api_key"] == ""


def test_restore_updates_when_new_key_given():
    old = [{"id": 1, "api_key": "sk-secret"}]
    new = [{"id": 1, "api_key": "sk-brand-new"}]
    assert restore(old, new)[0]["api_key"] == "sk-brand-new"


def test_new_row_with_mask_becomes_empty():
    out = restore([], [{"api_key": MASK, "name": "新建"}])
    assert out[0]["api_key"] == ""


def test_get_provider_uses_highest_priority_source():
    from app.services.ai import get_provider
    db = SessionLocal()
    _clear(db)
    conn = ModelConnection(provider="deepseek", name="ds", api_key="sk-binding")
    db.add(conn); db.flush()
    prof = ModelProfile(role="llm", connection_id=conn.id, model="deepseek-reasoner")
    db.add(prof); db.flush()
    db.add(RoleBinding(role="llm", profile_id=prof.id))
    db.commit()

    p = get_provider(db)
    assert p.name == "deepseek"
    assert p.model == "deepseek-reasoner"
    assert p.api_key == "sk-binding"
    db.close()


def test_get_provider_falls_back_to_fake_without_config():
    from app.services.ai import get_provider
    db = SessionLocal()
    _clear(db)
    p = get_provider(db)
    assert p.name == "fake"
    db.close()


def test_get_provider_legacy_openai_keeps_base_url():
    from app.services.ai import get_provider, OpenAICompatibleProvider
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="openai"))
    db.add(ModelConfig(key="ai_model", value="gpt-4o"))
    db.add(ModelConfig(key="ai_key", value="sk-relay"))
    db.add(ModelConfig(key="ai_base_url", value="https://relay/v1"))
    db.commit()

    p = get_provider(db)
    assert isinstance(p, OpenAICompatibleProvider)
    assert p.base_url == "https://relay/v1"
    assert p.model == "gpt-4o"
    db.close()


def test_get_tts_uses_binding():
    from app.services.tts import get_tts
    db = SessionLocal()
    _clear(db)
    conn = ModelConnection(provider="minimax", name="mm", api_key="mm-key")
    db.add(conn); db.flush()
    prof = ModelProfile(role="tts", connection_id=conn.id, model="speech-01-turbo",
                        options='{"voice": "female-shaonv"}')
    db.add(prof); db.flush()
    db.add(RoleBinding(role="tts", profile_id=prof.id))
    db.commit()

    t = get_tts(db)
    assert t.name == "minimax"
    assert t.api_key == "mm-key"
    assert t.voice == "female-shaonv"
    db.close()


def test_get_tts_legacy_still_works():
    from app.services.tts import get_tts
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="tts_provider", value="minimax"))
    db.add(ModelConfig(key="tts_key", value="mm-legacy"))
    db.add(ModelConfig(key="tts_voice", value="male-qn-qingse"))
    db.commit()

    t = get_tts(db)
    assert t.name == "minimax"
    assert t.api_key == "mm-legacy"
    assert t.voice == "male-qn-qingse"
    db.close()
