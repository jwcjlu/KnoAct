from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User, PdfDocument, Lesson, Text, ModelConfig

client = TestClient(app)


def _seed():
    db = SessionLocal()
    for m in (Text, Lesson, PdfDocument, User, ModelConfig):
        db.query(m).delete()
    db.commit()
    u = User(name="孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="y.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l = Lesson(document_id=doc.id, subject="语文", title="第1课",
               start_page=1, end_page=1, extract_status="done", audit_status="approved")
    db.add(l); db.flush()
    db.add(Text(lesson_id=l.id, content="白鹭是一首精巧的诗。"))
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit()
    return l.id


def test_ask_questions_requires_ai(setup_db):
    lid = _seed()
    r = client.post("/api/ask/questions", json={"lesson_id": lid})
    assert r.status_code == 503


def test_ask_reply_requires_ai(setup_db):
    lid = _seed()
    r = client.post("/api/ask/reply", json={"lesson_id": lid, "replies": {"q1": "好"}})
    assert r.status_code == 503
