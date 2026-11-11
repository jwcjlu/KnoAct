# 基础知识出题取知识点重写 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `_gen_knowledge` 从「当前课按 id 盲取前 5 + 旧课到期（默认 0）」改为「已学课范围 + 无限循环（到期/错/新/轮转四档 + 内置护栏）」。

**Architecture:** 仅重写 `task_gen.py::_gen_knowledge` 的取知识点部分：候选池 = 孩子绑定教材下「当前课及之前」所有 `approved` 课的知识点，按四档优先级 + 内置护栏填充，选中后仍交给现有 `generate_knowledge_questions` 出题。出题、判分、配置键、UI 均不动。

**Tech Stack:** FastAPI + SQLAlchemy（pytest）。

**测试命令**：`cd backend && python -m pytest tests/test_task_gen.py -v`（用 Bash 的 python）。

---

## 文件结构

- **修改** `backend/app/services/task_gen.py` — 重写 `_gen_knowledge`；`generate_tasks_for_user` 的 `_gen_knowledge` 调用去掉硬编码 `5`。
- **测试** `backend/tests/test_task_gen.py` — 新增/更新知识点取词测试。

---

## 任务 1：重写 `_gen_knowledge` 取知识点

**Files:**
- Modify: `backend/app/services/task_gen.py`
- Test: `backend/tests/test_task_gen.py`

### 前置：`KnowledgeMastery` 字段确认

`KnowledgeMastery`（`models.py:283`）字段：`user_id`、`bucket_id`、`knowledge_point_id`、`attempts`（JSON `[true,false,...]`）、`mastery`（float）、`mastered`（bool）、`next_review_at`、`updated_at`。**无 `mistake_count`** ——「错」档用 `attempts` 末位 `False` 近似。

### 现有 `_gen_knowledge`（task_gen.py:133-171）

签名 `_gen_knowledge(db, lesson, user_id, count, new_ratio=5, bucket_id=None)`，被 `generate_tasks_for_user` 在 task_gen.py:357 调用：`_gen_knowledge(db, lesson, user_id, n_know, 5, bucket.id)`。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_task_gen.py` 顶部 import 已含 `KnowledgePoint`、`KnowledgeMastery`（确认 `KnowledgeMastery` 已在 import 列表；若没有则加到第 5 行的 import 里）。

追加 helper 与测试到文件末尾：

```python
def _add_kps(db, lesson, contents):
    for c in contents:
        db.add(KnowledgePoint(subject=lesson.subject, category="字词", content=c, lesson_id=lesson.id))
    db.flush()


def test_knowledge_unlearned_lesson_excluded():
    """未学课（id>当前课）的知识点不进池。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 第1课，含 1 个知识点「形近字辨析」
    doc = db.query(PdfDocument).first()
    l2 = Lesson(document_id=doc.id, subject="语文", title="第2课",
                start_page=3, end_page=4, extract_status="done", audit_status="approved")
    db.add(l2); db.flush()
    _add_kps(db, l2, ["未学课知识点"])
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="knowledge").first()
    assert t is not None
    qs = json.loads(t.content)
    contents = {q.get("content") for q in qs}
    assert "未学课知识点" not in contents
    assert "形近字辨析" in contents
    db.close()


def test_knowledge_rotation_includes_mastered():
    """无限循环：mastered=True 的知识点在轮转档回来（不因已掌握消失）。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 第1课 1 个知识点「形近字辨析」
    kp = db.query(KnowledgePoint).filter_by(lesson_id=l1_id).first()
    db.add(KnowledgeMastery(user_id=uid, knowledge_point_id=kp.id,
                            attempts=json.dumps([True, True]),
                            mastery=0.95, mastered=True,
                            next_review_at=datetime.utcnow() + timedelta(days=30)))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="knowledge").first()
    # 只有这一个知识点，虽已掌握也应进（轮转档）
    assert t is not None
    qs = json.loads(t.content)
    assert len(qs) == 1
    db.close()


