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


def test_fetch_rejects_numeric_chapter_id():
    """教材章节纯数字 ID 不是 knowledgeId，避免 getQuestions 回落数学题。"""
    adapter = XuekubaoAdapter(base_url="https://api.xuekubao.com", access_key="k")
    raw = adapter.fetch_by_knowledge(knowledge_id="15174", page=1, fetch_answers=False)
    assert raw.get("errorCode") == "invalid"
    assert raw.get("data") == []
    assert "章节" in (raw.get("message") or "")


def test_knowledge_tree_posts_knowledge_api(monkeypatch):
    adapter = XuekubaoAdapter(base_url="https://api.xuekubao.com", access_key="k")
    seen = {}

    def fake_post(path, body=None):
        seen["path"] = path
        seen["body"] = body
        return {"errorCode": "0", "data": [{"name": "拼音", "oldId": "abc", "child": []}]}

    monkeypatch.setattr(adapter, "_post", fake_post)
    raw = adapter.knowledge_tree(pharse_id="1", subject_id="1", grade_id="151", edition_id="81")
    assert seen["path"] == "/api/v1/knowledgeApi"
    assert seen["body"]["subjectId"] == "1"
    assert raw["data"][0]["oldId"] == "abc"
