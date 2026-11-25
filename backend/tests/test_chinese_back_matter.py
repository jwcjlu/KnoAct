from app.services.pdf_split import (
    is_cn_table_title,
    _page_is_cn_word_table,
    _cn_table_kind_from_text,
    _detect_chinese_word_tables,
)


def test_is_cn_table_title():
    assert is_cn_table_title("词语表")
    assert is_cn_table_title("识字表")
    assert is_cn_table_title("写字表")
    assert not is_cn_table_title("桂花雨")


def test_page_kind_from_heading():
    assert _cn_table_kind_from_text("词语表\n1\n桂花 故乡") == "phrase"
    assert _cn_table_kind_from_text("写字表\n兰 桂") == "write"
    assert _cn_table_kind_from_text("识字表（会认的字）\n杭") == "recognize"
    assert _page_is_cn_word_table("词语表\n1 桂花 故乡")
    assert not _page_is_cn_word_table("第 1 课 桂花雨\n课文正文……")


def test_detect_chinese_word_tables_multi_page():
    texts = ["课文正文"] * 8
    texts[5] = "识字表\n1\n杭 营"
    texts[6] = "2\n兰 桂 rl"
    texts[7] = "写字表\n1\n篮 糕"
    result = _detect_chinese_word_tables("x.pdf", "语文", texts, len(texts), db=None)
    assert result == [
        {"kind": "recognize", "title": "识字表", "start_page": 6, "end_page": 7},
        {"kind": "write", "title": "写字表", "start_page": 8, "end_page": 8},
    ]


def test_detect_chinese_word_tables_non_chinese_subject():
    texts = ["识字表\n1\n杭"]
    assert _detect_chinese_word_tables("x.pdf", "英语", texts, len(texts), db=None) == []