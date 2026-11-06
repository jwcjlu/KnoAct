"""删除课程/生词/知识点时清理引用行（外键强制下不能 500；错题保留但解除关联）。"""
import shutil

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import (
    Annotation, KnowledgeMastery, KnowledgePoint, LearningProgress, Lesson, Mistake, Note,
    PdfDocument, PdfPage, Question, Quiz, Text, Textbook, ToolCall, Turn, UserDocument, WordBank,
    WordMastery,
)
from app.routers.knowledge import router as knowledge_router
from app.routers.pdf import router as pdf_router
from app.models import User
from conftest import auth_headers, make_account, make_document, make_lesson


def _client(router):
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _seed(storage_path=""):
    """一份教材一课，课下生词/知识点各一，并让各类行引用它们。返回 id 字典。"""
    s = SessionLocal()
    parent = make_account(s, "p_fk", "parent")
    uid = make_account(s, "kid_fk", "child", parent=parent).id
    doc = make_document(s, storage_path=storage_path)
    lesson = make_lesson(s, document=doc, extract_status="done", audit_status="approved")
    lid = lesson.id
    s.add(UserDocument(user_id=uid, document_id=doc.id))
    wb = WordBank(lesson_id=lid, subject="语文", word="白鹭", extra="bái lù")
    kp = KnowledgePoint(lesson_id=lid, subject="语文", category="修辞", content="比喻")
    s.add_all([wb, kp]); s.flush()
    s.add_all([
        Text(lesson_id=lid, content="白鹭是一首精巧的诗。"),
        Question(lesson_id=lid, qtype="reading", question="白鹭像什么？", answer="诗"),
        Note(lesson_id=lid, author_role="child", content="课内笔记", knowledge_point_id=kp.id),
        Annotation(lesson_id=lid, user_id=uid, kind="highlight", quote="白鹭"),
        Quiz(lesson_id=lid, user_id=uid, questions="[]"),
        LearningProgress(user_id=uid, subject="语文", current_lesson_id=lid),
        WordMastery(word_bank_id=wb.id, user_id=uid),
        KnowledgeMastery(user_id=uid, knowledge_point_id=kp.id),
        Mistake(user_id=uid, source_type="dictation", question="听写词语：白鹭",
                your_answer="白露", correct_answer="白鹭", word_bank_id=wb.id),
        Mistake(user_id=uid, source_type="reading", question="比喻句",
                your_answer="A", correct_answer="B", knowledge_point_id=kp.id),
        PdfPage(document_id=doc.id, page_number=1, image_path="p1.png"),
        Textbook(document_id=doc.id, subject="语文", unit="第一单元"),
    ])
    turn = Turn(user_id=uid, lesson_id=lid, capability="chat", mode="chat", question="白鹭是什么？")
    s.add(turn); s.flush()
    s.add(ToolCall(turn_id=turn.id, step=1, tool_name="lookup_word"))
    s.commit()
    ids = {"uid": uid, "parent_id": parent.id, "doc": doc.id, "lesson": lid, "wb": wb.id, "kp": kp.id, "turn": turn.id}
    s.close()
    return ids


def _assert_mistakes_detached(s, uid):
    mistakes = s.query(Mistake).filter_by(user_id=uid).all()
    assert len(mistakes) == 2
    assert all(m.word_bank_id is None and m.knowledge_point_id is None for m in mistakes)


def _assert_lesson_purged(s, ids):
    lid = ids["lesson"]
    # SQLite 会复用被删的 id，按标题确认旧课已删
    assert s.query(Lesson).filter_by(title="第1课").count() == 0
    for model in (WordBank, KnowledgePoint, Text, Question, Note, Annotation, Quiz):
        assert s.query(model).filter_by(lesson_id=lid).count() == 0, model.__name__
    assert s.query(WordMastery).count() == 0
    assert s.query(KnowledgeMastery).count() == 0
    _assert_mistakes_detached(s, ids["uid"])
    prog = s.query(LearningProgress).filter_by(user_id=ids["uid"]).one()
    assert prog.current_lesson_id is None
    turn = s.get(Turn, ids["turn"])
    assert turn is not None and turn.lesson_id is None
    assert s.query(ToolCall).filter_by(turn_id=ids["turn"]).count() == 1


