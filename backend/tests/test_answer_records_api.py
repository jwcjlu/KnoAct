"""GET /api/answer-records 当天做题明细查询（家长/管理员）。"""
from datetime import date, datetime, timedelta

from conftest import auth_headers, make_account
from app.models import User, AnswerRecord
from app.services.answer_record import record_answer


def test_list_today_records(client, setup_db, db):
    parent = make_account(db, "mama_ar", "parent")
    child = make_account(db, "kid_ar", "child", parent=parent)
    today = datetime.utcnow()
    record_answer(db, user_id=child.id, subject="英语", module="dictation",
                  question="apple", student_answer="apple", correct_answer="apple",
                  is_correct=True, source_type="word_bank", source_id=1)
    db.commit()
    # 昨天的一条不应出现在「当天」
    old = AnswerRecord(user_id=child.id, subject="英语", module="dictation",
                       question="banana", is_correct=False,
                       created_at=today - timedelta(days=1))
    db.add(old); db.commit()

    resp = client.get(
        f"/api/answer-records?user_id={child.id}&date={date.today().isoformat()}",
        headers=auth_headers(parent),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["records"][0]["question"] == "apple"
    assert data["records"][0]["is_correct"] is True


def test_answer_records_requires_parent_or_admin(client, setup_db, db):
    child = make_account(db, "kid_noauth", "child")
    # 未认证 → 401
    assert client.get(f"/api/answer-records?user_id={child.id}").status_code == 401
    # 孩子自己（非 parent/admin）→ 403
    assert client.get(f"/api/answer-records?user_id={child.id}",
                      headers=auth_headers(child)).status_code == 403


def test_answer_records_unknown_child_404(client, setup_db, db):
    admin = make_account(db, "root_ar", "admin")
    resp = client.get("/api/answer-records?user_id=99999", headers=auth_headers(admin))
    assert resp.status_code == 404
