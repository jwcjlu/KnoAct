# 知识点复习模块（遗忘曲线 SRS）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在学习进度范围内，已达标知识点自动进入独立复习队列，按 `INTERVALS` 到期；家长可调进度（前推补齐）与暂停/移出；孩子在每日 `kp_review` 任务与独立模块中完成轻量自测复习。

**Architecture:** 新表 `knowledge_review_items` 与 `KnowledgeMastery` 解耦；`knowledge_review` 服务负责 `try_enroll` / 进度补齐 / 三档调度 / due 选集；挂钩 `record_attempt` 与 `/api/progress/adjust|advance`；`task_gen` 按科生成 `published` 的 `kp_review` 快照；parent-web 队列页 + 进度 toast；Flutter 新 feature `kp_srs`。

**Tech Stack:** FastAPI + SQLAlchemy、pytest、parent-web 原生 JS、Flutter + Riverpod + go_router

**依据 spec:** `docs/superpowers/specs/2026-11-27-knowledge-review-srs-design.md`

**建议 worktree:** 从当前 master 开 `feature/knowledge-review-srs` 再执行（本计划写在主仓 docs，实现勿直接堆在未隔离分支上乱改）。

---

## 设计约束（实现时不可违反）

| 约束 | 原因 |
|------|------|
| 不手选入队作为家长主路径 | spec：自动 + 进度前推 |
| 进度往后调不自动移出 | 已锁定 |
| `kp_review` 生成时 `content_status=published` | 否则孩子 list_tasks 看不见 |
| 纯自评不改 mastery；带 `question_id` 才 `record_attempt` | 防刷掌握度 |
| 完成文案不写「已掌握/已理解」 | 原料巩固，不得宣称理解 |
| `/due` 与 `task_gen` 共用同一选集函数 | 双入口一致 |
| 不新增 `Question.knowledge_point_id` FK | 用 `extra` JSON 存 id |

---

## File Structure

| 文件 | 职责 | 动作 |
|------|------|------|
| `backend/app/models.py` | `KnowledgeReviewItem` | Modify |
| `backend/app/services/knowledge_review.py` | 入队/进度/间隔/due/complete/结案 | Create |
| `backend/app/services/mastery.py` | `record_attempt` 后 try_enroll | Modify |
| `backend/app/routers/progress.py` | adjust/advance 挂钩补齐 | Modify |
| `backend/app/routers/knowledge_review.py` | queue/pause/resume/remove/due/complete | Create |
| `backend/app/main.py` | include_router | Modify |
| `backend/app/services/task_gen.py` | `_gen_kp_review` + 按 type 幂等 | Modify |
| `backend/app/services/cleanup.py` | 删课时处理队列项（若需要） | Modify |
| `backend/tests/test_knowledge_review.py` | 核心后端测试 | Create |
| `parent-web/app.js` | 复习队列 Tab + 进度 toast | Modify |
| `student-app/lib/features/kp_srs/**` | 仓库/控制器/页面 | Create |
| `student-app/lib/features/home/home_logic.dart` | `kp_review` TaskMeta | Modify |
| `student-app/lib/core/router.dart` | 路由 | Modify |
| `student-app/test/features/kp_srs/**` | smoke | Create |

---

### Task 1: 模型 `KnowledgeReviewItem`

