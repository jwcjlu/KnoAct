from app.services.dictation_speak import (
    classify_speak_mode,
    seed_compound_from_extra,
    gloss_from_extra,
    build_speak_payload,
    parse_cue,
    dump_cue,
)


def test_classify_kind_write_is_char():
    assert classify_speak_mode(kind="write", word="事") == "char"


def test_classify_kind_phrase_is_word():
    assert classify_speak_mode(kind="phrase", word="认真") == "word"


def test_classify_fallback_by_len():
    assert classify_speak_mode(kind="", word="事") == "char"
    assert classify_speak_mode(kind="weird", word="认真") == "word"


def test_seed_compound_from_extra():
    assert seed_compound_from_extra("事", "shì 事情") == "事情"
    assert seed_compound_from_extra("事", "shì 故事很长的解释") is None


def test_gloss_from_extra_short():
    assert gloss_from_extra("认真", "rènzhēn 做事仔细") == "做事仔细"
    assert gloss_from_extra("认真", "rènzhēn " + ("很长" * 10)) is None


def test_build_speak_char_complete():
    p = build_speak_payload(word="事", kind="write", compound="事情", gloss_short=None)
    assert p["speak_text"] == "事，事情的事"
    assert p["speak_incomplete"] is False
    assert p["accept"] == ["事", "事情"]


def test_build_speak_word_complete():
    p = build_speak_payload(word="认真", kind="phrase", compound=None, gloss_short="做事仔细")
    assert p["speak_text"] == "认真，做事仔细"
    assert p["accept"] == ["认真"]


def test_build_speak_fallback():
    p = build_speak_payload(word="事", kind="write", compound=None, gloss_short=None)
    assert p["speak_text"] == "事，事"
    assert p["speak_incomplete"] is True
    assert p["accept"] == ["事"]


def test_cue_roundtrip():
    raw = dump_cue({"compound": "事情", "gloss_short": "", "source": "ai"})
    assert parse_cue(raw)["compound"] == "事情"


def test_wordbank_dictation_cue_column(setup_db, db):
    from app.models import WordBank
    from conftest import make_lesson

    lesson = make_lesson(db, subject="语文")
    wb = WordBank(
        lesson_id=lesson.id,
        subject="语文",
        word="事",
        extra="shì 事情",
        kind="write",
        dictation_cue='{"compound": "事情"}',
    )
    db.add(wb)
    db.commit()
    db.refresh(wb)
    assert "事情" in (wb.dictation_cue or "")


def _wb_char_empty(db):
    from app.models import WordBank
    from conftest import make_lesson

    lesson = make_lesson(db, subject="语文")
    wb = WordBank(
        lesson_id=lesson.id,
        subject="语文",
        word="事",
        extra="",
        kind="write",
        dictation_cue="",
    )
    db.add(wb)
    db.commit()
    db.refresh(wb)
    return wb


def test_fill_missing_cues_writes_compound(setup_db, db):
    from unittest.mock import MagicMock, patch

    from app.services.dictation_cue_fill import FILL_TIMEOUT_SEC, fill_missing_cues

    wb = _wb_char_empty(db)
    provider = MagicMock()
    provider.generate.return_value = (
        f'{{"items":[{{"id": {wb.id}, "compound": "事情", "gloss_short": ""}}]}}'
    )
    with patch("app.services.dictation_cue_fill.get_provider", return_value=provider):
        fill_missing_cues(db, [wb])
    db.refresh(wb)
    assert parse_cue(wb.dictation_cue)["compound"] == "事情"
    provider.generate.assert_called_once()
    _, kwargs = provider.generate.call_args
    assert kwargs.get("json_mode") is True
    assert kwargs.get("timeout") == FILL_TIMEOUT_SEC


def test_fill_missing_cues_ai_failure_noop(setup_db, db):
    from unittest.mock import patch

    from app.services.dictation_cue_fill import fill_missing_cues

    wb = _wb_char_empty(db)
    with patch("app.services.dictation_cue_fill.get_provider", side_effect=RuntimeError("no ai")):
        fill_missing_cues(db, [wb])
    db.refresh(wb)
    assert (wb.dictation_cue or "") == ""


def test_fill_missing_cues_passes_short_timeout(setup_db, db):
    from unittest.mock import MagicMock, patch

    from app.services.dictation_cue_fill import FILL_TIMEOUT_SEC, fill_missing_cues

    wb = _wb_char_empty(db)
    provider = MagicMock()
    provider.generate.return_value = (
        f'{{"items":[{{"id": {wb.id}, "compound": "事情", "gloss_short": ""}}]}}'
    )
    with patch("app.services.dictation_cue_fill.get_provider", return_value=provider):
        fill_missing_cues(db, [wb])
    _, kwargs = provider.generate.call_args
    assert kwargs.get("timeout") == FILL_TIMEOUT_SEC == 15.0


def test_fill_missing_cues_skips_extra_seeded(setup_db, db):
    from unittest.mock import MagicMock, patch

    from app.models import WordBank
    from app.services.dictation_cue_fill import fill_missing_cues
    from conftest import make_lesson

    lesson = make_lesson(db, subject="语文")
    wb = WordBank(
        lesson_id=lesson.id,
        subject="语文",
        word="事",
        extra="shì 事情",
        kind="write",
        dictation_cue='{"compound": "错词", "source": "ai"}',
    )
    db.add(wb)
    db.commit()
    db.refresh(wb)
    provider = MagicMock()
    with patch("app.services.dictation_cue_fill.get_provider", return_value=provider):
        fill_missing_cues(db, [wb])
    provider.generate.assert_not_called()