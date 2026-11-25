from app.models import WordBank
from app.services import word_kinds as wk


def test_word_bank_has_kind_column():
    cols = {c.name for c in WordBank.__table__.columns}
    assert "kind" in cols


def test_valid_kinds():
    assert wk.KIND_RECOGNIZE == "recognize"
    assert set(wk.CN_KINDS) == {"recognize", "write", "phrase"}
    assert wk.normalize_kind("write") == "write"
    try:
        wk.normalize_kind("unknown")
        assert False
    except ValueError:
        pass


def test_default_kind_for_subject():
    assert wk.default_kind_for_subject("语文") == "phrase"
    assert wk.default_kind_for_subject("english") == "word"


def test_get_dictation_kinds_cn_default(setup_db, db):
    from conftest import make_account
    from app.services.child_config import get_dictation_kinds_cn

    child = make_account(db, "kinds_child", "child")
    db.commit()
    assert get_dictation_kinds_cn(db, child.id) == list(wk.DEFAULT_CN_ENABLED)


def test_get_dictation_kinds_cn_parses_json(setup_db, db):
    from conftest import make_account
    from app.models import ChildConfig
    from app.services.child_config import get_dictation_kinds_cn

    child = make_account(db, "kinds_json", "child")
    db.add(ChildConfig(user_id=child.id, key="dictation_kinds_语文", value='["write","phrase"]'))
    db.commit()
    assert get_dictation_kinds_cn(db, child.id) == ["write", "phrase"]


def test_get_dictation_kinds_cn_empty_list(setup_db, db):
    from conftest import make_account
    from app.models import ChildConfig
    from app.services.child_config import get_dictation_kinds_cn

    child = make_account(db, "kinds_empty", "child")
    db.add(ChildConfig(user_id=child.id, key="dictation_kinds_语文", value="[]"))
    db.commit()
    assert get_dictation_kinds_cn(db, child.id) == []


def test_migrate_backfills_kind_by_subject(setup_db, db):
    from sqlalchemy import text

    from conftest import make_lesson
    from app.migrate_word_kind import migrate
    from app.models import WordBank

    cn = make_lesson(db, subject="语文")
    en = make_lesson(db, subject="英语")
    w1 = WordBank(lesson_id=cn.id, subject="语文", word="箩", extra="")
    w2 = WordBank(lesson_id=en.id, subject="英语", word="apple", extra="")
    db.add_all([w1, w2])
    db.commit()
    db.execute(text("UPDATE word_banks SET kind = ''"))
    db.commit()

    migrate(db)

    assert db.get(WordBank, w1.id).kind == "phrase"
    assert db.get(WordBank, w2.id).kind == "word"


def _legacy_word_banks_without_unique(db):
    """模拟迁移前库：word_banks 尚无 (lesson_id, kind, word) 唯一约束。"""
    from sqlalchemy import text

    db.execute(text("PRAGMA foreign_keys=OFF"))
    db.execute(text("DROP TABLE word_banks"))
    db.execute(text("""
        CREATE TABLE word_banks (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            subject VARCHAR(16) NOT NULL,
            word VARCHAR(64) NOT NULL,
            extra TEXT DEFAULT '',
            kind VARCHAR(16) DEFAULT 'phrase',
            FOREIGN KEY(lesson_id) REFERENCES lessons (id)
        )
    """))
    db.execute(text("PRAGMA foreign_keys=ON"))
    db.commit()
    db.expire_all()


def test_migrate_dedupes_same_lesson_kind_word(setup_db, db):
    from conftest import make_lesson, make_user
    from app.migrate_word_kind import migrate
    from app.models import Mistake, WordBank, WordMastery

    _legacy_word_banks_without_unique(db)
    lesson = make_lesson(db, subject="语文")
    user = make_user(db)
    low = WordBank(lesson_id=lesson.id, subject="语文", word="白鹭", extra="", kind="phrase")
    high = WordBank(lesson_id=lesson.id, subject="语文", word="白鹭", extra="dup", kind="phrase")
    db.add_all([low, high])
    db.flush()
    db.add(WordMastery(word_bank_id=high.id, user_id=user.id, correct_count=3, mastery=0.9))
    db.add(Mistake(
        user_id=user.id, source_type="dictation", question="听写",
        your_answer="x", correct_answer="白鹭", word_bank_id=high.id,
    ))
    db.commit()

    migrate(db)

    rows = db.query(WordBank).filter_by(lesson_id=lesson.id, word="白鹭").all()
    assert len(rows) == 1
    assert rows[0].id == low.id
    m = db.query(WordMastery).filter_by(user_id=user.id).one()
    assert m.word_bank_id == low.id and m.correct_count == 3
    mist = db.query(Mistake).filter_by(user_id=user.id).one()
    assert mist.word_bank_id == low.id


