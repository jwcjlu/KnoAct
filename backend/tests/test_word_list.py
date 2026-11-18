from app.models import Mistake, WordBank, WordMastery
from app.services.lesson_extract import apply_word_list, extract_word_list_units, parse_word_list_text
from conftest import make_document, make_lesson, make_user


_SAMPLE = """
Word list
Unit 1
go jogging 去慢跑
*busy 忙碌的
more ... than 超过；比……更……
weekend 周末
plan 计划
*early 早的
catch 抓住
robot 机器人
Unit 2
do exercise 做运动
Me too. 我也是。
*must 必须
habit 习惯
poster 海报
strong 强壮的
less 更少的
lie 躺
注：粗体词和词组为本册核心词汇。
Proper nouns
China 中国
"""


def test_parse_word_list_groups_units_and_stops_before_proper_nouns():
    units = parse_word_list_text(_SAMPLE)
    assert [w["word"] for w in units[1]][:3] == ["go jogging", "busy", "more ... than"]
    assert units[1][1]["extra"] == "*忙碌的"
    assert units[1][0]["extra"] == "去慢跑"
    assert any(w["word"] == "Me too." for w in units[2])
    assert all(w["word"] != "China" for rows in units.values() for w in rows)
    assert not any(w["word"].startswith("注") for rows in units.values() for w in rows)


def test_parse_word_list_keeps_parenthetical_gloss():
    raw = "Unit 4\nshall （表示将来的可能性）将\n" + "\n".join(
        f"word{i} 词{i}" for i in range(3)
    )
    units = parse_word_list_text(raw)
    shall = next(w for w in units[4] if w["word"] == "shall")
    assert shall["extra"].startswith("（表示将来")


def test_extract_word_list_units_reads_continuation_until_proper_nouns(monkeypatch):
    import app.services.lesson_extract as le

    texts = ["watermark"] * 6
    monkeypatch.setattr(le, "_page_text", lambda p: texts)
    monkeypatch.setattr(
        le, "_detect_word_list",
        lambda *a, **k: {"title": "Word list", "start_page": 5, "end_page": 6},
    )
    pages = {
        4: "Unit 1\n" + "\n".join(f"word{i} 词{i}" for i in range(8)),
        5: "Unit 2\ndo exercise 做运动\nProper nouns\nChina 中国",
    }
    monkeypatch.setattr(le, "_ocr_page", lambda pdf, idx, db, instruction: pages.get(idx, "no"))
    units = extract_word_list_units("x.pdf", db=object())
    assert units[1][0]["word"] == "word0"
    assert [w["word"] for w in units[2]] == ["do exercise"]
    assert all(w["word"] != "China" for rows in units.values() for w in rows)


def test_apply_word_list_replaces_lesson_words_and_keeps_mastery(db, monkeypatch):
    import app.services.lesson_extract as le

    user = make_user(db, name="晨晨")
    doc = make_document(db, subject="英语", filename="英语.pdf", storage_path="x.pdf")
    u1 = make_lesson(db, subject="英语", title="What do we do at the weekend?", document=doc, start_page=8, end_page=19)
    u2 = make_lesson(db, subject="英语", title="How do we stay healthy?", document=doc, start_page=20, end_page=31)
    kept = WordBank(lesson_id=u1.id, subject="英语", word="go jogging", extra="旧释义")
    dropped = WordBank(lesson_id=u1.id, subject="英语", word="not-in-list", extra="x")
    db.add_all([kept, dropped])
    db.flush()
    mastery = WordMastery(word_bank_id=kept.id, user_id=user.id, correct_count=2, mastery=0.8)
    mistake = Mistake(user_id=user.id, source_type="dictation", question="go jogging",
                      your_answer="", correct_answer="go jogging", word_bank_id=dropped.id)
    db.add_all([mastery, mistake])
    db.commit()
    kept_mastery_id = mastery.id

    monkeypatch.setattr(le, "extract_word_list_units", lambda *a, **k: {
        1: [{"word": "go jogging", "extra": "去慢跑"}, {"word": "busy", "extra": "*忙碌的"}],
        2: [{"word": "healthy", "extra": "健康的"}],
    })
    stats = apply_word_list(db, doc.id, "x.pdf")
    assert stats["units"] == 2 and stats["words"] == 3

    words1 = db.query(WordBank).filter_by(lesson_id=u1.id).order_by(WordBank.id).all()
    assert [(w.word, w.extra) for w in words1] == [("go jogging", "去慢跑"), ("busy", "*忙碌的")]
    moved = db.get(WordMastery, kept_mastery_id)
    assert moved.correct_count == 2
    assert moved.word_bank_id == words1[0].id
    assert db.get(Mistake, mistake.id).word_bank_id is None
    assert [w.word for w in db.query(WordBank).filter_by(lesson_id=u2.id).all()] == ["healthy"]


def test_apply_word_list_adds_word_list_lesson(db, monkeypatch):
    import app.services.lesson_extract as le
    from app.models import Lesson

    doc = make_document(db, subject="英语", filename="英语.pdf", storage_path="x.pdf")
    lesson = make_lesson(db, subject="英语", title="What do we do at the weekend?",
                         document=doc, start_page=8, end_page=20, audit_status="approved")
    db.commit()
    monkeypatch.setattr(le, "extract_word_list_units", lambda *a, **k: {
        1: [{"word": "go jogging", "extra": "去慢跑"}, {"word": "busy", "extra": "*忙碌的"}],
    })
    monkeypatch.setattr(le, "_detect_word_list", lambda *a, **k: {
        "title": "单词列表", "start_page": 18, "end_page": 19,
    })
    monkeypatch.setattr(le, "_page_text", lambda p: ["x"] * 20)
    apply_word_list(db, doc.id, "x.pdf")
    db.refresh(lesson)
    assert lesson.end_page == 17
    module = db.query(Lesson).filter_by(document_id=doc.id, title="单词列表").one()
    assert (module.start_page, module.end_page, module.audit_status) == (18, 19, "approved")
    rows = db.query(WordBank).filter_by(lesson_id=module.id).order_by(WordBank.id).all()
    assert [(w.word, w.extra) for w in rows] == [
        ("go jogging", "Unit 1 · 去慢跑"),
        ("busy", "Unit 1 · *忙碌的"),
    ]

