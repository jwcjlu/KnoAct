# backend/tests/test_knowledge_review.py
from datetime import datetime, timedelta

from app.models import KnowledgeMastery, KnowledgePoint, KnowledgeReviewItem, LearningProgress
from app.services.bucket_service import ensure_bucket
from app.services.knowledge_review import (
    apply_review_result,
    enroll_due_to_progress,
    try_enroll,
)
from app.services.mastery import record_attempt
from app.services.scheduler import INTERVALS
from conftest import make_document, make_lesson, make_user


def _kp_on_lesson(db, lesson, content="知识点"):
    kp = KnowledgePoint(
        subject=lesson.subject, category="字词", content=content, lesson_id=lesson.id
    )
    db.add(kp)
    db.flush()
    return kp


def _progress(db, user_id, document_id, subject, current_lesson_id):
    p = LearningProgress(
        user_id=user_id,
        document_id=document_id,
        subject=subject,
        current_lesson_id=current_lesson_id,
    )
    db.add(p)
    db.flush()
    return p


def _mastery(db, user_id, knowledge_point_id, bucket_id, *, mastery=0.95, mastered=True):
    m = KnowledgeMastery(
        user_id=user_id,
        knowledge_point_id=knowledge_point_id,
        bucket_id=bucket_id,
        mastery=mastery,
        mastered=mastered,
    )
    db.add(m)
    db.flush()
    return m


def test_knowledge_review_item_columns():
    cols = {c.name for c in KnowledgeReviewItem.__table__.columns}
    for name in (
        "id", "user_id", "knowledge_point_id", "bucket_id",
        "enrolled_by", "enroll_source", "enrolled_at",
        "status", "interval_index", "next_review_at",
        "last_result", "updated_at",
    ):
        assert name in cols, f"缺列 {name}"


def test_knowledge_review_item_unique_user_kp_bucket():
    # 至少有一对 (user_id, knowledge_point_id, bucket_id) 唯一约束
    assert any(
        set(c.name for c in u.columns) >= {"user_id", "knowledge_point_id", "bucket_id"}
        for u in KnowledgeReviewItem.__table__.constraints
        if u.__class__.__name__ == "UniqueConstraint"
    )


