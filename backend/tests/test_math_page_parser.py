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


def test_prompt_allows_text_and_underbrace(setup_db, db, monkeypatch):
    r"""\text{} / \underbrace / \begin{cases} 在 KaTeX 与 flutter_math_fork 里都能渲染
    （实测），提示词不应禁用它们——禁用会让模型把「2020个0」这类中文标注写错。"""
    import app.services.parsers.math_page as mp

    called = {}

    def _fake_vision(db_, image_bytes, system, prompt, **kw):
        called["system"] = system
        return '{"page_type":"practice","groups":[],"image_questions":[]}'

    monkeypatch.setattr(mp, "vision_json", _fake_vision)
    mp.analyze_page(db, b"\x89PNG", subject="数学")
    sys_prompt = called["system"]

    assert r"\text{}" in sys_prompt, "应允许 \\text{}"
    assert r"\underbrace" in sys_prompt, "应允许 \\underbrace"
    # 不应把它们列在「禁用」里
    forbid_line = next((ln for ln in sys_prompt.splitlines() if "禁用" in ln), "")
    assert r"\text{}" not in forbid_line
    assert r"\underbrace" not in forbid_line


def test_prompt_explains_multi_blank_split(setup_db, db, monkeypatch):
    """一题多空时要拆成多条 item，且 stem 不与 item.text 重复。"""
    import app.services.parsers.math_page as mp

    called = {}
    monkeypatch.setattr(
        mp, "vision_json",
        lambda db_, img, system, prompt, **kw: (
            called.update(system=system)
            or '{"page_type":"practice","groups":[],"image_questions":[]}'))
    mp.analyze_page(db, b"\x89PNG")

    assert "多个空" in called["system"]
    assert "不要把待填的题目本身也写进 stem" in called["system"]


def test_fix_blank_inside_math():
    r"""模型把 ____ 写进 $...$ 里会把公式劈成两半，必须挪出来。"""
    from app.services.parsers.math_page import parse_page_analysis

    def one(text):
        return parse_page_analysis(json.dumps({
            "page_type": "practice",
            "groups": [{"stem": "", "work_mode": "letter_pattern",
                        "items": [{"seq": 1, "y": 0.1, "text": text}]}],
            "image_questions": [],
        }))["groups"][0]["items"][0]["text"]

    # 真实踩到的坏形态
    assert one(r"$a \times b = ($____$)$；") == r"$a \times b =$ ____；"
    assert one(r"$x = ($____$)$") == r"$x =$ ____"
    # 已经正确的不要动
    assert one(r"$a \times b =$ ____") == r"$a \times b =$ ____"
    # 含正常公式的空位不要动
    assert one(r"$1111.05 \div 0.9 =$ ____") == r"$1111.05 \div 0.9 =$ ____"
    # 没有空位不动
    assert one(r"$1.08 \div 0.9 = 1.2$") == r"$1.08 \div 0.9 = 1.2$"


def test_wrap_bare_latex():
    r"""裸露在 $ 外的 \underline / \hspace / \text 会显示成源码，要自动包住。"""
    from app.services.parsers.math_page import parse_page_analysis

    def one(text):
        return parse_page_analysis(json.dumps({
            "page_type": "practice",
            "groups": [{"stem": "", "work_mode": "vertical",
                        "items": [{"seq": 1, "y": 0.1, "text": text}]}],
            "image_questions": [],
        }))["groups"][0]["items"][0]["text"]

    # 真实踩到的：竖式题横线写在 $ 外
    got = one("$603 - 239 =$\n\\underline{\\hspace{2cm}}")
    assert r"$\underline{\hspace{2cm}}$" in got, got
    assert "$603 - 239 =$\n$" in got, got

    # 已经包好的不动
    same = r"$603 - 239 = \underline{\hspace{2cm}}$"
    assert one(same) == same

    # 裸 \text{}
    assert one(r"共 \text{个}") == r"共 $\text{个}$"

    # 普通文本不动
    assert one("求涂色部分的面积") == "求涂色部分的面积"


def test_clean_markup_drops_stray_operator():
    r"""竖式题会把对齐用的 × 抄成独立一段（$204 \times 75 =$\n$\times$ ____），要删掉。"""
    from app.services.parsers.math_page import _clean_markup

    assert _clean_markup("$204 \\times 75 =$\n$\\times$ ____") == "$204 \\times 75 =$\n____"
    # 正常算式里的 × 不能删
    assert _clean_markup("$a \\times b =$ ____") == "$a \\times b =$ ____"
    assert _clean_markup("$3 \\times 4 = 12$") == "$3 \\times 4 = 12$"
    # 无运算符的普通文本不动
    assert _clean_markup("求涂色部分的面积") == "求涂色部分的面积"
