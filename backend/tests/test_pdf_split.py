from app.services.pdf_split import SUBJECT_RULES, render_pages, detect_lessons


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
