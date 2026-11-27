"""语文课内只抽知识点（按年级侧重），词表恒空。"""
from app.services.lesson_extract import (
    build_chinese_kp_prompt,
    extract_lesson_content,
    grade_band,
)


def test_grade_band_maps_three_tiers():
    assert grade_band(1) == "1-2"
    assert grade_band(2) == "1-2"
    assert grade_band(3) == "3-4"
    assert grade_band(4) == "3-4"
    assert grade_band(5) == "5-6"
    assert grade_band(6) == "5-6"
    assert grade_band(None) == "3-4"
    assert grade_band(0) == "3-4"
    assert grade_band(9) == "3-4"


def test_chinese_kp_prompt_has_whitelist_and_grade_focus_no_word_tables():
    low = build_chinese_kp_prompt(pages="第 1–2 页", page_block="课文…", grade=1)
    mid = build_chinese_kp_prompt(pages="第 1–2 页", page_block="课文…", grade=4)
    high = build_chinese_kp_prompt(pages="第 1–2 页", page_block="课文…", grade=5)

    for p in (low, mid, high):
        assert "拼音与汉字" in p
        assert "词语" in p
        assert "句子" in p
        assert "阅读" in p
        assert "积累" in p
        assert "知识点：" in p
        assert "课文：" in p
        assert "识字：" not in p
        assert "写字：" not in p
        assert "词语：" not in p  # 不要求词语表段
        assert "生词：" not in p

    assert "笔画" in low or "拼音" in low
    assert "病句" in high or "句式" in high
    assert "关联词" in mid or "把" in mid


def test_extract_chinese_fake_provider_words_empty(db, tmp_path, monkeypatch):
    pdf = tmp_path / "cn.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(
        "app.services.lesson_extract._lesson_texts",
        lambda *a, **k: "识字\n粗 瓷\n写字\n碗\n词语\n大碗\n课文正文一段。",
    )
    out = extract_lesson_content(str(pdf), "语文", 1, 2, db, grade=5)
    assert out["words"] == []
    assert "points" in out
    assert out["text"]  # 兜底仍可有课文


def test_extract_chinese_strips_ai_words(db, tmp_path, monkeypatch):
    pdf = tmp_path / "cn.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(
        "app.services.lesson_extract._lesson_texts",
        lambda *a, **k: "一碗粗瓷大碗。",
    )

    class Stub:
        name = "stub"

        def generate(self, prompt, system=""):
            assert "识字：" not in prompt
            assert "年级侧重" in prompt or "1-2" in prompt or "5-6" in prompt or "3-4" in prompt
            return (
                "知识点：\n- 形近字辨析：辩/辨\n"
                "课文：\n一碗粗瓷大碗。\n"
                "生词：\n粗|cu\n"
                "识字：\n碗|wan\n"
            )

    monkeypatch.setattr("app.services.lesson_extract.get_provider", lambda db: Stub())
    out = extract_lesson_content(str(pdf), "语文", 1, 2, db, grade=5)
    assert out["words"] == []
    assert any("辩" in p or "形近" in p for p in out["points"])
    assert "粗瓷" in out["text"] or "大碗" in out["text"]


def test_run_extract_passes_document_grade(setup_db, monkeypatch):
    import app.routers.pdf as pdf
    from app.database import SessionLocal
    from conftest import make_document, make_lesson

    s = SessionLocal()
    doc = make_document(s, subject="语文", storage_path="unused.pdf")
    doc.grade = 5
    lesson = make_lesson(s, subject="语文", document=doc, extract_status="pending")
    s.commit()
    doc_id, lesson_id = doc.id, lesson.id
    s.close()

    captured = {}

    def fake_extract(path, subject, start, end, db, grade=None):
        captured["grade"] = grade
        return {"words": [], "points": ["点A"], "text": ""}

    monkeypatch.setattr(pdf, "extract_lesson_content", fake_extract)
    monkeypatch.setattr(pdf, "generate_reading_questions", lambda *a, **k: [])
    monkeypatch.setattr(pdf, "_sync_chinese_word_tables", lambda *a, **k: None)
    pdf._EXTRACT_PROGRESS[doc_id] = {
        "total": 1, "done": 0, "current": "", "finished": False, "error": "",
    }
    pdf._run_extract(doc_id, "unused.pdf", [{
        "id": lesson_id, "title": "第1课", "start_page": 1, "end_page": 2, "subject": "语文",
    }])
    assert captured.get("grade") == 5


def test_run_extract_skips_cn_table_lesson_kp(setup_db, monkeypatch):
    """册末识字表不走课内知识点抽取，只标 done，等册末回填写词。"""
    import app.routers.pdf as pdf
    from app.database import SessionLocal
    from app.models import KnowledgePoint, Lesson
    from conftest import make_document, make_lesson

    s = SessionLocal()
    doc = make_document(s, subject="语文", storage_path="unused.pdf")
    table = make_lesson(
        s, subject="语文", title="识字表", document=doc,
        start_page=120, end_page=128, extract_status="pending",
    )
    s.commit()
    doc_id, table_id = doc.id, table.id
    s.close()

    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("册末表课不应调用 extract_lesson_content")

    monkeypatch.setattr(pdf, "extract_lesson_content", boom)
    monkeypatch.setattr(pdf, "_sync_chinese_word_tables", lambda *a, **k: None)
    pdf._EXTRACT_PROGRESS[doc_id] = {
        "total": 1, "done": 0, "current": "", "finished": False, "error": "",
    }
    pdf._run_extract(doc_id, "unused.pdf", [{
        "id": table_id, "title": "识字表", "start_page": 120, "end_page": 128, "subject": "语文",
    }])
    assert called["n"] == 0
    s = SessionLocal()
    row = s.get(Lesson, table_id)
    assert row.extract_status == "done"
    assert s.query(KnowledgePoint).filter_by(lesson_id=table_id).count() == 0
    s.close()