def test_knowledge_due_priority_over_new():
    """到期知识点优先于新知识点（到期档先填）。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 第1课 1 个知识点「形近字辨析」
    # 追加 2 个新知识点 + 1 个到期知识点
    _add_kps(db, db.query(Lesson).filter_by(id=l1_id).first(), ["新点A", "新点B"])
    due_kp = KnowledgePoint(subject="语文", category="字词", content="到期点", lesson_id=l1_id)
    db.add(due_kp); db.flush()
    db.add(KnowledgeMastery(user_id=uid, knowledge_point_id=due_kp.id,
                            attempts=json.dumps([False]),
                            mastery=0.1, mastered=False,
                            next_review_at=datetime.utcnow() - timedelta(days=1)))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="knowledge").first()
    assert t is not None
    qs = json.loads(t.content)
    contents = [q.get("content") for q in qs]
    # 到期点必在（优先级最高）
    assert "到期点" in contents
    db.close()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_task_gen.py::test_knowledge_unlearned_lesson_excluded tests/test_task_gen.py::test_knowledge_rotation_includes_mastered tests/test_task_gen.py::test_knowledge_due_priority_over_new -v`
Expected: FAIL（旧 `_gen_knowledge` 只取当前课 `limit(new_ratio=5)` 的新知识点；`test_knowledge_unlearned_lesson_excluded` 中第2课不取、但「形近字辨析」在；`test_knowledge_rotation_includes_mastered` 旧逻辑已掌握知识点仍在新课档会取到但语义不同；`test_knowledge_due_priority_over_new` 旧逻辑 `new_pts` 按 id 排序取前5，「到期点」id 最大可能排不进前5 → 断言失败）。

- [ ] **Step 3: 实现**

替换 `backend/app/services/task_gen.py` 的 `_gen_knowledge`（第 133-171 行整段）为：

```python
def _gen_knowledge(db, lesson, user_id, count, bucket_id=None):
    """按「已学课范围 + 无限循环」取知识点：
    - 候选池：绑定教材下、approved、subject 匹配、id <= 当前课的全部知识点。
    - 四档优先级：到期 -> 错 -> 新 -> 轮转。
      - 到期（next_review_at<=now）+ 错（最近一次答错、未到期）合计受 ceil(count/2) 上限。
      - 新（无 KnowledgeMastery 或 attempts 空）至少 1 个。
      - 轮转（其余，含 mastered）按最久没考补满 count。
    - 已掌握永不移出（B2 无限循环）。
    """
    import math
    subject = lesson.subject
    now = datetime.utcnow()

    bound_doc_ids = [r[0] for r in db.query(UserDocument.document_id).filter_by(user_id=user_id).all()]
    lesson_ids = [r[0] for r in db.query(Lesson.id).filter(
        Lesson.subject == subject,
        Lesson.document_id.in_(bound_doc_ids),
        Lesson.audit_status == "approved",
        Lesson.id <= lesson.id).all()]
    if not lesson_ids:
        return None

    points = (db.query(KnowledgePoint)
              .filter(KnowledgePoint.lesson_id.in_(lesson_ids))
              .order_by(KnowledgePoint.id).all())
    if not points:
        return None

    mrows = {m.knowledge_point_id: m for m in db.query(KnowledgeMastery).filter(
        KnowledgeMastery.user_id == user_id,
        KnowledgeMastery.knowledge_point_id.in_([p.id for p in points])).all()}

    def _m(p):
        return mrows.get(p.id)

    def _attempts(p):
        m = _m(p)
        if m is None:
            return []
        try:
            a = json.loads(m.attempts or "[]")
            return a if isinstance(a, list) else []
        except (ValueError, TypeError):
            return []

    def _is_new(p):
        return not _attempts(p)

    def _is_due(p):
        m = _m(p)
        return bool(m and m.next_review_at and m.next_review_at <= now)

    def _is_mistaken(p):
        a = _attempts(p)
        return bool(a and a[-1] is False and not _is_due(p))

    review_n = int(math.ceil(count / 2))
    new_n = max(1, count - review_n)

    due_pts = sorted((p for p in points if _is_due(p)),
                     key=lambda p: _m(p).next_review_at)[:review_n]
    picked = list(due_pts)
    if len(picked) < review_n:
        mistaken = [p for p in points if _is_mistaken(p) and p.id not in {x.id for x in picked}]
        picked += mistaken[:review_n - len(picked)]

    picked_ids = {p.id for p in picked}
    new_pts = [p for p in points if _is_new(p) and p.id not in picked_ids][:new_n]
    picked += new_pts
    picked_ids = {p.id for p in picked}

    if len(picked) < count:
        def _last_review(p):
            m = _m(p)
            return m.next_review_at or now
        rotation = sorted((p for p in points
                           if p.id not in picked_ids
                           and not _is_new(p)
                           and not _is_due(p)
                           and not _is_mistaken(p)),
                          key=_last_review)
        picked += rotation[:count - len(picked)]

    picked = picked[:count]
    if not picked:
        return None

    from .knowledge_quiz import generate_knowledge_questions
    from ..models import Question
    raw = [{"id": p.id, "content": p.content, "category": p.category} for p in picked]
    qs = generate_knowledge_questions(db, raw, subject)
    for item in qs:
        db.add(Question(
            lesson_id=lesson.id, qtype="knowledge",
            question=item.get("question") or item.get("content") or "",
            answer=item.get("answer") or "",
            subject=subject, date=datetime.utcnow().date(),
            status="pending", task_type="knowledge",
            user_id=user_id, bucket_id=bucket_id,
            extra=json.dumps({"keywords": item.get("keywords") or [], "content": item.get("content") or ""}, ensure_ascii=False),
        ))
    n_due = len(due_pts)
    n_mist = len([p for p in picked if _is_mistaken(p)])
    n_new = len(new_pts)
    n_rot = len(picked) - n_due - n_mist - n_new
    return Task(
        task_type="knowledge", subject=subject, title=f"{lesson.title} 基础知识",
        detail=f"重点巩固 · {len(picked)} 个知识点（到期 {n_due} + 错 {n_mist} + 新课 {n_new} + 轮转 {n_rot}）",
        content=json.dumps(qs, ensure_ascii=False),
        points=20,
    )
```

注意：原函数签名是 `_gen_knowledge(db, lesson, user_id, count, new_ratio=5, bucket_id=None)`。改成 `_gen_knowledge(db, lesson, user_id, count, bucket_id=None)`，并同步更新调用处（见 Step 4）。

- [ ] **Step 4: 更新调用处**

在 `generate_tasks_for_user`（task_gen.py:357）把：

```python
                _gen_knowledge(db, lesson, user_id, n_know, 5, bucket.id),
```

改为：

```python
                _gen_knowledge(db, lesson, user_id, n_know, bucket.id),
```

（`n_know = _default_count(db, "task_knowledge_count", 5, child_id=user_id)` 已在 task_gen.py:352，无需改动。）

- [ ] **Step 5: 跑新测试 + 全量 task_gen 回归**

Run: `cd backend && python -m pytest tests/test_task_gen.py -v`
Expected: 新增 3 个测试 PASS；既有 `test_gen_knowledge_content_has_question_fields`、`test_generated_questions_land_in_question_table` 等知识点测试应仍 PASS（fake provider 下题目空字符串、字段存在，取点逻辑改变不影响这些断言）。若有失败，读失败原因，按新算法语义修正断言，不改变算法意图。

- [ ] **Step 6: 全量后端回归**

Run: `cd backend && python -m pytest tests/ -q 2>&1 | tail -5`
Expected: 全部 PASS（约 482+ 个）。

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/task_gen.py backend/tests/test_task_gen.py
git commit -m "feat(knowledge): pick points within learned lessons with rotation"
```

---

## Self-Review

**Spec coverage：**
- 取知识点算法（已学课范围 + 四档 + 护栏）→ 任务 1 ✓
- 「错」档用 `attempts` 末位 False → 任务 1 `_is_mistaken` ✓
- 无限循环（mastered 不排除）→ 任务 1 `_is_mistaken`/rotation 无 mastered 过滤 ✓
- 出题/判分/配置/UI 不动 → 任务 1 只改 `_gen_knowledge` + 调用处 ✓

**Placeholder scan：** 无 TBD/TODO；所有代码步骤含完整代码。

**Type consistency：**
- `_gen_knowledge(db, lesson, user_id, count, bucket_id=None)` 签名在 Step 3 定义，Step 4 调用处一致 ✓
- `KnowledgeMastery` 无 `mistake_count`，「错」档只用 `attempts`（Step 3 `_attempts`/`_is_mistaken`）✓

**已知风险：** `test_knowledge_due_priority_over_new` 里「到期点」的 `KnowledgePoint.id` 是追加后最大的；旧算法 `new_pts` 按 id 升序取前 5，若第1课知识点总数 ≤ 5 则「到期点」也会进 `new_pts`（旧算法不区分到期/新），断言「到期点 in contents」可能旧代码就通过。为让失败更明确，`test_knowledge_unlearned_lesson_excluded` 与 `test_knowledge_rotation_includes_mastered` 才是决定性的失败点（旧算法对 mastered 知识点无轮转语义、对未学课也不取）。执行时以实际失败为准，若某测试旧代码就通过，改为构造能暴露差异的场景（如让到期点 id 排在 new_ratio 之后）。
