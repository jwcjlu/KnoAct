from datetime import date

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import PdfDocument, Lesson, Question


def _seed_questions():
    """造 2 道 pending 题目（不同学科），各属一个 lesson。"""
    db = SessionLocal()
    doc_math = PdfDocument(filename="math.pdf", subject="数学", storage_path="")
    doc_cn = PdfDocument(filename="cn.pdf", subject="语文", storage_path="")
    db.add_all([doc_math, doc_cn])
    db.flush()
    l_math = Lesson(document_id=doc_math.id, subject="数学", title="第1课",
                    start_page=1, end_page=1, extract_status="done", audit_status="approved")
    l_cn = Lesson(document_id=doc_cn.id, subject="语文", title="第1课",
                  start_page=1, end_page=1, extract_status="done", audit_status="approved")
    db.add_all([l_math, l_cn])
    db.flush()
    today = date.today()
    q1 = Question(lesson_id=l_math.id, qtype="math", question="1+1=?",
                  answer="2", subject="数学", date=today, status="pending", task_type="math")
    q2 = Question(lesson_id=l_cn.id, qtype="knowledge", question="白鹭的作者是谁？",
                  answer="郭沫若", subject="语文", date=today, status="pending", task_type="knowledge")
    db.add_all([q1, q2])
    db.commit()
    ids = (q1.id, q2.id)
    db.close()
    return ids, today


def test_review_groups_by_subject_and_lesson(client, setup_db):
    ids, today = _seed_questions()
    r = client.get(f"/api/questions/review?d={today.isoformat()}")
    assert r.status_code == 200
    groups = r.json()["groups"]
    subjects = {g["subject"] for g in groups}
    assert subjects == {"数学", "语文"}
    by_subject = {g["subject"]: g for g in groups}
    assert by_subject["数学"]["questions"][0]["id"] == ids[0]
    assert by_subject["语文"]["questions"][0]["id"] == ids[1]
    # lesson_title 已带上课程标题
    assert by_subject["数学"]["lesson_title"] == "第1课"
    assert by_subject["语文"]["lesson_title"] == "第1课"


def test_review_filters_by_subject(client, setup_db):
    ids, today = _seed_questions()
    r = client.get(f"/api/questions/review?d={today.isoformat()}&subject=数学")
    assert r.status_code == 200
    groups = r.json()["groups"]
    assert len(groups) == 1
    assert groups[0]["subject"] == "数学"
    assert groups[0]["questions"][0]["id"] == ids[0]


def test_approve_question(client, setup_db):
    ids, _ = _seed_questions()
    r = client.post(f"/api/questions/{ids[0]}/approve")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    db = SessionLocal()
    q = db.get(Question, ids[0])
    assert q.status == "published"
    db.close()


def test_reject_question(client, setup_db):
    ids, _ = _seed_questions()
    r = client.post(f"/api/questions/{ids[0]}/reject")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    db = SessionLocal()
    q = db.get(Question, ids[0])
    assert q.status == "rejected"
    db.close()


def test_approve_missing_question_404(client, setup_db):
    r = client.post("/api/questions/99999/approve")
    assert r.status_code == 404


def test_approve_by_lesson(client, setup_db):
    ids, today = _seed_questions()
    # 数学第1课 -> ids[0] 属 lesson，直接查它的 lesson_id
    db = SessionLocal()
    lesson_id = db.get(Question, ids[0]).lesson_id
    db.close()
    r = client.post("/api/questions/approve-by-lesson",
                    params={"lesson_id": lesson_id, "d": today.isoformat()})
    assert r.status_code == 200
    db = SessionLocal()
    q = db.get(Question, ids[0])
    assert q.status == "published"
    db.close()


def test_approve_by_subject(client, setup_db):
    ids, today = _seed_questions()
    r = client.post("/api/questions/approve-by-subject",
                    params={"subject": "语文", "d": today.isoformat()})
    assert r.status_code == 200
    db = SessionLocal()
    q = db.get(Question, ids[1])
    assert q.status == "published"
    # 数学那题不受影响
    q_math = db.get(Question, ids[0])
    assert q_math.status == "pending"
    db.close()
