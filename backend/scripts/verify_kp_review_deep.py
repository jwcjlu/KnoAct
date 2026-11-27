"""知识点复习 SRS 深验证（对齐规格成功标准 + 手动验收清单）。

用法（在 backend/）：
  set DATABASE_URL=sqlite:///./verify_kp_review.db
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8011
  python scripts/verify_kp_review_deep.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011"
FAILS: list[str] = []


def http(method: str, path: str, body: dict | None = None, token: str | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return e.code, payload


def ok(msg: str):
    print(f"OK  {msg}")


def fail(msg: str):
    print(f"FAIL: {msg}")
    FAILS.append(msg)


def check(cond: bool, msg: str):
    if cond:
        ok(msg)
    else:
        fail(msg)


def seed():
    import os

    os.environ.setdefault("DATABASE_URL", "sqlite:///./verify_kp_review.db")
    from app.database import SessionLocal, engine, Base
    from app.models import (
        User, PdfDocument, Lesson, KnowledgePoint, LearningProgress,
        KnowledgeMastery, UserDocument, KnowledgeReviewItem, Task, WordBank,
        WordMastery, AnswerRecord, Mistake,
    )
    from app.services.security import hash_password
    from app.services.bucket_service import ensure_bucket
    from app.schema_sync import sync_schema

    sync_schema(engine, Base.metadata)
    db = SessionLocal()
    try:
        for name in ("vfy_parent", "vfy_child"):
            u = db.query(User).filter_by(login_name=name).first()
            if not u:
                continue
            db.query(Task).filter_by(user_id=u.id).delete()
            db.query(AnswerRecord).filter_by(user_id=u.id).delete()
            db.query(Mistake).filter_by(user_id=u.id).delete()
            db.query(KnowledgeReviewItem).filter_by(user_id=u.id).delete()
            db.query(KnowledgeMastery).filter_by(user_id=u.id).delete()
            db.query(WordMastery).filter_by(user_id=u.id).delete()
            db.query(LearningProgress).filter_by(user_id=u.id).delete()
            db.query(UserDocument).filter_by(user_id=u.id).delete()
            db.delete(u)
        db.commit()

        parent = User(
            name="验证家长", login_name="vfy_parent", display_name="验证家长",
            role="parent", password_hash=hash_password("Verify123"),
        )
        db.add(parent)
        db.flush()
        child = User(
            name="验证孩子", login_name="vfy_child", display_name="验证孩子",
            role="child", parent_id=parent.id, grade=3,
            password_hash=hash_password("Verify123"),
        )
        db.add(child)
        db.flush()
        bucket = ensure_bucket(db, child.id)

        doc = PdfDocument(filename="verify.pdf", subject="语文", storage_path="")
        db.add(doc)
        db.flush()
        lessons = []
        for i, title in enumerate(("第1课", "第2课", "第3课"), start=1):
            les = Lesson(
                document_id=doc.id, subject="语文", title=title,
                start_page=i * 2 - 1, end_page=i * 2,
                extract_status="done", audit_status="approved",
            )
            db.add(les)
            db.flush()
            lessons.append(les)

        kps = []
        for les, content in zip(lessons, ("比喻", "拟人", "夸张")):
            kp = KnowledgePoint(
                lesson_id=les.id, subject="语文", category="修辞", content=content,
            )
            db.add(kp)
            db.flush()
            kps.append(kp)

        # 无 lesson 的 KP：永不自动入队
        orphan = KnowledgePoint(subject="语文", category="修辞", content="无课知识点")
        db.add(orphan)
        db.flush()

        db.add(UserDocument(user_id=child.id, document_id=doc.id))
        db.add(LearningProgress(
            user_id=child.id, document_id=doc.id, subject="语文",
            current_lesson_id=lessons[0].id,
        ))
        # 三课 KP 都已掌握；当前进度仅第1课 → 只有 kp0 可入队
        for kp in kps:
            db.add(KnowledgeMastery(
                user_id=child.id, knowledge_point_id=kp.id, bucket_id=bucket.id,
                mastery=0.95, mastered=True, attempts=json.dumps([True, True, True]),
            ))
        db.add(KnowledgeMastery(
            user_id=child.id, knowledge_point_id=orphan.id, bucket_id=bucket.id,
            mastery=0.95, mastered=True, attempts=json.dumps([True, True, True]),
        ))
        # 生词 mastery 供 word review 并存验证（可选）
        wb = WordBank(lesson_id=lessons[0].id, subject="语文", word="白鹭", extra="")
        db.add(wb)
        db.flush()
        db.add(WordMastery(
            user_id=child.id, word_bank_id=wb.id, bucket_id=bucket.id,
            mastery=0.2, mistake_count=3, is_weak=True,
        ))

        from app.services.knowledge_review import try_enroll
        row0 = try_enroll(db, child.id, kps[0].id, source="mastery")
        row_orphan = try_enroll(db, child.id, orphan.id, source="mastery")
        db.commit()
        return {
            "parent_id": parent.id,
            "child_id": child.id,
            "doc_id": doc.id,
            "l1": lessons[0].id,
            "l2": lessons[1].id,
            "l3": lessons[2].id,
            "kp1": kps[0].id,
            "kp2": kps[1].id,
            "kp3": kps[2].id,
            "orphan": orphan.id,
            "item1": row0.id if row0 else None,
            "orphan_enrolled": row_orphan is not None,
        }
    finally:
        db.close()


def force_due(user_id: int, item_ids: list[int] | None = None):
    from app.database import SessionLocal
    from app.models import KnowledgeReviewItem
    db = SessionLocal()
    try:
        q = db.query(KnowledgeReviewItem).filter_by(user_id=user_id, status="active")
        if item_ids is not None:
            q = q.filter(KnowledgeReviewItem.id.in_(item_ids))
        rows = q.all()
        past = datetime.utcnow() - timedelta(hours=2)
        for r in rows:
            r.next_review_at = past
        db.commit()
        return [r.id for r in rows]
    finally:
        db.close()


def gen_tasks(user_id: int):
    from app.database import SessionLocal
    from app.services.task_gen import generate_tasks_for_user
    db = SessionLocal()
    try:
        generate_tasks_for_user(db, user_id, date.today())
        db.commit()
    finally:
        db.close()


def load_item(item_id: int):
    from app.database import SessionLocal
    from app.models import KnowledgeReviewItem
    db = SessionLocal()
    try:
        return db.get(KnowledgeReviewItem, item_id)
    finally:
        db.close()


def mastery_attempts(user_id: int, kp_id: int):
    from app.database import SessionLocal
    from app.models import KnowledgeMastery
    from app.services.bucket_service import ensure_bucket
    db = SessionLocal()
    try:
        bid = ensure_bucket(db, user_id).id
        m = db.query(KnowledgeMastery).filter_by(
            user_id=user_id, knowledge_point_id=kp_id, bucket_id=bid).first()
        if not m:
            return None
        try:
            return json.loads(m.attempts or "[]")
        except json.JSONDecodeError:
            return m.attempts
    finally:
        db.close()


def main():
    print(f"BASE={BASE}")
    code, _ = http("POST", "/api/auth/login", {"login_name": "__ping__", "password": "x"})
    check(code in (200, 401, 403, 404, 422), f"服务可达 HTTP={code}")

    ids = seed()
    ok(f"种子 child={ids['child_id']} item1={ids['item1']}")
    check(ids["item1"] is not None, "成功标准1：进度内达标 KP 自动入队")
    check(ids["orphan_enrolled"] is False, "边界：无 lesson_id 的 KP 永不入队")

    code, pl = http("POST", "/api/auth/login", {
        "login_name": "vfy_parent", "password": "Verify123",
    })
    check(code == 200 and bool(pl.get("access_token")), "家长登录")
    pt = pl["access_token"]
    code, cl = http("POST", "/api/auth/login", {
        "login_name": "vfy_child", "password": "Verify123",
    })
    check(code == 200 and bool(cl.get("access_token")), "孩子登录")
    ct = cl["access_token"]

    # 队列初始应只有第1课
    code, queue = http("GET", f"/api/knowledge-review/queue?user_id={ids['child_id']}", token=pt)
    check(code == 200, f"家长 queue HTTP={code}")
    q_items = queue.get("items") or []
    check(len(q_items) == 1 and q_items[0]["knowledge_point_id"] == ids["kp1"],
          f"初始队列仅 kp1（实际 {len(q_items)} 条）")

    # 进度前推到第3课 → 应补入 kp2+kp3
    code, adj = http("POST", "/api/progress/adjust", {
        "user_id": ids["child_id"], "lesson_id": ids["l3"],
        "document_id": ids["doc_id"], "subject": "语文",
    }, token=pt)
    check(code == 200 and adj.get("review_enrolled_count") == 2,
          f"成功标准1/验收2：前推到第3课 enrolled={adj.get('review_enrolled_count')}")

    code, queue2 = http("GET", f"/api/knowledge-review/queue?user_id={ids['child_id']}", token=pt)
    kps_in_q = {x["knowledge_point_id"] for x in (queue2.get("items") or [])}
    check(kps_in_q == {ids["kp1"], ids["kp2"], ids["kp3"]},
          f"前推后队列含三课 KP（实际 {kps_in_q}）")

    # 进度调回第1课 → 队列不减
    code, adj_back = http("POST", "/api/progress/adjust", {
        "user_id": ids["child_id"], "lesson_id": ids["l1"],
        "document_id": ids["doc_id"], "subject": "语文",
    }, token=pt)
    check(code == 200 and adj_back.get("review_enrolled_count") == 0,
          f"验收2：调回 enrolled=0（实际 {adj_back.get('review_enrolled_count')}）")
    code, queue3 = http("GET", f"/api/knowledge-review/queue?user_id={ids['child_id']}", token=pt)
    check(len(queue3.get("items") or []) == 3, "验收2：调回后队列不减仍为 3")

    # 拨到期 → 生成 kp_review，并与 review/dictation 可并存
    due_ids = force_due(ids["child_id"])
    ok(f"拨到期 item_ids={due_ids}")
    gen_tasks(ids["child_id"])

    today = date.today().isoformat()
    tq = urllib.parse.urlencode({"user_id": ids["child_id"], "date": today})
    code, tasks = http("GET", f"/api/tasks?{tq}", token=ct)
    check(code == 200, f"GET /api/tasks HTTP={code}")
    task_list = tasks if isinstance(tasks, list) else tasks.get("tasks") or tasks.get("items") or []

    types = {t.get("task_type") for t in task_list if isinstance(t, dict)}
    kp_tasks = [t for t in task_list if isinstance(t, dict) and t.get("task_type") == "kp_review"]
    check(len(kp_tasks) >= 1, f"成功标准3/验收3：存在 kp_review（types={types}）")

    # /due 与任务快照选集一致（同科）
    due_q = urllib.parse.urlencode({"user_id": ids["child_id"], "subject": "语文"})
    code, due = http("GET", f"/api/knowledge-review/due?{due_q}", token=ct)
    check(code == 200 and len(due.get("items") or []) >= 1,
          f"/due 非空 HTTP={code} n={len(due.get('items') or [])}")
    due_item_ids = [x["item_id"] for x in (due.get("items") or [])]
    if kp_tasks:
        try:
            snap = json.loads(kp_tasks[0].get("content") or "[]")
        except json.JSONDecodeError:
            snap = []
        snap_ids = [x.get("item_id") for x in snap if isinstance(x, dict)]
        check(set(snap_ids) == set(due_item_ids),
              f"成功标准3：task 快照与 /due 一致 snap={snap_ids} due={due_item_ids}")
        # 题目不下发答案
        leaked = any(
            ("answer" in (x.get("prompt") or {}) and (x.get("prompt") or {}).get("answer"))
            for x in (due.get("items") or [])
        )
        check(not leaked, "题目载荷不泄露标准答案")

    # 三档：remember 升档；fuzzy 保持；forgot 回 0
    # 取三条分别测（若不足则复用）
    items_for_grade = due.get("items") or []
    if len(items_for_grade) < 3:
        # 重新 due 前把已 complete 的拨回去会幂等挡住；用队列里未测的
        from app.database import SessionLocal
        from app.models import KnowledgeReviewItem
        db = SessionLocal()
        try:
            rows = db.query(KnowledgeReviewItem).filter_by(
                user_id=ids["child_id"], status="active").order_by(KnowledgeReviewItem.id).all()
            for r in rows:
                r.next_review_at = datetime.utcnow() - timedelta(hours=1)
                r.last_result = ""
                r.updated_at = datetime.utcnow() - timedelta(days=1)
            db.commit()
            items_for_grade = [
                {"item_id": r.id, "knowledge_point_id": r.knowledge_point_id,
                 "prompt": {"source": "self_rate"}}
                for r in rows
            ]
        finally:
            db.close()

    # remember
    it_r = items_for_grade[0]
    before = load_item(it_r["item_id"])
    code, done_r = http("POST", "/api/knowledge-review/complete", {
        "user_id": ids["child_id"], "item_id": it_r["item_id"],
        "result": "remember", "duration_ms": 800,
    }, token=ct)
    after = load_item(it_r["item_id"])
    check(code == 200 and after.interval_index == before.interval_index + 1,
          f"验收4：remember 升档 {before.interval_index}→{after.interval_index}")
    att_before = mastery_attempts(ids["child_id"], it_r["knowledge_point_id"])

    # 同日幂等
    code, done_r2 = http("POST", "/api/knowledge-review/complete", {
        "user_id": ids["child_id"], "item_id": it_r["item_id"], "result": "forgot",
    }, token=ct)
    after2 = load_item(it_r["item_id"])
    check(code == 200 and done_r2.get("already_completed") is True
          and after2.interval_index == after.interval_index,
          "同日 complete 幂等（第二次 forgot 不降档）")
    att_after = mastery_attempts(ids["child_id"], it_r["knowledge_point_id"])
    check(att_before == att_after, "纯自评不改 mastery.attempts")

    # fuzzy / forgot on other items
    from app.database import SessionLocal
    from app.models import KnowledgeReviewItem, Task

    if len(items_for_grade) >= 2:
        it_f = items_for_grade[1]
        db = SessionLocal()
        try:
            row = db.get(KnowledgeReviewItem, it_f["item_id"])
            row.last_result = ""
            row.updated_at = datetime.utcnow() - timedelta(days=1)
            row.interval_index = 2
            db.commit()
            idx0 = 2
        finally:
            db.close()
        code, _ = http("POST", "/api/knowledge-review/complete", {
            "user_id": ids["child_id"], "item_id": it_f["item_id"], "result": "fuzzy",
        }, token=ct)
        a = load_item(it_f["item_id"])
        check(code == 200 and a.interval_index == idx0, f"fuzzy 保持档位={a.interval_index}")

    if len(items_for_grade) >= 3:
        it_g = items_for_grade[2]
        db = SessionLocal()
        try:
            row = db.get(KnowledgeReviewItem, it_g["item_id"])
            row.last_result = ""
            row.updated_at = datetime.utcnow() - timedelta(days=1)
            row.interval_index = 3
            db.commit()
        finally:
            db.close()
        code, done_g = http("POST", "/api/knowledge-review/complete", {
            "user_id": ids["child_id"], "item_id": it_g["item_id"], "result": "forgot",
        }, token=ct)
        a = load_item(it_g["item_id"])
        check(code == 200 and a.interval_index == 0,
              f"forgot 回档0（实际 {a.interval_index}） result={done_g.get('result')}")

    # 暂停一项 → 不在 due；任务可结案
    db = SessionLocal()
    try:
        active = db.query(KnowledgeReviewItem).filter_by(
            user_id=ids["child_id"], status="active").all()
        for r in active:
            r.next_review_at = datetime.utcnow() - timedelta(hours=1)
            r.last_result = ""
            r.updated_at = datetime.utcnow() - timedelta(days=1)
        db.commit()
        pause_id = active[0].id if active else None
        other_ids = [r.id for r in active[1:]]
    finally:
        db.close()

    if pause_id is not None:
        nxt_before = load_item(pause_id).next_review_at
        code, paused = http("POST", f"/api/knowledge-review/item/{pause_id}/pause", {}, token=pt)
        check(code == 200 and paused.get("status") == "paused", "成功标准2：pause")
        nxt_after = load_item(pause_id).next_review_at
        check(nxt_before == nxt_after, "暂停冻结 next_review_at")

        code, due2 = http("GET", f"/api/knowledge-review/due?{due_q}", token=ct)
        due2_ids = [x["item_id"] for x in (due2.get("items") or [])]
        check(pause_id not in due2_ids, "暂停项不进 /due")

        # 其余项 complete 完 + 暂停 → 任务 approved
        for iid in other_ids:
            http("POST", "/api/knowledge-review/complete", {
                "user_id": ids["child_id"], "item_id": iid, "result": "remember",
            }, token=ct)
        # 若快照含 pause_id，pause 本身应触发 settle
        db = SessionLocal()
        try:
            t = db.query(Task).filter_by(
                user_id=ids["child_id"], task_type="kp_review", date=date.today(),
            ).first()
            # 若今日任务快照含 pause 项，应已结案；否则至少 pause HTTP 成功
            if t is not None:
                # 主动再结算一次（complete/pause 路径已调）
                from app.services.knowledge_review import maybe_settle_kp_review_task
                maybe_settle_kp_review_task(db, ids["child_id"], "语文")
                db.refresh(t)
                check(t.submit_status == "approved",
                      f"验收5：暂停后任务可结案 status={t.submit_status}")
            else:
                ok("无当日 kp_review 任务（跳过结案断言）")
        finally:
            db.close()

        code, resumed = http("POST", f"/api/knowledge-review/item/{pause_id}/resume", {}, token=pt)
        check(code == 200 and resumed.get("status") == "active", "成功标准2：resume")

    # 权限：孩子不能看 queue；外人不能代 complete
    code, _ = http("GET", f"/api/knowledge-review/queue?user_id={ids['child_id']}", token=ct)
    check(code == 403, f"孩子看 queue → 403（实际 {code}）")

    print()
    if FAILS:
        print(f"DEEP VERIFY FAIL ({len(FAILS)})")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    print("DEEP VERIFY PASS")


if __name__ == "__main__":
    main()
