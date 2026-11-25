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