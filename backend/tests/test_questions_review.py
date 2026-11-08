from datetime import date

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import PdfDocument, Lesson, Question, User
from conftest import auth_headers, make_account

client = TestClient(app)


def _seed_questions():
    """造 2 道 pending 题目（不同学科），各属一个 lesson。"""
    db = SessionLocal()
    parent = make_account(db, "p_qr", "parent")
    db.commit()
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
    pid = parent.id
    db.close()
    return ids, today, pid


def _ph(pid):
    s = SessionLocal()
    h = auth_headers(s.get(User, pid))
    s.close()
    return h


def test_review_groups_by_subject_and_lesson(client, setup_db):
    ids, today, pid = _seed_questions()
    h = _ph(pid)
    r = client.get(f"/api/questions/review?d={today.isoformat()}", headers=h)
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
    ids, today, pid = _seed_questions()
    h = _ph(pid)
    r = client.get(f"/api/questions/review?d={today.isoformat()}&subject=数学", headers=h)
    assert r.status_code == 200
    groups = r.json()["groups"]
    assert len(groups) == 1
    assert groups[0]["subject"] == "数学"
    assert groups[0]["questions"][0]["id"] == ids[0]


def test_approve_question(client, setup_db):
    ids, _, pid = _seed_questions()
    h = _ph(pid)
    r = client.post(f"/api/questions/{ids[0]}/approve", headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    db = SessionLocal()
    q = db.get(Question, ids[0])
    assert q.status == "published"
    db.close()


def test_reject_question(client, setup_db):
    ids, _, pid = _seed_questions()
    h = _ph(pid)
    r = client.post(f"/api/questions/{ids[0]}/reject", headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    db = SessionLocal()
    q = db.get(Question, ids[0])
    assert q.status == "rejected"
    db.close()


def test_approve_missing_question_404(client, setup_db):
    _, _, pid = _seed_questions()
    h = _ph(pid)
    r = client.post("/api/questions/99999/approve", headers=h)
    assert r.status_code == 404


def test_approve_by_lesson(client, setup_db):
    ids, today, pid = _seed_questions()
    h = _ph(pid)
    # 数学第1课 -> ids[0] 属 lesson，直接查它的 lesson_id
    db = SessionLocal()
    lesson_id = db.get(Question, ids[0]).lesson_id
    db.close()
    r = client.post("/api/questions/approve-by-lesson",
                    params={"lesson_id": lesson_id, "d": today.isoformat()},
                    headers=h)
    assert r.status_code == 200
    db = SessionLocal()
    q = db.get(Question, ids[0])
    assert q.status == "published"
    db.close()


def test_approve_by_subject(client, setup_db):
    ids, today, pid = _seed_questions()
    h = _ph(pid)
    r = client.post("/api/questions/approve-by-subject",
                    params={"subject": "语文", "d": today.isoformat()},
                    headers=h)
    assert r.status_code == 200
    db = SessionLocal()
    q = db.get(Question, ids[1])
    assert q.status == "published"
    # 数学那题不受影响
    q_math = db.get(Question, ids[0])
    assert q_math.status == "pending"
    db.close()


def test_add_question_rich_structure(client, setup_db):
    db = SessionLocal()
    parent = make_account(db, "rich_parent", "parent")
    h = auth_headers(parent)
    db.close()
    body = {
        "lesson_id": None,
        "bank_id": None,
        "qtype": "single_choice",
        "question": "1+1=?",
        "options": [{"label": "2", "value": 0}, {"label": "1", "value": 1}],
        "answer_json": {"correct_index": 0},
        "answer": "2",
    }
    r = client.post("/api/questions", json=body, headers=h)
    assert r.status_code == 200
    qid = r.json()["id"]
    db = SessionLocal()
    q = db.get(Question, qid)
    db.close()
    assert q.qtype == "single_choice"
    assert q.qtype_category == "choice"
    assert q.status == "pending"  # 人工录入默认进审核队列
    assert "2" in q.options
