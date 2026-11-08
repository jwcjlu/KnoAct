from app.core.source_registry import SOURCE_REGISTRY
from app.core.tiku_cn_adapter import TikuCnAdapter, item_to_draft


def test_normalize_single_choice_from_list():
    raw = {
        "data": {
            "list": [{
                "id": 99,
                "stem": "1+1=?",
                "type": "1",
                "optionA": "1",
                "optionB": "2",
                "answer": "B",
                "analysis": "基础运算",
            }],
        },
    }
    drafts = SOURCE_REGISTRY["tiku.cn"].normalize(raw)
    assert len(drafts) == 1
    d = drafts[0]
    assert d.qtype == "single_choice"
    assert d.answer_json.get("correct_index") == 1
    assert d.tags.get("tiku_id") == "99"


def test_normalize_multi_choice_options_array():
    raw = {"list": [{
        "question": "哪些偶数？",
        "type": "multi",
        "options": ["2", "3", "4"],
        "answer": "AC",
    }]}
    drafts = SOURCE_REGISTRY["tiku.cn"].normalize(raw)
    assert len(drafts) == 1
    assert drafts[0].qtype == "multi_choice"
    assert sorted(drafts[0].answer_json.get("correct_index", [])) == [0, 2]


def test_fetch_not_configured():
    adapter = TikuCnAdapter(base_url="", app_key="")
    raw = adapter.fetch(keyword="test")
    assert raw.get("error") == "not_configured"
    assert adapter.normalize(raw) == []


def test_item_to_draft_fill_blank():
    d = item_to_draft({"question": "春天___播种", "type": "4", "answer": "适合,温暖的"})
    assert d is not None
    assert d.qtype == "fill_blank"
    assert d.answer_json.get("blanks") == ["适合", "温暖的"]
