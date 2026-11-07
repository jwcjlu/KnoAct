from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import (
    User, Task, Point, LearningProgress, Mistake, Goal, LearningRecord,
    PdfDocument, Lesson, WordBank, KnowledgePoint, Text, WordMastery,
    SchoolYearBucket, UserDocument,
)
from app.services.task_gen import generate_tasks_for_user
from conftest import auth_headers

client = TestClient(app)


def _seed():
    db = SessionLocal()
    for model in (Task, Point, LearningProgress, Mistake, Goal, LearningRecord,
                  WordMastery, WordBank, KnowledgePoint, Text, Lesson,
                  PdfDocument, User):
        db.query(model).delete()
    db.commit()
    parent = User(name="金爸爸", role="parent")
    db.add(parent)
    db.flush()
    u = User(name="金同学", role="child", parent_id=parent.id)
    db.add(u)
    db.flush()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc)
    db.flush()
    l1 = Lesson(document_id=doc.id, subject="语文", title="第1课",
                start_page=1, end_page=2, extract_status="done", audit_status="approved")
    db.add(l1)
    db.flush()
    db.add(WordBank(lesson_id=l1.id, subject="语文", word="白鹭", extra="pinyin 释义"))
    db.add(KnowledgePoint(subject="语文", category="字词", content="形近字辨析", lesson_id=l1.id))
    db.add(UserDocument(user_id=u.id, document_id=doc.id))
    db.commit()
    return u.id


def _h(uid):
    db = SessionLocal()
    try:
        return auth_headers(db.get(User, uid))
    finally:
        db.close()


def _parent_h(uid):
    db = SessionLocal()
    try:
        child = db.get(User, uid)
        return auth_headers(db.get(User, child.parent_id))
    finally:
        db.close()


def test_list_tasks_published_only_for_child():
    uid = _seed()
    generate_tasks_for_user(SessionLocal(), uid, date.today())
    r = client.get(f"/api/tasks?user_id={uid}&date={date.today()}&role=child", headers=_h(uid))
    assert r.status_code == 200
    assert r.json() == []  # pending_review, child shouldn't see


def test_approve_then_child_sees_task():
    uid = _seed()
    generate_tasks_for_user(SessionLocal(), uid, date.today())
    db = SessionLocal()
    task = db.query(Task).filter_by(user_id=uid, date=date.today()).first()
    tid = task.id
    db.close()
    assert client.post(f"/api/tasks/{tid}/approve", headers=_parent_h(uid)).json() == {"ok": True}
    r = client.get(f"/api/tasks?user_id={uid}&date={date.today()}&role=child", headers=_h(uid))
    assert len(r.json()) >= 1


def test_list_tasks_filters_by_bucket_id():
    uid = _seed()
    db = SessionLocal()
    b1 = SchoolYearBucket(user_id=uid, grade=3, school_year="2025-2026", status="archived")
    b2 = SchoolYearBucket(user_id=uid, grade=4, school_year="2026-2027", status="active")
    db.add_all([b1, b2])
    db.flush()
    t1 = Task(user_id=uid, date=date.today(), subject="语文", task_type="dictation",
              title="历史桶任务", content_status="published", bucket_id=b1.id)
    t2 = Task(user_id=uid, date=date.today(), subject="数学", task_type="custom",
              title="当前桶任务", content_status="published", bucket_id=b2.id)
    db.add_all([t1, t2])
    db.commit()
    b1id, b2id = b1.id, b2.id
    db.close()

    # 按历史桶过滤只返回该桶任务
    r = client.get(f"/api/tasks?user_id={uid}&date={date.today()}&role=parent&bucket_id={b1id}", headers=_parent_h(uid))
    titles = [t["title"] for t in r.json()]
    assert titles == ["历史桶任务"]

    r2 = client.get(f"/api/tasks?user_id={uid}&date={date.today()}&role=parent&bucket_id={b2id}", headers=_parent_h(uid))
    titles2 = [t["title"] for t in r2.json()]
    assert titles2 == ["当前桶任务"]