def test_migrate_idempotent(setup_db, db):
    from conftest import make_lesson
    from app.migrate_word_kind import migrate
    from app.models import WordBank

    lesson = make_lesson(db, subject="语文")
    db.add(WordBank(lesson_id=lesson.id, subject="语文", word="矗立", extra=""))
    db.commit()
    migrate(db)
    migrate(db)
    assert db.query(WordBank).filter_by(lesson_id=lesson.id).count() == 1


def test_replace_lesson_words_keeps_mastery_per_kind(setup_db, db):
    from conftest import make_lesson, make_user
    from app.models import WordBank, WordMastery
    from app.services.lesson_extract import _replace_lesson_words

    lesson = make_lesson(db, subject="语文")
    user = make_user(db)
    rec_old = WordBank(lesson_id=lesson.id, subject="语文", word="箩", extra="", kind="recognize")
    wr_old = WordBank(lesson_id=lesson.id, subject="语文", word="箩", extra="", kind="write")
    db.add_all([rec_old, wr_old])
    db.flush()
    rec_m = WordMastery(word_bank_id=rec_old.id, user_id=user.id, correct_count=5, mastery=0.7)
    wr_m = WordMastery(word_bank_id=wr_old.id, user_id=user.id, correct_count=2, mastery=0.4)
    db.add_all([rec_m, wr_m])
    db.commit()
    rec_m_id, wr_m_id = rec_m.id, wr_m.id

    _replace_lesson_words(db, lesson, [
        {"word": "箩", "extra": "luó", "kind": "recognize"},
        {"word": "箩", "extra": "luó 竹箩", "kind": "write"},
    ])
    db.commit()

    rows = {w.kind: w for w in db.query(WordBank).filter_by(lesson_id=lesson.id).all()}
    assert set(rows) == {"recognize", "write"}
    assert db.get(WordMastery, rec_m_id).word_bank_id == rows["recognize"].id
    assert db.get(WordMastery, wr_m_id).word_bank_id == rows["write"].id
    assert db.get(WordMastery, rec_m_id).correct_count == 5
    assert db.get(WordMastery, wr_m_id).correct_count == 2


def test_parse_ai_output_chinese_three_kinds():
    from app.services.lesson_extract import _parse_ai_output

    raw = """识字：
箩|luó
写字：
箩|luó
词语：
枚|máo 一枚
知识点：
白鹭
课文：
一首诗。"""
    parsed = _parse_ai_output(raw, "语文")
    kinds = [(w["word"], w["kind"]) for w in parsed["words"]]
    assert kinds == [("箩", "recognize"), ("箩", "write"), ("枚", "phrase")]
    assert parsed["points"] == ["白鹭"]
    assert "一首诗" in parsed["text"]


def test_parse_ai_output_chinese_rejects_shengci_section():
    from app.services.lesson_extract import _parse_ai_output

    raw = """生词：
箩|luó
知识点：
白鹭
课文：
一首诗。"""
    parsed = _parse_ai_output(raw, "语文")
    assert parsed["words"] == []
    assert parsed["points"] == ["白鹭"]
    assert "一首诗" in parsed["text"]


def test_parse_ai_output_english_words_have_kind_word():
    from app.services.lesson_extract import _parse_ai_output

    raw = """生词：
apple|/ˈæpl/ n. 苹果
busy|/ˈbɪzi/ adj. 忙碌的
知识点：
可数名词
课文：
Hello."""
    parsed = _parse_ai_output(raw, "英语")
    assert all(w["kind"] == "word" for w in parsed["words"])
    assert [w["word"] for w in parsed["words"]] == ["apple", "busy"]