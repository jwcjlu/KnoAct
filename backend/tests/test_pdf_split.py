from app.services.pdf_split import (
    SUBJECT_RULES,
    render_pages,
    detect_lessons,
    detect_lessons_from_pdf,
    _math_unit_title,
    _math_unit_title_from_ocr,
    _clean_math_topic,
    _dedupe_math_hits,
    _detect_word_list,
)


def test_subject_rules_present():
    assert set(SUBJECT_RULES.keys()) == {"语文", "英语", "数学"}
    assert SUBJECT_RULES["数学"]["has_word_bank"] is False
    assert SUBJECT_RULES["语文"]["has_word_bank"] is True


def test_render_pages_creates_images(tmp_path):
    pages = render_pages(document_id=1, pdf_path=str(tmp_path / "nope.pdf"), out_dir=str(tmp_path))
    assert pages == []


def test_detect_lessons_anchor():
    titles = ["第 1 课 古诗三首", "第 2 课 白鹭", "第 12 课 精读"]
    lessons = detect_lessons(titles)
    assert [l["title"] for l in lessons] == ["第 1 课 古诗三首", "第 2 课 白鹭", "第 12 课 精读"]


def test_detect_lessons_from_pdf_missing_file(tmp_path):
    assert detect_lessons_from_pdf(str(tmp_path / "nope.pdf"), "语文") == []


def test_math_unit_title_beishida_layout():
    page = (
        "60\n"
        "我把图①平移到图③\n"
        "5\n"
        "第五单元5\n"
        "多边形的面积\n"
        "比较图形的面积\n"
        "北师大版\n"
    )
    assert _math_unit_title(page) == "第五单元 多边形的面积"


def test_math_unit_title_garbled_font_layer():
    page = (
        "2\n"
        "1\n"
        "第\u02b7单元\x12\n"
        "小数的\u6d59认识\n"
        "小数的认识（一）\n"
        "北师大版\n"
    )
    title = _math_unit_title(page)
    assert title.startswith("第一单元 ")
    assert "认识" in title


def test_math_unit_title_from_ocr_layout():
    raw = "第一单元  \n小数的再认识和加减法\n"
    assert _math_unit_title_from_ocr(raw) == "第一单元 小数的再认识和加减法"


def test_clean_math_topic_strips_font_garbage():
    assert _clean_math_topic("小数的\u06b9认识（一）") == "小数的认识（一）"


def test_dedupe_math_hits_same_unit():
    hits = [(65, "第五单元 多边形的面积"), (70, "第五单元 重复页眉"), (87, "第六单元 确定位置")]
    assert _dedupe_math_hits(hits) == [(65, "第五单元 多边形的面积"), (87, "第六单元 确定位置")]


def test_detect_word_list_text_keyword():
    # 文本型：书末页含 "Word List" 关键字
    texts = ["目录", "Unit 1", "Unit 2"] + ["Word List apple banana"] + ["cat dog"]
    result = _detect_word_list("x.pdf", "英语", texts, len(texts), db=None)
    assert result == {"title": "Word list", "start_page": 4, "end_page": 5}


def test_detect_word_list_ocr_scanned(monkeypatch):
    # 扫描版：文本层只有水印，靠 OCR 二分类命中
    import app.services.pdf_split as split

    texts = ["3A00012026 AU"] * 10
    calls = []

    def fake_ocr(pdf_path, page_index, db, instruction):
        calls.append(page_index)
        return "yes" if page_index == 8 else "no"

    monkeypatch.setattr(split, "_ocr_page", fake_ocr)
    result = _detect_word_list("x.pdf", "英语", texts, len(texts), db=object())
    assert result == {"title": "Word list", "start_page": 9, "end_page": 10}
    assert 8 in calls  # 确实 OCR 了书末页


def test_detect_word_list_ocr_takes_earliest(monkeypatch):
    # 多个 yes 页时取最早的（书末连续几页都是单词表）
    import app.services.pdf_split as split

    texts = ["3A00012026 AU"] * 10

    def fake_ocr(pdf_path, page_index, db, instruction):
        return "yes" if page_index in (6, 7, 8) else "no"

    monkeypatch.setattr(split, "_ocr_page", fake_ocr)
    result = _detect_word_list("x.pdf", "英语", texts, len(texts), db=object())
    assert result == {"title": "Word list", "start_page": 7, "end_page": 10}


def test_detect_word_list_not_found(monkeypatch):
    import app.services.pdf_split as split

    texts = ["3A00012026 AU"] * 10
    monkeypatch.setattr(split, "_ocr_page", lambda *a, **k: "no")
    assert _detect_word_list("x.pdf", "英语", texts, len(texts), db=object()) is None


def test_detect_word_list_non_english():
    texts = ["Unit 1", "Word List"] * 2
    assert _detect_word_list("x.pdf", "数学", texts, len(texts), db=object()) is None
