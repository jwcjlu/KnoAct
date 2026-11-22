"""页面分析 JSON 规范化：容错、排序、题型回落、页类型过滤。"""
import json

import pytest

from app.services.parsers.math_page import analyze_page, parse_page_analysis


def _raw(payload) -> str:
    return json.dumps(payload, ensure_ascii=False)


def test_parses_normal_payload():
    raw = _raw({
        "page_type": "practice",
        "groups": [{
            "stem": "不计算，运用规律直接写出得数",
            "instruction": "",
            "work_mode": "pattern",
            "need_process": False,
            "continues_next_page": False,
            "lesson_no": 3,
            "lesson_title": "第3课时 一个数除以小数",
            "items": [
                {"seq": 1, "y": 0.18, "text": "$1.08 \\div 0.9 = 1.2$",
                 "answer_hint": "1.2", "is_example": True},
                {"seq": 4, "y": 0.57, "text": "$1111.05 \\div 0.9 =$ ____",
                 "answer_hint": "", "is_example": False},
            ],
        }],
        "image_questions": [],
    })
    out = parse_page_analysis(raw)
    assert out["page_type"] == "practice"
    assert len(out["groups"]) == 1
    g = out["groups"][0]
    assert g["work_mode"] == "pattern"
    assert g["lesson_no"] == 3
    assert g["lesson_title"] == "第3课时 一个数除以小数"
    assert [i["seq"] for i in g["items"]] == [1, 4]
    assert g["items"][0]["is_example"] is True


def test_items_sorted_by_y_for_dense_grid():
    """一页 40 道口算：AI 返回顺序可能跳行，必须按 y 排。"""
    raw = _raw({
        "page_type": "practice",
        "groups": [{"stem": "", "work_mode": "oral", "items": [
            {"seq": 3, "y": 0.5, "text": "3+3=____"},
            {"seq": 1, "y": 0.1, "text": "1+1=____"},
            {"seq": 2, "y": 0.3, "text": "2+2=____"},
        ]}],
        "image_questions": [],
    })
    out = parse_page_analysis(raw)
    assert [i["seq"] for i in out["groups"][0]["items"]] == [1, 2, 3]


def test_unknown_work_mode_falls_back_to_other():
    raw = _raw({"page_type": "practice", "groups": [
        {"stem": "x", "work_mode": "no_such_mode", "items": []},
    ], "image_questions": []})
    assert parse_page_analysis(raw)["groups"][0]["work_mode"] == "other"


@pytest.mark.parametrize("bad_type", ["toc", "answer_key", "cover", "blank"])
def test_non_practice_page_type_kept_for_router_to_skip(bad_type):
    raw = _raw({"page_type": bad_type, "groups": [], "image_questions": []})
    assert parse_page_analysis(raw)["page_type"] == bad_type


def test_unknown_page_type_defaults_to_practice():
    """拿不准页类型时宁可多导（默认 practice）。"""
    raw = _raw({"page_type": "weird", "groups": [], "image_questions": []})
    assert parse_page_analysis(raw)["page_type"] == "practice"


def test_tolerates_noise_around_json():
    raw = '这是分析结果：\n{"page_type":"practice","groups":[],"image_questions":[]}\n完毕'
    assert parse_page_analysis(raw)["page_type"] == "practice"


@pytest.mark.parametrize("raw", ["", "not json", "{broken", "[]", "null"])
def test_malformed_input_returns_safe_empty(raw):
    out = parse_page_analysis(raw)
    assert out["page_type"] == "practice"
    assert out["groups"] == []
    assert out["image_questions"] == []


def test_missing_fields_get_defaults():
    raw = _raw({"page_type": "practice", "groups": [
        {"items": [{"text": "1+1=____"}]},
    ]})
    g = parse_page_analysis(raw)["groups"][0]
    assert g["stem"] == ""
    assert g["need_process"] is False
    assert g["continues_next_page"] is False
    assert g["lesson_no"] is None
    assert g["lesson_title"] == ""
    item = g["items"][0]
    assert item["seq"] == 1        # 缺 seq 时按出现顺序补
    assert item["is_example"] is False


def test_image_questions_validated():
    raw = _raw({"page_type": "practice", "groups": [], "image_questions": [
        {"start": 0.71, "end": 0.86, "title": "求涂色部分的面积"},
        {"start": 0.9, "end": 0.1, "title": "非法范围应丢弃"},
        {"start": "x", "end": None, "title": "类型错应丢弃"},
    ]})
    iq = parse_page_analysis(raw)["image_questions"]
    assert len(iq) == 1
    assert iq[0]["title"] == "求涂色部分的面积"


def test_analyze_page_calls_vision_json(setup_db, db, monkeypatch):
    import app.services.parsers.math_page as mp

    called = {}

    def _fake_vision(db_, image_bytes, system, prompt, **kw):
        called.update(system=system, prompt=prompt, bytes=image_bytes)
        return '{"page_type":"practice","groups":[],"image_questions":[]}'

    monkeypatch.setattr(mp, "vision_json", _fake_vision)
    out = mp.analyze_page(db, b"\x89PNG", subject="数学")
    assert out["page_type"] == "practice"
    assert "严禁" in called["system"]
    assert called["bytes"] == b"\x89PNG"
    # 提示词里的 LaTeX 必须是单反斜杠（json 里才写 \\div）
    assert "\\div" in called["system"]
    assert "\\\\div" not in called["system"]
