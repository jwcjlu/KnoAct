from app.services.provider_registry import REGISTRY, find


def test_qwen_in_tts_not_in_llm():
    ids = {s.id for s in REGISTRY["tts"]}
    assert "qwen" in ids
    assert "qwen" not in {s.id for s in REGISTRY["llm"]}
    spec = find("qwen", "tts")
    assert spec.id == "qwen"
    assert spec.default_model == "qwen3-tts-flash"
    assert spec.needs_base_url is False