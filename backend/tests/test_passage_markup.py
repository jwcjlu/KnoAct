from app.core.passage_markup import FILL_BLANK_QTYPES, blanks_aligned, count_blanks


def test_count_blanks():
    assert count_blanks("") == 0
    assert count_blanks("hello") == 0
    assert count_blanks("I have ____ apples.") == 1
    assert count_blanks("____ and ____") == 2
    assert count_blanks("___") == 0  # 3 个下划线不算
    assert count_blanks("________") == 2  # 8 个下划线 = 两处挖空


def test_blanks_aligned_no_fill_blank_always_ok():
    assert blanks_aligned("____ appears in text", fill_blank_count=0) is True
    assert blanks_aligned("no blanks", fill_blank_count=0) is True


def test_blanks_aligned_requires_equal_count():
    assert blanks_aligned("A ____ B ____", fill_blank_count=2) is True
    assert blanks_aligned("A ____ B ____", fill_blank_count=1) is False
    assert blanks_aligned("plain", fill_blank_count=1) is False


def test_fill_blank_qtypes():
    assert "fill_blank" in FILL_BLANK_QTYPES
    assert "cloze" in FILL_BLANK_QTYPES
    assert "single_choice" not in FILL_BLANK_QTYPES
