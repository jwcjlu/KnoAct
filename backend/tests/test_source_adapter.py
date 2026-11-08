from app.core.source_adapter import QuestionDraft, ManualAdapter, ThirdPartyAdapter
from app.core.source_registry import SOURCE_REGISTRY


def test_manual_adapter_normalize():
    raw = {"qtype": "single_choice", "question": "1+1=?", "options": [{"label": "1", "value": 0}, {"label": "2", "value": 1}], "answer_json": {"correct_index": 1}}
    drafts = ManualAdapter().normalize(raw)
    assert len(drafts) == 1
    d = drafts[0]
    assert d.qtype == "single_choice"
    assert d.options == [{"label": "1", "value": 0}, {"label": "2", "value": 1}]
    assert d.answer_json == {"correct_index": 1}


def test_third_party_registry_has_tiku():
    assert "tiku.cn" in SOURCE_REGISTRY
    adapter = SOURCE_REGISTRY["tiku.cn"]
    assert isinstance(adapter, ThirdPartyAdapter)
    assert adapter.name == "tiku.cn"


def test_tiku_stub_returns_empty():
    assert SOURCE_REGISTRY["tiku.cn"].normalize({"raw": "x"}) == []
