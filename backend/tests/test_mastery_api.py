from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User, KnowledgePoint, Lesson, PdfDocument, WordBank, KnowledgeMastery, WordMastery
from app.services.mastery import record_attempt

client = TestClient(app)


def _seed():
    db = SessionLocal()
    for m in (KnowledgeMastery, WordMastery, WordBank, KnowledgePoint, Lesson, PdfDocument, User):
        db.query(m).delete()
    db.commit()
    u = User(name="孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="y.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l = Lesson(document_id=doc.id, subject="语文", title="第1课",
               start_page=1, end_page=1, extract_status="done", audit_status="approved")
    db.add(l); db.flush()
    kp = KnowledgePoint(subject="语文", category="字词", content="形近字辨析", lesson_id=l.id)
    db.add(kp); db.flush()
    db.commit()
    return u.id, kp.id


def test_mastery_overview_by_subject(setup_db):
    uid, kpid = _seed()
    db = SessionLocal()
    record_attempt(db, uid, "knowledge", kpid, True)
    db.close()
    r = client.get(f"/api/mastery/overview?user_id={uid}&subject=语文")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["knowledge_point_id"] == kpid
    assert data[0]["mastery"] == 0.5


def test_mastery_record_endpoint(setup_db):
    uid, kpid = _seed()
    r = client.post("/api/mastery/record", json={
        "user_id": uid, "target_type": "knowledge", "target_id": kpid, "is_correct": True,
    })
    assert r.status_code == 200
    assert r.json()["mastery"] == 0.5
