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