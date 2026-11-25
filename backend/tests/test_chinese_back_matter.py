from app.models import KnowledgePoint, WordBank
from app.services.pdf_split import (
    is_cn_table_title,
    _page_is_cn_word_table,
    _cn_table_kind_from_text,
    _detect_chinese_word_tables,
)
from app.services import lesson_extract as le
from app.services.lesson_extract import (
    apply_chinese_word_tables,
    extract_chinese_table_units,
    parse_chinese_table_text,
)
from app.services.word_kinds import KIND_PHRASE, KIND_RECOGNIZE
from conftest import make_document, make_lesson

_PHRASE_SAMPLE = """
词语表
1
桂花 故乡 时节 欣赏 糕饼 成熟 完整
茶叶
2
播种 收获 食品 吩咐 价钱 可贵 果实
体面
4
地道 平原 扫荡 封锁 武装 粉碎 简直
"""


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


def test_parse_chinese_table_groups_by_lesson_no():
    by = parse_chinese_table_text(_PHRASE_SAMPLE, kind="phrase")
    assert [w["word"] for w in by[1]][:3] == ["桂花", "故乡", "时节"]
    assert any(w["word"] == "茶叶" for w in by[1])
    assert any(w["word"] == "体面" for w in by[2])
    assert 3 not in by
    assert by[4][0]["word"] == "地道"
    assert all(w.get("kind") == "phrase" for rows in by.values() for w in rows)


def test_parse_write_table_single_chars():
    raw = "写字表\n1\n兰 桂 曼\n2\n亩 亭 吩\n"
    by = parse_chinese_table_text(raw, kind="write")
    assert [w["word"] for w in by[1]] == ["兰", "桂", "曼"]
    assert [w["word"] for w in by[2]] == ["亩", "亭", "吩"]


def test_parse_chinese_table_lesson_no_on_same_line():
    raw = "词语表\n1 桂花 故乡\n2 播种 收获\n"
    by = parse_chinese_table_text(raw, kind="phrase")
    assert [w["word"] for w in by[1]] == ["桂花", "故乡"]
    assert [w["word"] for w in by[2]] == ["播种", "收获"]


def test_extract_chinese_table_units(monkeypatch):
    sample = "词语表\n1\n桂花 故乡\n"
    monkeypatch.setattr(le, "_lesson_texts", lambda pdf, sp, ep, db=None: sample)
    by = extract_chinese_table_units("x.pdf", None, "phrase", 6, 6)
    assert [w["word"] for w in by[1]] == ["桂花", "故乡"]


def test_replace_kind_only_leaves_other_kinds_and_points(db, monkeypatch):
    doc = make_document(db, subject="语文", filename="语文.pdf", storage_path="x.pdf")
    l1 = make_lesson(db, subject="语文", title="桂花雨", document=doc, start_page=7, end_page=9)
    l2 = make_lesson(db, subject="语文", title="落花生", document=doc, start_page=10, end_page=11)
    db.add_all([
        WordBank(lesson_id=l1.id, subject="语文", word="杭", extra="", kind=KIND_RECOGNIZE),
        WordBank(lesson_id=l1.id, subject="语文", word="旧词", extra="", kind=KIND_PHRASE),
        KnowledgePoint(lesson_id=l1.id, subject="语文", category="本课", content="借物抒情"),
    ])
    db.commit()
    monkeypatch.setattr(le, "_detect_chinese_word_tables", lambda *a, **k: [
        {"kind": KIND_PHRASE, "title": "词语表", "start_page": 90, "end_page": 91},
    ])
    monkeypatch.setattr(le, "extract_chinese_table_units", lambda pdf, db, kind, sp, ep: {
        1: [{"word": "桂花", "extra": "", "kind": KIND_PHRASE},
            {"word": "故乡", "extra": "", "kind": KIND_PHRASE}],
        2: [{"word": "播种", "extra": "", "kind": KIND_PHRASE}],
    } if kind == KIND_PHRASE else {})
    r = apply_chinese_word_tables(db, doc.id, "x.pdf")
    assert r["words"] >= 3
    phrases = [w.word for w in db.query(WordBank).filter_by(lesson_id=l1.id, kind=KIND_PHRASE)]
    assert set(phrases) == {"桂花", "故乡"}
    assert "旧词" not in phrases
    assert db.query(WordBank).filter_by(lesson_id=l1.id, kind=KIND_RECOGNIZE, word="杭").count() == 1
    assert db.query(KnowledgePoint).filter_by(lesson_id=l1.id).count() == 1


def test_missing_lesson_no_does_not_clear_kind(db, monkeypatch):
    doc = make_document(db, subject="语文", filename="语文.pdf", storage_path="x.pdf")
    l3 = make_lesson(db, subject="语文", title="第三课", document=doc, start_page=12, end_page=14)
    db.add(WordBank(lesson_id=l3.id, subject="语文", word="留", extra="", kind=KIND_PHRASE))
    db.commit()
    monkeypatch.setattr(le, "_detect_chinese_word_tables", lambda *a, **k: [
        {"kind": KIND_PHRASE, "title": "词语表", "start_page": 90, "end_page": 90},
    ])
    monkeypatch.setattr(le, "extract_chinese_table_units", lambda *a, **k: {
        4: [{"word": "地道", "extra": "", "kind": KIND_PHRASE}],
    })
    apply_chinese_word_tables(db, doc.id, "x.pdf")
    assert db.query(WordBank).filter_by(lesson_id=l3.id, word="留").count() == 1