def test_add_custom_task_and_confirm_awards_points():
    uid = _seed()
    r = client.post("/api/tasks", json={
        "user_id": uid, "date": str(date.today()), "task_type": "custom",
        "title": "读一页书", "points": 30,
    }, headers=_parent_h(uid))
    assert r.status_code == 200
    tid = r.json()["id"]
    assert client.post(f"/api/tasks/{tid}/submit", headers=_h(uid)).json() == {"ok": True}
    assert client.post(f"/api/tasks/{tid}/confirm", headers=_parent_h(uid)).json()["ok"] is True
    db = SessionLocal()
    pts = db.query(Point).filter_by(user_id=uid).all()
    assert len(pts) == 1
    assert pts[0].delta == 30
    db.close()


def test_double_confirm_awards_only_one_point():
    uid = _seed()
    r = client.post("/api/tasks", json={
        "user_id": uid, "date": str(date.today()), "task_type": "custom",
        "title": "读一页书", "points": 30,
    }, headers=_parent_h(uid))
    tid = r.json()["id"]
    client.post(f"/api/tasks/{tid}/submit", headers=_h(uid))
    ph = _parent_h(uid)
    first = client.post(f"/api/tasks/{tid}/confirm", headers=ph).json()
    second = client.post(f"/api/tasks/{tid}/confirm", headers=ph).json()
    assert first["ok"] is True
    assert second["ok"] is True
    assert second.get("already") is True
    db = SessionLocal()
    pts = db.query(Point).filter_by(user_id=uid).all()
    assert len(pts) == 1
    assert pts[0].delta == 30
    db.close()


def test_submit_after_confirm_does_not_downgrade():
    uid = _seed()
    r = client.post("/api/tasks", json={
        "user_id": uid, "date": str(date.today()), "task_type": "custom",
        "title": "读一页书", "points": 30,
    }, headers=_parent_h(uid))
    tid = r.json()["id"]
    client.post(f"/api/tasks/{tid}/submit", headers=_h(uid))
    client.post(f"/api/tasks/{tid}/confirm", headers=_parent_h(uid))
    # 已 approved，再 submit 不应降级回 submitted
    assert client.post(f"/api/tasks/{tid}/submit", headers=_h(uid)).json() == {"ok": True}
    db = SessionLocal()
    t = db.get(Task, tid)
    assert t.submit_status == "approved"
    db.close()


def test_confirm_unsubmitted_task_is_refused():
    uid = _seed()
    r = client.post("/api/tasks", json={
        "user_id": uid, "date": str(date.today()), "task_type": "custom",
        "title": "读一页书",
    }, headers=_parent_h(uid))
    tid = r.json()["id"]
    resp = client.post(f"/api/tasks/{tid}/confirm", headers=_parent_h(uid)).json()
    assert resp["ok"] is False
    db = SessionLocal()
    t = db.get(Task, tid)
    assert t.submit_status == "not_started"
    pts = db.query(Point).filter_by(user_id=uid).all()
    assert len(pts) == 0
    db.close()


def test_upload_photo_rejects_unsupported_ext():
    uid = _seed()
    r = client.post("/api/tasks", json={
        "user_id": uid, "date": str(date.today()), "task_type": "custom",
        "title": "读一页书",
    }, headers=_parent_h(uid))
    tid = r.json()["id"]
    resp = client.post(
        f"/api/tasks/{tid}/upload-photo",
        files={"file": ("bad.txt", b"hello", "text/plain")},
        headers=_h(uid),
    )
    assert resp.json() == {"ok": False, "error": "unsupported file type"}


def _make_knowledge_task(uid, kp_id, content_extra=None):
    import json
    point = {"id": kp_id, "content": "形近字辨析", "category": "字词",
             "question": "「白鹭」和「白露」有什么区别？",
             "answer": "白鹭是鸟，白露是节气",
             "keywords": ["鸟", "节气"]}
    if content_extra:
        point.update(content_extra)
    r = client.post("/api/tasks", json={
        "user_id": uid, "date": str(date.today()), "task_type": "knowledge", "title": "基础知识",
        "content": json.dumps([point], ensure_ascii=False),
    }, headers=_parent_h(uid))
    return r.json()["id"]