def test_try_enroll_requires_mastery_and_progress(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson_a = make_lesson(db, subject="语文", title="第1课", document=doc)
    kp = _kp_on_lesson(db, lesson_a)
    _progress(db, user.id, doc.id, "语文", lesson_a.id)
    ensure_bucket(db, user.id)
    assert try_enroll(db, user.id, kp.id) is None


def test_try_enroll_skips_ahead_of_progress(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson_a = make_lesson(db, subject="语文", title="第1课", document=doc)
    lesson_b = make_lesson(db, subject="语文", title="第2课", document=doc)
    kp_b = _kp_on_lesson(db, lesson_b)
    _progress(db, user.id, doc.id, "语文", lesson_a.id)
    bid = ensure_bucket(db, user.id).id
    _mastery(db, user.id, kp_b.id, bid)
    assert try_enroll(db, user.id, kp_b.id) is None


def test_try_enroll_success_when_mastered_in_scope(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson_a = make_lesson(db, subject="语文", title="第1课", document=doc)
    lesson_b = make_lesson(db, subject="语文", title="第2课", document=doc)
    kp_a = _kp_on_lesson(db, lesson_a)
    _progress(db, user.id, doc.id, "语文", lesson_b.id)
    bid = ensure_bucket(db, user.id).id
    _mastery(db, user.id, kp_a.id, bid)
    before = datetime.utcnow()
    row = try_enroll(db, user.id, kp_a.id, enrolled_by=user.id, source="mastery")
    after = datetime.utcnow()
    assert row is not None
    assert row.status == "active"
    assert row.interval_index == 0
    assert row.bucket_id == bid
    assert row.enroll_source == "mastery"
    expected = before + timedelta(days=INTERVALS[0])
    assert row.next_review_at >= expected - timedelta(seconds=2)
    assert row.next_review_at <= after + timedelta(days=INTERVALS[0]) + timedelta(seconds=2)


def test_try_enroll_returns_none_when_already_active(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson = make_lesson(db, subject="语文", title="第1课", document=doc)
    kp = _kp_on_lesson(db, lesson)
    _progress(db, user.id, doc.id, "语文", lesson.id)
    bid = ensure_bucket(db, user.id).id
    _mastery(db, user.id, kp.id, bid)
    first = try_enroll(db, user.id, kp.id)
    assert first is not None
    assert try_enroll(db, user.id, kp.id) is None


def test_progress_forward_enrolls_mastered_in_new_range(db):
    user = make_user(db)
    parent = make_user(db)
    doc = make_document(db, subject="语文")
    lesson_a = make_lesson(db, subject="语文", title="第1课", document=doc)
    lesson_b = make_lesson(db, subject="语文", title="第2课", document=doc)
    kp_b = _kp_on_lesson(db, lesson_b)
    _progress(db, user.id, doc.id, "语文", lesson_b.id)
    bid = ensure_bucket(db, user.id).id
    _mastery(db, user.id, kp_b.id, bid)
    n = enroll_due_to_progress(
        db,
        user.id,
        doc.id,
        "语文",
        old_lesson_id=lesson_a.id,
        new_lesson_id=lesson_b.id,
        enrolled_by=parent.id,
    )
    assert n == 1
    row = (
        db.query(KnowledgeReviewItem)
        .filter_by(user_id=user.id, knowledge_point_id=kp_b.id, bucket_id=bid)
        .first()
    )
    assert row is not None
    assert row.status == "active"
    assert row.enroll_source == "progress_adjust"
    assert row.enrolled_by == parent.id


def test_record_attempt_auto_enrolls_when_mastered_in_scope(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson = make_lesson(db, subject="语文", title="第1课", document=doc)
    kp = _kp_on_lesson(db, lesson)
    _progress(db, user.id, doc.id, "语文", lesson.id)
    bid = ensure_bucket(db, user.id).id
    for _ in range(3):
        record_attempt(db, user.id, "knowledge", kp.id, True, bucket_id=bid)
    row = (
        db.query(KnowledgeReviewItem)
        .filter_by(user_id=user.id, knowledge_point_id=kp.id, bucket_id=bid)
        .first()
    )
    assert row is not None
    assert row.status == "active"
    assert row.enroll_source == "mastery"


def test_record_attempt_does_not_enroll_ahead_of_progress(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson_a = make_lesson(db, subject="语文", title="第1课", document=doc)
    lesson_b = make_lesson(db, subject="语文", title="第2课", document=doc)
    kp_b = _kp_on_lesson(db, lesson_b)
    _progress(db, user.id, doc.id, "语文", lesson_a.id)
    bid = ensure_bucket(db, user.id).id
    for _ in range(3):
        record_attempt(db, user.id, "knowledge", kp_b.id, True, bucket_id=bid)
    row = (
        db.query(KnowledgeReviewItem)
        .filter_by(user_id=user.id, knowledge_point_id=kp_b.id, bucket_id=bid)
        .first()
    )
    assert row is None


def _review_item(db, user_id, knowledge_point_id, bucket_id, *, interval_index=0):
    now = datetime.utcnow()
    row = KnowledgeReviewItem(
        user_id=user_id,
        knowledge_point_id=knowledge_point_id,
        bucket_id=bucket_id,
        status="active",
        interval_index=interval_index,
        next_review_at=now,
    )
    db.add(row)
    db.flush()
    return row


def test_remember_increases_interval(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson = make_lesson(db, subject="语文", title="第1课", document=doc)
    kp = _kp_on_lesson(db, lesson)
    bid = ensure_bucket(db, user.id).id
    item = _review_item(db, user.id, kp.id, bid, interval_index=0)
    before = datetime.utcnow()
    apply_review_result(db, item, "remember")
    after = datetime.utcnow()
    assert item.interval_index == 1
    assert item.last_result == "remember"
    lo = before + timedelta(days=INTERVALS[1])
    hi = after + timedelta(days=INTERVALS[1]) + timedelta(seconds=2)
    assert lo <= item.next_review_at <= hi


def test_fuzzy_keeps_index(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson = make_lesson(db, subject="语文", title="第1课", document=doc)
    kp = _kp_on_lesson(db, lesson)
    bid = ensure_bucket(db, user.id).id
    i = 2
    item = _review_item(db, user.id, kp.id, bid, interval_index=i)
    before = datetime.utcnow()
    apply_review_result(db, item, "fuzzy")
    after = datetime.utcnow()
    assert item.interval_index == i
    assert item.last_result == "fuzzy"
    lo = before + timedelta(days=INTERVALS[i])
    hi = after + timedelta(days=INTERVALS[i]) + timedelta(seconds=2)
    assert lo <= item.next_review_at <= hi


def test_forgot_resets_to_zero(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson = make_lesson(db, subject="语文", title="第1课", document=doc)
    kp = _kp_on_lesson(db, lesson)
    bid = ensure_bucket(db, user.id).id
    item = _review_item(db, user.id, kp.id, bid, interval_index=3)
    before = datetime.utcnow()
    apply_review_result(db, item, "forgot")
    after = datetime.utcnow()
    assert item.interval_index == 0
    assert item.last_result == "forgot"
    lo = before + timedelta(days=INTERVALS[0])
    hi = after + timedelta(days=INTERVALS[0]) + timedelta(seconds=2)
    assert lo <= item.next_review_at <= hi


def test_idempotent_same_utc_day(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson = make_lesson(db, subject="语文", title="第1课", document=doc)
    kp = _kp_on_lesson(db, lesson)
    bid = ensure_bucket(db, user.id).id
    item = _review_item(db, user.id, kp.id, bid, interval_index=0)
    apply_review_result(db, item, "remember")
    assert item.interval_index == 1
    first_next = item.next_review_at
    apply_review_result(db, item, "remember")
    assert item.interval_index == 1
    assert item.next_review_at == first_next


def test_progress_backward_does_not_remove(db):
    user = make_user(db)
    doc = make_document(db, subject="语文")
    lesson_a = make_lesson(db, subject="语文", title="第1课", document=doc)
    lesson_b = make_lesson(db, subject="语文", title="第2课", document=doc)
    kp_a = _kp_on_lesson(db, lesson_a)
    _progress(db, user.id, doc.id, "语文", lesson_a.id)
    bid = ensure_bucket(db, user.id).id
    _mastery(db, user.id, kp_a.id, bid)
    row = try_enroll(db, user.id, kp_a.id, source="mastery")
    assert row is not None
    n = enroll_due_to_progress(
        db,
        user.id,
        doc.id,
        "语文",
        old_lesson_id=lesson_b.id,
        new_lesson_id=lesson_a.id,
        enrolled_by=user.id,
    )
    assert n == 0
    still = (
        db.query(KnowledgeReviewItem)
        .filter_by(user_id=user.id, knowledge_point_id=kp_a.id, bucket_id=bid)
        .first()
    )
    assert still is not None
    assert still.status == "active"


# ---------------------------------------------------------------------------
# Task 6：到期选取 / 出题回退 / complete & queue API
# ---------------------------------------------------------------------------
import json  # noqa: E402

from app.models import AnswerRecord, ChildConfig, Mistake, Question  # noqa: E402
from app.services import knowledge_review as kr  # noqa: E402
from conftest import auth_headers, parent_child  # noqa: E402


def _item(db, user_id, kp, bid, *, due=True, status="active", interval_index=0, minutes_ago=5):
    now = datetime.utcnow()
    nxt = now - timedelta(minutes=minutes_ago) if due else now + timedelta(days=3)
    row = KnowledgeReviewItem(
        user_id=user_id, knowledge_point_id=kp.id, bucket_id=bid,
        status=status, interval_index=interval_index, next_review_at=nxt,
        enroll_source="mastery",
    )
    db.add(row)
    db.flush()
    return row


def _kp_question(db, kp, user_id, *, answer="比喻是把一事物比作另一事物", keywords=("比喻", "事物")):
    q = Question(
        lesson_id=kp.lesson_id, qtype="knowledge", question="什么是比喻？", answer=answer,
        subject=kp.subject, status="pending", task_type="knowledge", user_id=user_id,
        extra=json.dumps({"knowledge_point_id": kp.id, "keywords": list(keywords)},
                         ensure_ascii=False),
    )
    db.add(q)
    db.flush()
    return q


def test_select_due_respects_per_subject_cap(db):
    user = make_user(db)
    bid = ensure_bucket(db, user.id).id
    db.add(ChildConfig(user_id=user.id, key="task_kp_review_count", value="2"))
    expected_cn = []
    for subject, n in (("语文", 4), ("数学", 3)):
        lesson = make_lesson(db, subject=subject)
        for i in range(n):
            kp = _kp_on_lesson(db, lesson, f"{subject}{i}")
            it = _item(db, user.id, kp, bid, minutes_ago=100 - i)
            if subject == "语文":
                expected_cn.append(it.id)
    _item(db, user.id, _kp_on_lesson(db, make_lesson(db, subject="英语"), "未到期"), bid, due=False)
    _item(db, user.id, _kp_on_lesson(db, make_lesson(db, subject="英语"), "暂停"), bid,
          status="paused")
    items = kr.select_due_items(db, user.id)
    subs = [db.get(KnowledgePoint, i.knowledge_point_id).subject for i in items]
    assert subs.count("语文") == 2 and subs.count("数学") == 2 and len(items) == 4
    # 最早到期的优先
    cn_picked = [i.id for i in items if db.get(KnowledgePoint, i.knowledge_point_id).subject == "语文"]
    assert cn_picked == expected_cn[:2]
    only_math = kr.select_due_items(db, user.id, "数学")
    assert len(only_math) == 2


def test_prompt_self_rate_when_generation_empty_and_no_answer_leak(db):
    user = make_user(db)
    bid = ensure_bucket(db, user.id).id
    kp = _kp_on_lesson(db, make_lesson(db), "比喻")
    item = _item(db, user.id, kp, bid)
    out = kr.serialize_due_item(db, user.id, item)  # 测试环境 provider=fake → 无题
    assert out["prompt"]["source"] == "self_rate"
    assert out["prompt"]["question_id"] is None
    assert out["title"] == "比喻" and out["lesson_title"] == "第1课"


def test_prompt_reuse_and_generated_do_not_expose_answer(db, monkeypatch):
    user = make_user(db)
    bid = ensure_bucket(db, user.id).id
    lesson = make_lesson(db)
    kp1 = _kp_on_lesson(db, lesson, "比喻")
    kp2 = _kp_on_lesson(db, lesson, "拟人")
    q1 = _kp_question(db, kp1, user.id)
    p1 = kr._build_prompt(db, user.id, kp1)
    assert p1["source"] == "reuse" and p1["question_id"] == q1.id
    assert "answer" not in p1 and "keywords" not in p1

    monkeypatch.setattr(
        "app.services.knowledge_quiz.generate_knowledge_questions",
        lambda db, points, subject: [{"id": points[0]["id"], "question": "什么是拟人？",
                                      "answer": "把物当人写", "keywords": ["物", "人"]}],
    )
    p2 = kr._build_prompt(db, user.id, kp2)
    assert p2["source"] == "generated" and "answer" not in p2
    saved = db.get(Question, p2["question_id"])
    assert json.loads(saved.extra)["knowledge_point_id"] == kp2.id
    assert json.loads(saved.extra)["keywords"] == ["物", "人"]
    # 再取一次应复用刚落库的题
    assert kr._build_prompt(db, user.id, kp2)["source"] == "reuse"


def test_complete_wrong_answer_forces_forgot(db):
    user = make_user(db)
    bid = ensure_bucket(db, user.id).id
    kp = _kp_on_lesson(db, make_lesson(db), "比喻")
    item = _item(db, user.id, kp, bid, interval_index=2)
    q = _kp_question(db, kp, user.id)
    out = kr.complete_item(db, user.id, item.id, "remember", question_id=q.id,
                           student_answer="不知道", duration_ms=1200)
    assert out["result"] == "forgot" and out["is_correct"] is False
    db.refresh(item)
    assert item.interval_index == 0 and item.last_result == "forgot"
    rec = db.query(AnswerRecord).filter_by(user_id=user.id).one()
    assert rec.source_type == "knowledge_review" and rec.is_correct is False
    assert rec.duration_ms == 1200
    mk = db.query(Mistake).filter_by(user_id=user.id, knowledge_point_id=kp.id).one()
    assert mk.your_answer == "不知道"
    km = db.query(KnowledgeMastery).filter_by(
        user_id=user.id, knowledge_point_id=kp.id, bucket_id=bid).one()
    assert json.loads(km.attempts) == [False]


def test_complete_correct_answer_remember_and_self_rate(db):
    user = make_user(db)
    bid = ensure_bucket(db, user.id).id
    lesson = make_lesson(db)
    kp = _kp_on_lesson(db, lesson, "比喻")
    kp2 = _kp_on_lesson(db, lesson, "拟人")
    item = _item(db, user.id, kp, bid)
    item2 = _item(db, user.id, kp2, bid, interval_index=1)
    q = _kp_question(db, kp, user.id)
    out = kr.complete_item(db, user.id, item.id, "forgot", question_id=q.id,
                           student_answer="比喻就是把一事物比作另一事物")
    assert out["result"] == "remember" and out["is_correct"] is True
    db.refresh(item)
    assert item.interval_index == 1
    # 纯自评：不判分、不写掌握度，也不收错题（remember）
    out2 = kr.complete_item(db, user.id, item2.id, "remember")
    assert out2["graded"] is False
    assert db.query(KnowledgeMastery).filter_by(
        user_id=user.id, knowledge_point_id=kp2.id).count() == 0
    assert db.query(Mistake).count() == 0


def test_complete_correct_answer_overrides_client_fuzzy(db):
    user = make_user(db)
    bid = ensure_bucket(db, user.id).id
    kp = _kp_on_lesson(db, make_lesson(db), "比喻")
    item = _item(db, user.id, kp, bid, interval_index=1)
    q = _kp_question(db, kp, user.id)
    out = kr.complete_item(db, user.id, item.id, "fuzzy", question_id=q.id,
                           student_answer="比喻就是把一事物比作另一事物")
    assert out["is_correct"] is True and out["result"] == "remember"
    db.refresh(item)
    assert item.last_result == "remember"
    assert item.interval_index == 2


def test_complete_on_paused_returns_400(client, db):
    parent, child, parent_h, child_h = parent_child(db)
    bid = ensure_bucket(db, child.id).id
    kp = _kp_on_lesson(db, make_lesson(db), "比喻")
    item = _item(db, child.id, kp, bid, status="paused")
    db.commit()
    r = client.post("/api/knowledge-review/complete", headers=child_h,
                    json={"user_id": child.id, "item_id": item.id, "result": "remember"})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "item_not_active"


def test_queue_pause_resume_remove_and_due_endpoints(client, db):
    parent, child, parent_h, child_h = parent_child(db)
    bid = ensure_bucket(db, child.id).id
    lesson = make_lesson(db)
    kp1 = _kp_on_lesson(db, lesson, "比喻")
    kp2 = _kp_on_lesson(db, lesson, "拟人")
    i1 = _item(db, child.id, kp1, bid)
    i2 = _item(db, child.id, kp2, bid, due=False)
    db.commit()
    r = client.get("/api/knowledge-review/queue", params={"user_id": child.id}, headers=parent_h)
    assert r.status_code == 200
    body = r.json()
    assert {x["item_id"] for x in body["items"]} == {i1.id, i2.id}
    assert body["due_today"] == 1 and body["due_this_week"] == 2
    # 孩子不能看队列
    assert client.get("/api/knowledge-review/queue", params={"user_id": child.id},
                      headers=child_h).status_code == 403

    r = client.get("/api/knowledge-review/due", params={"user_id": child.id}, headers=child_h)
    assert r.status_code == 200
    assert [x["item_id"] for x in r.json()["items"]] == [i1.id]

    assert client.post(f"/api/knowledge-review/item/{i1.id}/pause", headers=parent_h).json()["status"] == "paused"
    assert client.get("/api/knowledge-review/due", params={"user_id": child.id},
                      headers=child_h).json()["items"] == []
    assert client.post(f"/api/knowledge-review/item/{i1.id}/resume", headers=parent_h).json()["status"] == "active"
    assert client.post(f"/api/knowledge-review/item/{i2.id}/remove", headers=parent_h).json()["status"] == "removed"
    body = client.get("/api/knowledge-review/queue", params={"user_id": child.id},
                      headers=parent_h).json()
    assert [x["item_id"] for x in body["items"]] == [i1.id]

    # 完成 → 200，且无关孩子不能代答
    r = client.post("/api/knowledge-review/complete", headers=child_h,
                    json={"user_id": child.id, "item_id": i1.id, "result": "fuzzy"})
    assert r.status_code == 200 and r.json()["result"] == "fuzzy"
    other = make_account_other(db)
    r = client.post("/api/knowledge-review/complete", headers=auth_headers(other),
                    json={"user_id": child.id, "item_id": i1.id, "result": "remember"})
    assert r.status_code == 403


def make_account_other(db):
    from conftest import make_account
    p = make_account(db, "other_parent", "parent")
    return make_account(db, "other_child", "child", parent=p)