**Files:**
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_knowledge_review.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_knowledge_review.py
from app.models import KnowledgeReviewItem

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
    names = {u.name for u in KnowledgeReviewItem.__table__.constraints
             if hasattr(u, "columns")}
    # 至少有一对 (user_id, knowledge_point_id, bucket_id) 唯一约束
    assert any(
        set(c.name for c in u.columns) >= {"user_id", "knowledge_point_id", "bucket_id"}
        for u in KnowledgeReviewItem.__table__.constraints
        if u.__class__.__name__ == "UniqueConstraint"
    )
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_knowledge_review.py::test_knowledge_review_item_columns -v`  
Expected: FAIL（模型不存在）

- [ ] **Step 3: 实现模型**

在 `models.py` 合适位置（建议 `KnowledgeMastery` 附近）追加：

```python
class KnowledgeReviewItem(Base):
    __tablename__ = "knowledge_review_items"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "knowledge_point_id", "bucket_id",
            name="uq_kp_review_user_kp_bucket",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"))
    bucket_id: Mapped[int] = mapped_column(
        ForeignKey("school_year_buckets.id"), nullable=True)
    enrolled_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True)
    enroll_source: Mapped[str] = mapped_column(String(32), default="mastery")
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(16), default="active")
    interval_index: Mapped[int] = mapped_column(Integer, default=0)
    next_review_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_result: Mapped[str] = mapped_column(String(16), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

说明：SQLite 下 `bucket_id` 为 NULL 时唯一约束允许多行——入队时**必须**写入非空 `bucket_id`（与 spec 一致）。若测试库 create_all，重启/fixture 会建表。

- [ ] **Step 4: 测试通过并提交**

```bash
cd backend && python -m pytest tests/test_knowledge_review.py::test_knowledge_review_item_columns tests/test_knowledge_review.py::test_knowledge_review_item_unique_user_kp_bucket -v
git add backend/app/models.py backend/tests/test_knowledge_review.py
git commit -m "feat(models): add KnowledgeReviewItem for KP SRS queue"
```

---

### Task 2: `in_progress_scope` + `try_enroll`

**Files:**
- Create: `backend/app/services/knowledge_review.py`
- Test: `backend/tests/test_knowledge_review.py`

- [ ] **Step 1: 写失败测试**（用现有 conftest 的 db/user fixture 模式；若无则仿 `test_expression.py` / `test_task_gen.py`）

```python
from datetime import datetime, timedelta
from app.services.knowledge_review import try_enroll, in_progress_scope

def test_try_enroll_requires_mastery_and_progress(db, child, lesson_a, lesson_b, kp_on_a, bucket):
    # 进度停在 lesson_a；kp 在 lesson_a；无 mastery → 不入队
    assert try_enroll(db, child.id, kp_on_a.id, source="mastery") is None

def test_try_enroll_skips_ahead_of_progress(db, child, lesson_a, lesson_b, kp_on_b, mastery_ok, bucket):
    # 进度在 a，kp 在 b → 跳过
    assert try_enroll(db, child.id, kp_on_b.id, source="mastery") is None

def test_try_enroll_success_when_mastered_in_scope(db, child, lesson_a, kp_on_a, mastery_ok, bucket):
    item = try_enroll(db, child.id, kp_on_a.id, source="mastery")
    assert item is not None
    assert item.status == "active"
    assert item.interval_index == 0
    assert item.next_review_at.date() == (datetime.utcnow() + timedelta(days=1)).date()
```

测试夹具自行用 `LearningProgress` / `KnowledgeMastery(mastered=True, mastery=0.95, bucket_id=...)` 搭；保持最小。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_knowledge_review.py -k try_enroll -v`

- [ ] **Step 3: 实现**

`knowledge_review.py` 核心：

```python
def in_progress_scope(db, user_id: int, kp: KnowledgePoint) -> bool:
    if not kp.lesson_id:
        return False
    lesson = db.get(Lesson, kp.lesson_id)
    if not lesson:
        return False
    from .learning_progress import get_progress
    prog = get_progress(db, user_id, lesson.document_id, lesson.subject)
    if not prog or not prog.current_lesson_id:
        return False
    lessons = (db.query(Lesson)
               .filter_by(document_id=lesson.document_id, subject=lesson.subject)
               .order_by(Lesson.id).all())
    ids = [l.id for l in lessons]
    if lesson.id not in ids or prog.current_lesson_id not in ids:
        return False
    return ids.index(lesson.id) <= ids.index(prog.current_lesson_id)

def try_enroll(db, user_id, knowledge_point_id, *, enrolled_by=None, source="mastery"):
    from .bucket_guard import resolve_bucket_id
    bid = resolve_bucket_id(db, user_id, None)
    if bid is None:
        return None
    kp = db.get(KnowledgePoint, knowledge_point_id)
    if not kp or not in_progress_scope(db, user_id, kp):
        return None
    m = (db.query(KnowledgeMastery)
         .filter_by(user_id=user_id, knowledge_point_id=knowledge_point_id, bucket_id=bid)
         .first())
    if not m or not (m.mastered or m.mastery >= 0.9):
        return None
    row = (db.query(KnowledgeReviewItem)
           .filter_by(user_id=user_id, knowledge_point_id=knowledge_point_id, bucket_id=bid)
           .first())
    if row and row.status in ("active", "paused"):
        return None
    now = datetime.utcnow()
    if row is None:
        row = KnowledgeReviewItem(user_id=user_id, knowledge_point_id=knowledge_point_id, bucket_id=bid)
        db.add(row)
    row.status = "active"
    row.interval_index = 0
    row.next_review_at = now + timedelta(days=1)
    row.enrolled_by = enrolled_by
    row.enroll_source = source
    row.enrolled_at = now
    row.updated_at = now
    db.flush()
    return row
```

- [ ] **Step 4: 测试通过并提交**

```bash
git add backend/app/services/knowledge_review.py backend/tests/test_knowledge_review.py
git commit -m "feat(knowledge-review): try_enroll gated by mastery and progress"
```

---

### Task 3: 进度前推补齐 `enroll_due_to_progress`

**Files:**
- Modify: `backend/app/services/knowledge_review.py`
- Modify: `backend/app/routers/progress.py`
- Test: `backend/tests/test_knowledge_review.py`

- [ ] **Step 1: 写失败测试**

```python
def test_progress_forward_enrolls_mastered_in_new_range(...):
    # 进度 a→b；kp_on_b 已 mastery；调用 enroll_due_to_progress
    n = enroll_due_to_progress(db, child.id, document_id, subject,
                               old_lesson_id=lesson_a.id, new_lesson_id=lesson_b.id,
                               enrolled_by=parent.id)
    assert n == 1

def test_progress_backward_does_not_remove(...):
    # 已有队列项；b→a；n==0 且项仍 active
    ...
```

- [ ] **Step 2: 实现 `enroll_due_to_progress`**

- 算 old/new 下标；`new < old` → return 0  
- 取课序 ∈ (old, new]（old 空则 ≤ new）的 lesson ids  
- 查这些课的 KP，对每个 `try_enroll(..., source="progress_adjust", enrolled_by=...)`  
- 返回成功入队条数  

- [ ] **Step 3: 改 `progress.adjust`**

调整前记下 `old_lesson_id = prog.current_lesson_id`，写新课后：

```python
from ..services.knowledge_review import enroll_due_to_progress
n = enroll_due_to_progress(
    db, req.user_id, prog.document_id, lesson.subject,
    old_lesson_id=old_lesson_id, new_lesson_id=lesson.id,
    enrolled_by=user.id,
)
db.commit()
return {..., "review_enrolled_count": n}
```

`advance`：在 `advance_lesson` 前后取 old/new，passed 时同样调用（`enrolled_by=None` 可）。

- [ ] **Step 4: 测试 + 提交**

```bash
git commit -m "feat(knowledge-review): enroll on progress forward adjust"
```

---

### Task 4: 挂钩 `record_attempt` 自动入队

**Files:**
- Modify: `backend/app/services/mastery.py`
- Test: `backend/tests/test_knowledge_review.py`

- [ ] **Step 1: 测试** — 进度内 KP，连续答对使 `mastered`，调用 `record_attempt` 后队列出现一行。超进度则无。

- [ ] **Step 2: 在 `record_attempt` 末尾**（commit 前或后，保持与现网一致；建议 commit 前 flush 后）：

```python
if target_type == "knowledge" and (mastered or mastery >= 0.9):
    from .knowledge_review import try_enroll
    try_enroll(db, user_id, target_id, source="mastery")
```

注意：避免循环 import；函数内 import。纯自评 complete **不会**走这里改 mastery（见 Task 6）。

- [ ] **Step 3: 提交**

```bash
git commit -m "feat(mastery): auto-enroll KP into review queue when mastered in scope"
```

---

### Task 5: 三档间隔 `apply_review_result`

**Files:**
- Modify: `backend/app/services/knowledge_review.py`
- Test: `backend/tests/test_knowledge_review.py`

- [ ] **Step 1: 测试**

```python
def test_remember_increases_interval(...):
    # index 0 → remember → index 1, days=2
def test_fuzzy_keeps_index(...):
def test_forgot_resets_to_zero(...):
def test_idempotent_same_utc_day(...):
    # 第二次 apply 不升档
```

- [ ] **Step 2: 实现**

```python
from .scheduler import INTERVALS

def apply_review_result(db, item: KnowledgeReviewItem, result: str) -> KnowledgeReviewItem:
    now = datetime.utcnow()
    if item.last_result and item.updated_at and item.updated_at.date() == now.date():
        return item  # 幂等
    i = item.interval_index or 0
    if result == "remember":
        i = min(i + 1, len(INTERVALS) - 1)
        item.next_review_at = now + timedelta(days=INTERVALS[i])
    elif result == "fuzzy":
        item.next_review_at = now + timedelta(days=INTERVALS[i])
    else:  # forgot
        i = 0
        item.next_review_at = now + timedelta(days=1)
    item.interval_index = i
    item.last_result = result
    item.updated_at = now
    return item
```

- [ ] **Step 3: 提交**

```bash
git commit -m "feat(knowledge-review): three-grade SRS interval updates"
```

---

### Task 6: due 选集 + prompt 降级 + complete API

**Files:**
- Modify: `backend/app/services/knowledge_review.py`
- Create: `backend/app/routers/knowledge_review.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_knowledge_review.py`

命名约定：`serialize_due_item(db, user_id, item) -> dict` = §2.4 整条 JSON；其内部调用 `_build_prompt(db, user_id, kp) -> prompt dict`。`task_gen` 与 `/due` **只**调用 `serialize_due_item` / `select_due_items`。

- [ ] **Step 1: 实现 `select_due_items(db, user_id, subject=None) -> list[KnowledgeReviewItem]`**

- active + `next_review_at <= now` + 同 bucket  
- join KP，按 subject 分组，每组取 `get_child_config_int(..., "task_kp_review_count", 6)` 条  
- 排序：`next_review_at`, `interval_index`

- [ ] **Step 2: 实现 `_build_prompt` + `serialize_due_item`**

1. reuse：扫 `Question` 的 `extra`/`tags` 含该 kp id，有答案则用  
2. generated：`generate_knowledge_questions` 出 1 题并落库（`extra` 含 `knowledge_point_id`+`keywords`）；载荷不下发标准答案作权威  
3. self_rate：仅 content  

- [ ] **Step 3: 家长队列路由先挂上** — `GET /queue`（可附 `due_today`/`due_this_week`）、pause/resume/remove；`main.py` include。settle 可先 no-op stub。

- [ ] **Step 4: `complete_item` + `GET /due` + `POST /complete`**

- 校验 access、status==active  
- 若 `question_id`：读库判分 → 覆盖 result  
- `apply_review_result`；写 `AnswerRecord`；forgot → `Mistake`  
- 可判分时 `record_attempt`  
- 调 `maybe_settle_kp_review_task`（Task 7 实现实体）

鉴权对齐现网：孩子学习用户 + `ensure_user_access`；家长队列用 `require_role("parent","admin")`。

- [ ] **Step 5: 测试 due 上限、complete 覆盖自评、pause 后 complete 400、queue 列表**

- [ ] **Step 6: 提交**

```bash
git commit -m "feat(knowledge-review): due/complete APIs with prompt fallback"
```

---

### Task 7: `kp_review` 任务生成与结案

**Files:**
- Modify: `backend/app/services/task_gen.py`
- Modify: `backend/app/services/knowledge_review.py`（settle）
- Test: `backend/tests/test_knowledge_review.py` / 扩展 `test_task_gen.py`

- [ ] **Step 1: `_gen_kp_review(db, user_id, subject, day, bucket_id)`**

```python
def _gen_kp_review(db, user_id, subject, day, bucket_id):
    # serialize_due_item 与 Task 6 /due 共用
    from .knowledge_review import select_due_items, serialize_due_item
    exists = db.query(Task).filter_by(
        user_id=user_id, subject=subject, date=day, task_type="kp_review").first()
    if exists:
        return None
    items = select_due_items(db, user_id, subject=subject)
    if not items:
        return None
    payload = [serialize_due_item(db, user_id, it) for it in items]
    return Task(
        task_type="kp_review", subject=subject, title="知识点复习",
        detail=f"遗忘曲线 · {len(payload)} 个到期知识点",
        content=json.dumps(payload, ensure_ascii=False),
        points=25, content_status="published",
    )
```

- [ ] **Step 2: 改 `generate_tasks_for_user`**

现有逻辑「同科当日已有任意 Task 则 `continue`」会挡死 `kp_review`。改为：

```python
for subject in subjects:
    lesson = _current_lesson(...)
    exists_other = db.query(Task).filter(
        Task.user_id == user_id, Task.subject == subject, Task.date == day,
        Task.task_type != "kp_review",
    ).first()
    if not exists_other and lesson:
        # 原 gens 列表...
        ...
    # 无论是否已有听写等，都尝试 kp_review
    kr = _gen_kp_review(db, user_id, subject, day, bucket.id)
    if kr is not None:
        kr.user_id = user_id
        kr.date = day
        kr.bucket_id = bucket.id
        db.add(kr)
```

- [ ] **Step 3: `maybe_settle_kp_review_task(db, user_id, subject)`**

找当日该科 `kp_review` 且未 approved；解析 content 里每个 `item_id`：若均「今日已 complete（看 item.updated_at+last_result）或 status≠active」→ `submit_status=approved`。

- [ ] **Step 4: 测试** — 有 due 生成任务且 published；已有 dictation 时仍能生成 kp_review；pause 快照项后 settle 成功。

- [ ] **Step 5: 提交**

```bash
git commit -m "feat(task_gen): add kp_review daily tasks with settle rules"
```

---

### Task 8: parent-web 队列页 + 进度 toast

**Files:**
- Modify: `parent-web/app.js`
- Modify: `parent-web/index.html`（若 Tab 写在 HTML）

- [ ] **Step 1: 在 `PARENT_TABS` / 渲染分支增加「知识点复习」**（挂在孩子相关 Tab，需选中孩子）

- [ ] **Step 2: `loadKpReviewQueue` → `GET /api/knowledge-review/queue?user_id=`**

页面必须包含：

- 短说明：「复习列表随学习进度与掌握情况自动加入；往后调进度不会移出，需要请暂停或移出。」
- 统计：今日到期数、本周将到期数（queue 接口附带 `due_today` / `due_this_week`，或前端按 `next_review_at` 算）
- 表格：内容截断、学科、档位、下次到期、来源、pause/resume/remove

- [ ] **Step 3: 改 `adjustProgress`（或现有进度提交函数）**

读响应 `review_enrolled_count`，若 `>0` toast「已自动加入 M 个达标知识点到复习」。

- [ ] **Step 4: 手动浏览器冒烟**

- [ ] **Step 5: 提交**

```bash
git commit --trailer "Co-authored-by: Cursor <cursoragent@cursor.com>" -m "feat(parent-web): KP review queue panel and progress enroll toast"
```

---

### Task 9: Flutter `kp_srs` feature（双入口）

**Files:**
- Create: `student-app/lib/features/kp_srs/data/kp_srs_repository.dart`
- Create: `student-app/lib/features/kp_srs/kp_srs_controller.dart`
- Create: `student-app/lib/features/kp_srs/ui/kp_srs_page.dart`
- Modify: `student-app/lib/core/router.dart`
- Modify: `student-app/lib/features/home/home_logic.dart`（`TaskMeta` + **`TaskAction` / `taskAction()`**）
- Modify: `student-app/lib/features/home/ui/home_page.dart`（`_onTask` switch + 独立入口）
- Test: `student-app/test/features/kp_srs/kp_srs_test.dart`
- Test: `student-app/test/features/home/home_logic_test.dart`

- [ ] **Step 1: Repository** — `fetchDue` / `complete`；任务入口用 `Task.content` 解码 items。

- [ ] **Step 2: Controller** — index、提交中、forgot 展开、完成态。

- [ ] **Step 3: UI**

- self_rate：三按钮「记得 / 有点忘 / 忘了」
- 有题：作答 + 提交
- forgot：展开 `content`
- 结束页：「今天按计划复习了 N 个知识点」（禁止「已掌握」）
- 空 due：「今天没有要复习的知识点」

- [ ] **Step 4: 路由** `/kp-srs`（`taskId` 可选）。有 `taskId` → 任务快照；无 → `GET /due`。

- [ ] **Step 5: 接好任务入口（必须，否则 comingSoon）**

在 `home_logic.dart` 给 `TaskAction` 增加 `openKpSrs`，并在 `taskAction()` 中：

```dart
if (t.taskType == 'kp_review') return TaskAction.openKpSrs;
```

以及：

```dart
'kp_review': TaskMeta('知识点复习', '约 10 分钟', Icons.replay, _green),
```

在 `home_page.dart` `_onTask` 增加：

```dart
case TaskAction.openKpSrs:
  context.push(taskRoute('/kp-srs', returnTo: '/home') + '&taskId=${t.id}');
```

（参数拼接方式与现网 `taskRoute` 风格对齐。）

更新 `home_logic_test`：`taskType: 'kp_review'` → `TaskAction.openKpSrs`（**不是** `comingSoon`）。

- [ ] **Step 6: 独立「复习」入口**

挂在**学习首页**任务列表上方或旁的按钮「知识点复习」，`context.push('/kp-srs')`（无 taskId，页内拉 `/due`）。不要复用旧 `knowledge_review` 页；不要只做任务入口。

- [ ] **Step 7: Flutter 测试**

Run: `flutter test test/features/kp_srs/ test/features/home/home_logic_test.dart`

- [ ] **Step 8: 提交**

```bash
git commit --trailer "Co-authored-by: Cursor <cursoragent@cursor.com>" -m "feat(student-app): kp_srs review session for due knowledge points"
```

---

### Task 10: 清理与回归

**Files:**
- Modify: `backend/app/services/cleanup.py`
- 全量相关测试

- [ ] **Step 1: cleanup** — 在 `detach_points` / 删除 `KnowledgePoint` **之前**，对该批 `knowledge_point_id` **硬删** `knowledge_review_items`（仅 `status=removed` 挡不住 FK）。删 lesson 时同样先清队列行。

- [ ] **Step 2: 回归**

```bash
cd backend && python -m pytest tests/test_knowledge_review.py tests/test_task_gen.py tests/test_scheduler.py -v
flutter test test/features/kp_srs/ test/features/home/home_logic_test.dart
```

- [ ] **Step 3: 提交**

```bash
git commit --trailer "Co-authored-by: Cursor <cursoragent@cursor.com>" -m "chore: cleanup hooks and regression for knowledge-review SRS"
```

---

## 手动验收清单

1. 孩子进度在第 1 课，第 1 课某 KP 练到达标 → 队列出现，明日到期。  
2. 家长进度调到第 3 课 → toast 入队数增加；调回第 1 课 → 队列不减。  
3. 把 `next_review_at` 改到过去 → 生成 `kp_review` 且孩子首页可见。  
4. 复习：记得升档；忘了回 1 天并看到讲解；完成页无「已掌握」。  
5. 暂停一项后任务仍可结案。

---

## 执行备注

- 后端测试用 Bash 的 `python`（见 AGENTS.md：PowerShell conda 可能缺依赖）。  
- DB 必须从 `backend/` 启动，避免空库。  
- `generate_knowledge_questions` 无模型时应用 fake 兜底，保证 self_rate/generated 可测。