def test_knowledge_review_grade_records_mastery():
    import json
    from app.models import KnowledgeMastery
    uid = _seed()
    db = SessionLocal()
    kp = db.query(KnowledgePoint).first()
    kp_id = kp.id
    db.close()
    tid = _make_knowledge_task(uid, kp_id)

    # 关键词命中的答案 → 判对，落掌握度
    d = client.post(f"/api/tasks/{tid}/knowledge-review",
                    json={"user_id": uid, "answers": [{"id": kp_id, "user_answer": "白鹭是鸟，白露是节气"}]},
                    headers=_h(uid)).json()
    assert d["ok"] is True
    assert d["correct"] == 1
    assert d["total"] == 1
    assert d["results"][0]["is_correct"] is True
    assert d["results"][0]["answer"] == "白鹭是鸟，白露是节气"

    db = SessionLocal()
    t = db.get(Task, tid)
    assert t.submit_status == "submitted"
    saved = json.loads(t.content)[0]
    assert saved["last_correct"] is True
    km = db.query(KnowledgeMastery).filter_by(user_id=uid, knowledge_point_id=kp_id).first()
    assert km is not None
    assert json.loads(km.attempts) == [True]
    db.close()


def test_knowledge_review_wrong_answer_records_false():
    import json
    from app.models import KnowledgeMastery
    uid = _seed()
    db = SessionLocal()
    kp = db.query(KnowledgePoint).first()
    kp_id = kp.id
    db.close()
    tid = _make_knowledge_task(uid, kp_id)

    d = client.post(f"/api/tasks/{tid}/knowledge-review",
                    json={"user_id": uid, "answers": [{"id": kp_id, "user_answer": "不知道"}]},
                    headers=_h(uid)).json()
    assert d["ok"] is True
    assert d["results"][0]["is_correct"] is False

    db = SessionLocal()
    km = db.query(KnowledgeMastery).filter_by(user_id=uid, knowledge_point_id=kp_id).first()
    assert json.loads(km.attempts) == [False]
    db.close()


def test_knowledge_review_refused_after_approval():
    import json
    uid = _seed()
    db = SessionLocal()
    kp = db.query(KnowledgePoint).first()
    kp_id = kp.id
    db.close()
    tid = _make_knowledge_task(uid, kp_id)
    db = SessionLocal()
    db.get(Task, tid).submit_status = "approved"
    db.commit()
    db.close()

    d = client.post(f"/api/tasks/{tid}/knowledge-review",
                    json={"user_id": uid, "answers": [{"id": kp_id, "user_answer": "白鹭是鸟"}]},
                    headers=_h(uid)).json()
    assert d["ok"] is False


def _add_dictation_task(uid):
    r = client.post("/api/tasks", json={
        "user_id": uid,
        "date": str(date.today()),
        "task_type": "dictation",
        "subject": "语文",
        "title": "听写",
        "content": "[]",
    }, headers=_parent_h(uid))
    return r.json()["id"]


def test_dictation_submit_requires_photo_in_paper_mode():
    uid = _seed()
    db = SessionLocal()
    from app.models import ChildConfig

    db.add(ChildConfig(user_id=uid, key="dictation_input_mode", value="paper_photo"))
    db.commit()
    db.close()
    tid = _add_dictation_task(uid)
    r = client.post(f"/api/tasks/{tid}/submit", headers=_h(uid))
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "photo_required"


def test_dictation_submit_ok_on_screen_without_photo():
    uid = _seed()
    db = SessionLocal()
    from app.models import ChildConfig

    db.add(ChildConfig(user_id=uid, key="dictation_input_mode", value="on_screen"))
    db.commit()
    db.close()
    tid = _add_dictation_task(uid)
    assert client.post(f"/api/tasks/{tid}/submit", headers=_h(uid)).json() == {"ok": True}


def test_dictation_confirm_rejects_paper_without_photo():
    uid = _seed()
    db = SessionLocal()
    from app.models import ChildConfig, Task

    db.add(ChildConfig(user_id=uid, key="dictation_input_mode", value="paper_photo"))
    db.commit()
    tid = _add_dictation_task(uid)
    t = db.get(Task, tid)
    t.submit_status = "submitted"
    db.commit()
    db.close()
    r = client.post(f"/api/tasks/{tid}/confirm", headers=_parent_h(uid))
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "photo_required"
