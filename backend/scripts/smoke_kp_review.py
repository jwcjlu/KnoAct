"""真服务冒烟：知识点复习 SRS API。

用法（先起 uvicorn 指向同一 DB）：
  set DATABASE_URL=sqlite:///./smoke_kp_review.db
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8011
  python scripts/smoke_kp_review.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# 允许从 scripts/ 直接跑时 import app.*
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011"


def http(method: str, path: str, body: dict | None = None, token: str | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return e.code, payload


def fail(msg: str):
    print(f"FAIL: {msg}")
    sys.exit(1)


def ok(msg: str):
    print(f"OK  {msg}")


def seed_db():
    """直接写库：家长/孩子/课/知识点/进度/掌握度。"""
    import os

    # 与服务端同一相对路径：必须在 backend/ 下跑
    os.environ.setdefault("DATABASE_URL", "sqlite:///./smoke_kp_review.db")

    from app.database import SessionLocal, engine, Base
    from app.models import (
        User, PdfDocument, Lesson, KnowledgePoint, LearningProgress,
        KnowledgeMastery, UserDocument, KnowledgeReviewItem,
    )
    from app.services.security import hash_password
    from app.services.bucket_service import ensure_bucket
    from app.schema_sync import sync_schema

    sync_schema(engine, Base.metadata)
    db = SessionLocal()
    try:
        # 清掉上次冒烟数据（按 login_name）
        for name in ("smoke_parent", "smoke_child"):
            u = db.query(User).filter_by(login_name=name).first()
            if u:
                db.query(KnowledgeReviewItem).filter_by(user_id=u.id).delete()
                db.query(KnowledgeMastery).filter_by(user_id=u.id).delete()
                db.query(LearningProgress).filter_by(user_id=u.id).delete()
                db.query(UserDocument).filter_by(user_id=u.id).delete()
                db.delete(u)
        db.commit()

        parent = User(
            name="冒烟家长", login_name="smoke_parent", display_name="冒烟家长",
            role="parent", password_hash=hash_password("Smoke123"),
        )
        db.add(parent)
        db.flush()
        child = User(
            name="冒烟孩子", login_name="smoke_child", display_name="冒烟孩子",
            role="child", parent_id=parent.id, password_hash=hash_password("Smoke123"),
        )
        db.add(child)
        db.flush()
        bucket = ensure_bucket(db, child.id)

        doc = PdfDocument(filename="smoke.pdf", subject="语文", storage_path="")
        db.add(doc)
        db.flush()
        l1 = Lesson(
            document_id=doc.id, subject="语文", title="第1课", start_page=1, end_page=2,
            extract_status="done", audit_status="approved",
        )
        l2 = Lesson(
            document_id=doc.id, subject="语文", title="第2课", start_page=3, end_page=4,
            extract_status="done", audit_status="approved",
        )
        db.add_all([l1, l2])
        db.flush()
        kp1 = KnowledgePoint(lesson_id=l1.id, subject="语文", category="修辞", content="比喻：本体+比喻词+喻体")
        kp2 = KnowledgePoint(lesson_id=l2.id, subject="语文", category="修辞", content="拟人：把物当人写")
        db.add_all([kp1, kp2])
        db.flush()

        db.add(UserDocument(user_id=child.id, document_id=doc.id))
        db.add(LearningProgress(
            user_id=child.id, document_id=doc.id, subject="语文", current_lesson_id=l1.id,
        ))
        db.add(KnowledgeMastery(
            user_id=child.id, knowledge_point_id=kp1.id, bucket_id=bucket.id,
            mastery=0.95, mastered=True, attempts=json.dumps([True, True, True]),
        ))
        db.add(KnowledgeMastery(
            user_id=child.id, knowledge_point_id=kp2.id, bucket_id=bucket.id,
            mastery=0.95, mastered=True, attempts=json.dumps([True, True, True]),
        ))
        db.flush()
        from app.services.knowledge_review import try_enroll
        # 进度在第1课：kp1 应可入队
        try_enroll(db, child.id, kp1.id, source="mastery")
        db.commit()
        return {
            "parent_id": parent.id,
            "child_id": child.id,
            "doc_id": doc.id,
            "l1_id": l1.id,
            "l2_id": l2.id,
            "kp1_id": kp1.id,
            "kp2_id": kp2.id,
        }
    finally:
        db.close()


def main():
    print(f"BASE={BASE}")
    code, health = http("GET", "/api/auth/me")  # may 401
    # 探测服务
    code, _ = http("POST", "/api/auth/login", {"login_name": "__ping__", "password": "x"})
    if code not in (200, 401, 403, 404, 422):
        fail(f"服务不可达 HTTP {code}")
    ok("服务可达")

    ids = seed_db()
    ok(f"种子写入 child={ids['child_id']} kp1={ids['kp1_id']} kp2={ids['kp2_id']}")

    code, parent_login = http("POST", "/api/auth/login", {
        "login_name": "smoke_parent", "password": "Smoke123",
    })
    if code != 200 or not parent_login.get("access_token"):
        fail(f"家长登录失败 {code} {parent_login}")
    pt = parent_login["access_token"]
    ok("家长登录")

    code, child_login = http("POST", "/api/auth/login", {
        "login_name": "smoke_child", "password": "Smoke123",
    })
    if code != 200 or not child_login.get("access_token"):
        fail(f"孩子登录失败 {code} {child_login}")
    ct = child_login["access_token"]
    ok("孩子登录")

    # 进度内达标 → 应能通过 adjust 前推补齐 / 或手动触发 try_enroll 已在 seed 后
    # seed 时进度在 l1，kp1 应可入队：用 progress adjust 推到 l1 触发补齐（old=l1 new=l1 可能 0）
    # 先用孩子做一次 mastery 路径：直接调 progress adjust 到 l2 应入队 kp2
    code, adj = http("POST", "/api/progress/adjust", {
        "user_id": ids["child_id"],
        "lesson_id": ids["l2_id"],
        "document_id": ids["doc_id"],
        "subject": "语文",
    }, token=pt)
    if code != 200:
        fail(f"progress/adjust 失败 {code} {adj}")
    n = adj.get("review_enrolled_count", 0)
    ok(f"进度前推到第2课 review_enrolled_count={n}")
    if n < 1:
        fail("前推应至少入队 kp2（已掌握）")

    code, queue = http("GET", f"/api/knowledge-review/queue?user_id={ids['child_id']}", token=pt)
    if code != 200:
        fail(f"queue 失败 {code} {queue}")
    items = queue.get("items") or queue.get("queue") or []
    if isinstance(queue, dict) and "items" not in queue and "queue" not in queue:
        # 可能直接返回 list 包在其它键
        items = queue.get("items")
        if items is None:
            # 尝试顶层 list
            fail(f"queue 响应结构异常: {list(queue.keys())} {queue}")
    ok(f"队列 items={len(items)} due_today={queue.get('due_today')} due_week={queue.get('due_this_week')}")
    if len(items) < 1:
        fail("队列应有至少 1 条")

    # 把一条 next_review_at 改到过去，便于 due
    from app.database import SessionLocal
    from app.models import KnowledgeReviewItem
    db = SessionLocal()
    try:
        rows = db.query(KnowledgeReviewItem).filter_by(
            user_id=ids["child_id"], status="active").all()
        for r in rows:
            r.next_review_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()
        item_id = rows[0].id
        subject = "语文"
    finally:
        db.close()
    ok(f"已把 {len(rows)} 条 next_review_at 拨到过去 item_id={item_id}")

    due_q = urllib.parse.urlencode({"user_id": ids["child_id"], "subject": "语文"})
    code, due = http("GET", f"/api/knowledge-review/due?{due_q}", token=ct)
    if code != 200:
        fail(f"due 失败 {code} {due}")
    due_items = due.get("items") or due if isinstance(due, list) else due.get("items", [])
    if isinstance(due, dict):
        due_items = due.get("items") or []
    ok(f"due items={len(due_items)}")
    if not due_items:
        fail("due 应非空")

    first = due_items[0]
    code, done = http("POST", "/api/knowledge-review/complete", {
        "user_id": ids["child_id"],
        "item_id": first["item_id"],
        "result": "remember",
        "duration_ms": 1200,
    }, token=ct)
    if code != 200:
        fail(f"complete 失败 {code} {done}")
    ok(f"complete remember → interval={done.get('interval_index')} next={done.get('next_review_at')}")

    code, done2 = http("POST", "/api/knowledge-review/complete", {
        "user_id": ids["child_id"],
        "item_id": first["item_id"],
        "result": "forgot",
    }, token=ct)
    if code != 200:
        fail(f"幂等 complete 失败 {code} {done2}")
    if done2.get("already_completed") is not True and done2.get("interval_index") != done.get("interval_index"):
        # 允许返回 already_completed 或保持档位
        fail(f"同日二次 complete 应幂等: {done2}")
    ok("同日 complete 幂等")

    # pause
    code, paused = http("POST", f"/api/knowledge-review/item/{item_id}/pause", {}, token=pt)
    # some routes may not need body
    if code not in (200, 204):
        # try without body via GET-style — already posted
        fail(f"pause 失败 {code} {paused}")
    ok("pause")

    code, bad = http("POST", "/api/knowledge-review/complete", {
        "user_id": ids["child_id"],
        "item_id": item_id,
        "result": "remember",
    }, token=ct)
    if code != 400:
        fail(f"paused complete 应得 400，实际 {code} {bad}")
    ok("paused complete → 400")

    print("\nSMOKE PASS")


if __name__ == "__main__":
    main()