def test_reextract_lesson_detaches_word_and_point_references(setup_db, monkeypatch):
    import app.routers.pdf as pdf
    ids = _seed()
    monkeypatch.setattr(pdf, "extract_lesson_content", lambda *a, **k: {
        "words": [{"word": "新词", "extra": "xīn cí"}], "points": ["新知识点"], "text": "新课文。"})
    monkeypatch.setattr(pdf, "generate_reading_questions",
                        lambda db, text, n=3: [{"question": "新题", "answer": "新答"}])
    pdf._EXTRACT_PROGRESS[ids["doc"]] = {"total": 1, "done": 0, "current": "", "finished": False, "error": ""}

    pdf._run_extract(ids["doc"], "unused.pdf", [{
        "id": ids["lesson"], "title": "第1课", "start_page": 1, "end_page": 3, "subject": "语文"}])

    assert pdf._EXTRACT_PROGRESS[ids["doc"]]["error"] == ""
    s = SessionLocal()
    assert [w.word for w in s.query(WordBank).filter_by(lesson_id=ids["lesson"])] == ["新词"]
    assert [p.content for p in s.query(KnowledgePoint).filter_by(lesson_id=ids["lesson"])] == ["新知识点"]
    assert [q.question for q in s.query(Question).filter_by(lesson_id=ids["lesson"])] == ["新题"]
    assert s.query(WordMastery).count() == 0
    assert s.query(KnowledgeMastery).count() == 0
    _assert_mistakes_detached(s, ids["uid"])
    note = s.query(Note).filter_by(lesson_id=ids["lesson"]).one()
    assert note.knowledge_point_id is None
    assert s.get(Lesson, ids["lesson"]).extract_status == "done"
    s.close()


def test_resplit_document_purges_lessons_and_references(setup_db, monkeypatch, tmp_path):
    import app.routers.pdf as pdf
    src = tmp_path / "语文.pdf"
    src.write_bytes(b"%PDF-1.4")
    ids = _seed(storage_path=str(src))
    monkeypatch.setattr(pdf, "detect_lessons_from_pdf", lambda path, subject, db: [
        {"title": "新第1课", "start_page": 1, "end_page": 2},
        {"title": "新第2课", "start_page": 3, "end_page": 4},
    ])

    s = SessionLocal()
    h = auth_headers(s.get(User, ids["parent_id"]))
    s.close()
    resp = _client(pdf_router).post(f"/api/pdf/documents/{ids['doc']}/resplit", headers=h)
    assert resp.status_code == 200
    assert resp.json() == {"lessons": 2}

    s = SessionLocal()
    _assert_lesson_purged(s, ids)
    titles = [l.title for l in s.query(Lesson).filter_by(document_id=ids["doc"]).order_by(Lesson.start_page)]
    assert titles == ["新第1课", "新第2课"]
    s.close()


def test_delete_document_purges_lessons_and_references(setup_db, monkeypatch, tmp_path):
    src = tmp_path / "语文.pdf"
    src.write_bytes(b"%PDF-1.4")
    ids = _seed(storage_path=str(src))
    # 页面目录按相对路径 uploads/{id}_pages 拼，别误删开发库里的真实页面
    monkeypatch.setattr(shutil, "rmtree", lambda *a, **k: None)

    s = SessionLocal()
    h = auth_headers(s.get(User, ids["parent_id"]))
    s.close()
    resp = _client(pdf_router).delete(f"/api/pdf/documents/{ids['doc']}", headers=h)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "deleted": ids["doc"]}

    s = SessionLocal()
    _assert_lesson_purged(s, ids)
    assert s.get(PdfDocument, ids["doc"]) is None
    assert s.query(PdfPage).filter_by(document_id=ids["doc"]).count() == 0
    assert s.query(Textbook).filter_by(document_id=ids["doc"]).count() == 0
    s.close()
    assert not src.exists()


def test_delete_knowledge_point_detaches_references(setup_db):
    ids = _seed()
    s = SessionLocal()
    h = auth_headers(s.get(User, ids["parent_id"]))
    s.close()
    resp = _client(knowledge_router).delete(f"/api/knowledge/{ids['kp']}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    s = SessionLocal()
    assert s.get(KnowledgePoint, ids["kp"]) is None
    assert s.query(KnowledgeMastery).count() == 0
    kp_mistake = s.query(Mistake).filter_by(source_type="reading").one()
    assert kp_mistake.knowledge_point_id is None
    assert s.query(Note).filter_by(lesson_id=ids["lesson"]).one().knowledge_point_id is None
    # 与该知识点无关的行不受影响
    assert s.query(WordMastery).count() == 1
    assert s.query(Mistake).filter_by(source_type="dictation").one().word_bank_id == ids["wb"]
    s.close()
