from app.core.source_adapter import QuestionDraft, ManualAdapter, ThirdPartyAdapter, OcrAdapter
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


def test_third_party_registry_has_xuekubao():
    from app.core.xuekubao_adapter import XuekubaoAdapter

    assert "xuekubao" in SOURCE_REGISTRY
    adapter = SOURCE_REGISTRY["xuekubao"]
    assert isinstance(adapter, XuekubaoAdapter)
    assert adapter.name == "xuekubao"


def test_tiku_normalize_unknown_shape_returns_empty():
    assert SOURCE_REGISTRY["tiku.cn"].normalize({"raw": "x"}) == []


def test_ocr_adapter_normalize_dict_and_list():
    # dict-with-questions 与 prompt/choices 回退分支
    raw = {"questions": [
        {"prompt": "3+2=?", "choices": [{"label": "5", "value": 0}], "answer": "5"},
        {"question": "", "prompt": "", "answer": "忽略空题干"},
        "not-a-dict",
    ]}
    drafts = OcrAdapter().normalize(raw)
    assert len(drafts) == 1
    d = drafts[0]
    assert d.qtype == "short_answer"  # 未给 qtype 默认
    assert d.question == "3+2=?"
    assert d.options == [{"label": "5", "value": 0}]
