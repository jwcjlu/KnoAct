from app.core.source_registry import SOURCE_REGISTRY
from app.core.xuekubao_adapter import XuekubaoAdapter, xuekubao_item_to_draft


def test_normalize_xuekubao_single_choice():
    raw = {
        "errorCode": "0",
        "data": [{
            "id": "1001",
            "title": "1+1=?",
            "qtpye": "选择题",
            "option_a": "1",
            "option_b": "2",
            "option_c": "3",
            "option_d": "4",
            "diff": "1.00",
            "knowledgeMore": [{"knowledgeId": "ABC", "knowledgeName": "加法"}],
        }],
    }
    drafts = SOURCE_REGISTRY["xuekubao"].normalize(raw)
    assert len(drafts) == 1
    d = drafts[0]
    assert d.qtype == "single_choice"
    assert len(d.options) == 4
    assert d.tags.get("xuekubao_id") == "1001"
    assert d.tags.get("knowledge_id") == "ABC"
    assert d.difficulty == "easy"


def test_merge_answers_enriches_draft():
    item = {
        "id": "9",
        "title": "选 B",
        "qtpye": "选择题",
        "option_a": "A",
        "option_b": "B",
        "answer": "B",
        "parse": "解析说明",
    }
    d = xuekubao_item_to_draft(item)
    assert d is not None
    assert d.answer_json.get("correct_index") == 1
    assert d.analysis == "解析说明"


def test_fetch_not_configured():
    adapter = XuekubaoAdapter(base_url="https://api.xuekubao.com", access_key="")
    raw = adapter.fetch_by_knowledge(knowledge_id="kid", page=1, fetch_answers=False)
    assert raw.get("errorCode") == "not_configured"
    assert adapter.normalize(raw) == []
