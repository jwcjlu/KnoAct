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


def test_mastery_report_counts(setup_db):
    uid, kpid = _seed()
    db = SessionLocal()
    record_attempt(db, uid, "knowledge", kpid, True)
    db.close()
    r = client.get(f"/api/mastery/report?user_id={uid}&subject=语文")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert data["mastered"] + data["weak"] >= 1
    assert len(data["rows"]) >= 1


def test_mastery_record_scoped_to_bucket(setup_db, db):
    from app.services.bucket_service import ensure_bucket
    from app.models import User, KnowledgeMastery, KnowledgePoint, Lesson, PdfDocument
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    lesson = Lesson(document_id=doc.id, subject="语文", title="课", start_page=1, end_page=1)
    db.add(lesson); db.flush()
    kp = KnowledgePoint(lesson_id=lesson.id, subject="语文", category="字词", content="苹果")
    db.add(kp); db.flush()
    u = User(name="晨晨", role="child", grade=3)
    db.add(u); db.commit()
    b = ensure_bucket(db, u.id)
    from app.services.mastery import record_attempt
    record_attempt(db, u.id, "knowledge", kp.id, True, bucket_id=b.id)
    row = db.query(KnowledgeMastery).filter_by(user_id=u.id, knowledge_point_id=kp.id).first()
    assert row.bucket_id == b.id


def test_mastery_overview_sees_bucketed_record_only(setup_db):
    """桶内掌握度经 overview/report 可见；NULL 命名空间的旧记录不可见（按 active 桶过滤）。"""
    from app.services.bucket_service import ensure_bucket
    from app.models import User, KnowledgeMastery, KnowledgePoint, Lesson, PdfDocument
    db = SessionLocal()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    lesson = Lesson(document_id=doc.id, subject="语文", title="课", start_page=1, end_page=1)
    db.add(lesson); db.flush()
    kp = KnowledgePoint(lesson_id=lesson.id, subject="语文", category="字词", content="苹果")
    db.add(kp); db.flush()
    u = User(name="晨晨", role="child", grade=3)
    db.add(u); db.commit()
    b = ensure_bucket(db, u.id)
    uid, kpid, b_id = u.id, kp.id, b.id
    # 旧记录落在 NULL 命名空间（不带 bucket）
    record_attempt(db, uid, "knowledge", kpid, True)
    # 新记录落在 active 桶
    record_attempt(db, uid, "knowledge", kpid, True, bucket_id=b_id)
    db.close()

    r = client.get(f"/api/mastery/overview?user_id={uid}&subject=语文")
    assert r.status_code == 200
    rows = r.json()
    # active 桶过滤后，只应看到桶内的那一条（NULL 命名空间的旧行被过滤）
    assert len(rows) == 1
    assert rows[0]["knowledge_point_id"] == kpid

    rep = client.get(f"/api/mastery/report?user_id={uid}&subject=语文").json()
    assert rep["mastered"] + rep["weak"] == 1
    assert len(rep["rows"]) == 1
    assert rep["rows"][0]["knowledge_point_id"] == kpid
