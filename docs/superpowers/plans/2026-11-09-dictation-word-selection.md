# 听写出词重写（遗忘曲线动态挑词 + 护栏 + 孩子级配置）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `_gen_dictation` 从「当前课按 id 盲取前 N」改为「已学课范围 + 无限循环复习（到期/错词/新词/轮转四档优先级）」，并让听写参数支持孩子级配置（修复家长端写全局、读孩子的 bug）。

**Architecture:** 重写 `task_gen.py::_gen_dictation` 的取词：候选池 = 孩子绑定教材下「当前课及之前」所有 `approved` 课的生词（向前扩展、未学课不进池、已学课永不踢出），按「到期词 → 错词 → 新词 → 轮转补位」四档 + 比例护栏填充。新增 `get_child_config_float` 读浮点配置；新增孩子级配置写入口（复用 `dictation_input_mode` 的 `ChildConfig` 存储）；家长端 UI 增删键并分流写入。

**Tech Stack:** FastAPI + SQLAlchemy（pytest 测试）；原生 JS 家长端（`parent-web/app.js`）。

**测试命令**：从 `backend/` 目录跑 `python -m pytest tests/ -v`（用 Bash 的 python，已装 sqlalchemy；详见 AGENTS.md 环境陷阱）。

---

## 文件结构

- **修改** `backend/app/services/child_config.py` — 新增 `get_child_config_float`。
- **修改** `backend/app/services/task_gen.py` — 重写 `_gen_dictation`，`generate_tasks_for_user` 读新键。
- **修改** `backend/app/routers/learning.py` — 扩展 `PreferencesReq` + `PUT/GET /api/learning/preferences` 支持听写参数孩子级读写。
- **修改** `parent-web/app.js` — 配置 UI 增删键 + `saveLearningConfig` 分流。
- **测试** `backend/tests/test_child_config.py`、`backend/tests/test_task_gen.py`、`backend/tests/test_dictation_preferences.py`。

---

## 任务 1：`get_child_config_float`（读浮点配置）

**Files:**
- Modify: `backend/app/services/child_config.py`
- Test: `backend/tests/test_child_config.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_child_config.py` 顶部 import 后追加：

```python
from app.services.child_config import get_child_config_float
```

在文件末尾追加：

```python
def test_get_child_config_float_child_override(setup_db, db):
    child = _child(db)
    db.add(ModelConfig(key="task_dictation_due_cap", value="0.5"))
    db.add(ChildConfig(user_id=child.id, key="task_dictation_due_cap", value="0.3"))
    db.commit()
    assert get_child_config_float(db, child.id, "task_dictation_due_cap", 0.5) == 0.3


def test_get_child_config_float_falls_back_to_global(setup_db, db):
    child = _child(db)
    db.add(ModelConfig(key="task_dictation_new_floor", value="0.4"))
    db.commit()
    assert get_child_config_float(db, child.id, "task_dictation_new_floor", 0.3) == 0.4


def test_get_child_config_float_falls_back_to_default(setup_db, db):
    child = _child(db)
    db.commit()
    assert get_child_config_float(db, child.id, "nope_float", 0.25) == 0.25


def test_get_child_config_float_clamps_to_01(setup_db, db):
    child = _child(db)
    db.add(ChildConfig(user_id=child.id, key="task_dictation_due_cap", value="2.5"))
    db.commit()
    assert get_child_config_float(db, child.id, "task_dictation_due_cap", 0.5) == 1.0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_child_config.py -v`
Expected: 4 个新测试 FAIL（`ImportError: cannot import name 'get_child_config_float'`）。

- [ ] **Step 3: 实现**

在 `backend/app/services/child_config.py` 的 `get_child_config_int` 之后追加：

```python
def get_child_config_float(db: Session, child_id: int, key: str, fallback: float) -> float:
    val = get_child_config_str(db, child_id, key, "")
    try:
        result = float(val) if val else fallback
    except ValueError:
        return fallback
    return max(0.0, min(1.0, result))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_child_config.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/child_config.py backend/tests/test_child_config.py
git commit -m "feat(config): add get_child_config_float with 0..1 clamp"
```

---

## 任务 2：重写 `_gen_dictation` 取词（核心算法）

**Files:**
- Modify: `backend/app/services/task_gen.py`
- Test: `backend/tests/test_task_gen.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_task_gen.py` 末尾追加（复用现有 `_setup` 与 `WordMastery`/`WordBank`/`Lesson` 导入；`UserDocument` 已在顶部导入）：

```python
def _add_words(db, lesson, words):
    for w in words:
        db.add(WordBank(lesson_id=lesson.id, subject=lesson.subject, word=w, extra=""))
    db.flush()


def test_dictation_due_cap_and_new_floor():
    """到期词超过上限时被截断，且新词下限始终保留。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 第1课：白鹭、矗立（当前课）
    doc = db.query(PdfDocument).first()
    # 第2课放 3 个词，全部到期；但第2课 > 当前课(l1)，应不进池
    # 为验证「已学课范围」，这里改为在第1课内追加到期词，另建第2课验证不进池
    l2 = Lesson(document_id=doc.id, subject="语文", title="第2课",
                start_page=3, end_page=4, extract_status="done", audit_status="approved")
    db.add(l2); db.flush()
    _add_words(db, l2, ["未学课词"])
    db.commit()

    # 当前课(l1)内造 3 个到期词
    for wb in db.query(WordBank).filter_by(lesson_id=l1_id).all():
        db.add(WordMastery(word_bank_id=wb.id, is_weak=True,
                           next_review_at=datetime.utcnow() - timedelta(days=1),
                           user_id=uid, mastery=0.1, attempts=json.dumps([False]),
                           mistake_count=1))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    words = json.loads(t.content)
    got = {w["word"] for w in words}
    # 未学课(l2)的词不进池
    assert "未学课词" not in got
    # 当前课两个词都到期 → 都进；不硬补
    assert {"白鹭", "矗立"} <= got
    assert len(words) == 2
    db.close()


def test_dictation_rotation_includes_mastered_words():
    """B2 无限循环：已掌握的词不移出，在到期/错词/新词不足时按最久没考补位回来。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 白鹭、矗立
    # 白鹭：已掌握、未到期（mastery>=0.9, next_review_at 在远期）
    wb_ba = db.query(WordBank).filter_by(lesson_id=l1_id, word="白鹭").first()
    db.add(WordMastery(word_bank_id=wb_ba.id, is_weak=False,
                       next_review_at=datetime.utcnow() + timedelta(days=30),
                       user_id=uid, mastery=0.95,
                       attempts=json.dumps([True, True, True]),
                       mistake_count=0))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    # 白鹭(已掌握) 与 矗立(新词) 都应进池：白鹭落在「轮转」档，矗立落在「新词」档
    assert t is not None
    got = {w["word"] for w in json.loads(t.content)}
    assert "白鹭" in got
    assert "矗立" in got
    db.close()


def test_dictation_fills_with_low_mastery_words():
    """到期+新词不足 count 时，用轮转词（已考过、没错、未到期）按最久没考补满 count。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 白鹭、矗立 两个新词
    doc = db.query(PdfDocument).first()
    # 在第1课内追加 5 个「已考过、没错、未到期」词（轮转词）
    _add_words(db, db.query(Lesson).filter_by(id=l1_id).first(),
               ["轮转1", "轮转2", "轮转3", "轮转4", "轮转5"])
    for wb in db.query(WordBank).filter_by(lesson_id=l1_id).all():
        if wb.word in ("白鹭", "矗立"):
            continue
        db.add(WordMastery(word_bank_id=wb.id, is_weak=False,
                           next_review_at=datetime.utcnow() + timedelta(days=3),
                           user_id=uid, mastery=0.4, attempts=json.dumps([True]),
                           mistake_count=0))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    words = json.loads(t.content)
    # 新词 2 个(白鹭、矗立) + 轮转 5 个 = 7，补满 count
    assert len(words) == 7
    db.close()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_task_gen.py::test_dictation_due_cap_and_new_floor tests/test_task_gen.py::test_dictation_rotation_includes_mastered_words tests/test_task_gen.py::test_dictation_fills_with_low_mastery_words -v`
Expected: FAIL（旧算法只从 `lesson_id=当前课` 取新词、且会跨课取到期词、且不取「已考过未到期」词作为轮转；三个新测试分别断言「未学课不进池」「已掌握词进池」「轮转词补满」，旧代码均不满足）。

- [ ] **Step 3: 实现**

替换 `backend/app/services/task_gen.py` 的 `_gen_dictation`（第 37-60 行整段）为：

```python
def _gen_dictation(db, lesson, user_id, count, due_cap=0.5, new_floor=0.3):
    """按「已学课范围 + 无限循环」出听写：
    - 候选池：绑定教材下、audit_status=approved、subject 匹配、且 id <= 当前课(lesson.id)
      的全部 WordBank（未学课不进池，已学课永不踢出）。
    - 四档优先级：到期词 → 错词 → 新词 → 轮转补位。
      - 到期词（next_review_at<=now）+ 错词（mistake_count>0 未到期）合计受 due_n 上限。
      - 新词（无 WordMastery 或 attempts 为空）受 new_n 下限保障。
      - 轮转词（已考过、没错、未到期，含已掌握）按「最久没考」补满 count。
    - 所有词永不移出（B2）；已掌握的词靠轮转档回来。
    """
    import math
    subject = lesson.subject
    now = datetime.utcnow()

    # 候选池：当前课及之前的所有 approved 课（按 Lesson.id <= lesson.id 截断）
    bound_doc_ids = [r[0] for r in db.query(UserDocument.document_id).filter_by(user_id=user_id).all()]
    lesson_ids = [r[0] for r in db.query(Lesson.id).filter(
        Lesson.subject == subject,
        Lesson.document_id.in_(bound_doc_ids),
        Lesson.audit_status == "approved",
        Lesson.id <= lesson.id).all()]
    if not lesson_ids:
        return None

    words = (db.query(WordBank)
             .filter(WordBank.lesson_id.in_(lesson_ids))
             .order_by(WordBank.id).all())
    if not words:
        return None

    # 该孩子每个词的 mastery 记录（word_bank_id -> WordMastery）
    mrows = {m.word_bank_id: m for m in db.query(WordMastery).filter(
        WordMastery.user_id == user_id,
        WordMastery.word_bank_id.in_([w.id for w in words])).all()}

    def _m(wb):
        return mrows.get(wb.id)

    def _is_new(wb):
        m = _m(wb)
        if m is None:
            return True
        try:
            return not json.loads(m.attempts or "[]")
        except (ValueError, TypeError):
            return True

    def _is_due(wb):
        m = _m(wb)
        return bool(m and m.next_review_at and m.next_review_at <= now)

    def _is_mistaken(wb):
        m = _m(wb)
        return bool(m and (m.mistake_count or 0) > 0 and not _is_due(wb))

    due_n = int(math.ceil(count * due_cap))
    new_n = max(1, int(math.floor(count * new_floor)))

    # 1+2: 复习档（到期 + 错词），合计受 due_n 上限
    due_words = sorted((w for w in words if _is_due(w)),
                       key=lambda w: _m(w).next_review_at)[:due_n]
    picked = list(due_words)
    if len(picked) < due_n:
        mistaken = sorted((w for w in words if _is_mistaken(w)),
                          key=lambda w: -(_m(w).mistake_count or 0))
        picked += mistaken[:due_n - len(picked)]

    picked_ids = {w.id for w in picked}

    # 3: 新词，受 new_n 下限
    new_words = [w for w in words if _is_new(w) and w.id not in picked_ids][:new_n]
    picked += new_words
    picked_ids = {w.id for w in picked}

    # 4: 轮转补位（已考过、没错、未到期，含已掌握），按最久没考排
    if len(picked) < count:
        def _last_review(w):
            m = _m(w)
            return m.next_review_at or now  # NULL 视为最早，先轮
        rotation = sorted((w for w in words
                           if w.id not in picked_ids
                           and not _is_new(w)
                           and not _is_due(w)
                           and not _is_mistaken(w)),
                          key=_last_review)
        picked += rotation[:count - len(picked)]

    if not picked:
        return None
    n_review = len(due_words) + len([w for w in picked if _is_due(w) or _is_mistaken(w)])
    n_new = len(new_words)
    n_rot = len(picked) - n_review - n_new
    return Task(
        task_type="dictation", subject=subject, title=f"{lesson.title} 生词听写",
        detail=f"今日听写 · {len(picked)} 个（复习 {n_review} + 新课 {n_new} + 轮转 {n_rot}）",
        content=json.dumps([{"id": w.id, "word": w.word, "extra": w.extra} for w in picked], ensure_ascii=False),
        points=20,
    )
```

- [ ] **Step 4: 更新 `generate_tasks_for_user` 读新键**

在 `backend/app/services/task_gen.py` 的 `generate_tasks_for_user`（约 281-286 行）中，把读 `new_ratio` 与调 `_gen_dictation` 的两处改为：

```python
        n_dict = _default_count(db, f"task_dictation_count_{subject}", 7, child_id=user_id)
        n_know = _default_count(db, "task_knowledge_count", 5, child_id=user_id)
        from .child_config import get_child_config_float
        due_cap = get_child_config_float(db, user_id, "task_dictation_due_cap", 0.5)
        new_floor = get_child_config_float(db, user_id, "task_dictation_new_floor", 0.3)
        gens = [_gen_dictation(db, lesson, user_id, n_dict, due_cap, new_floor),
                _gen_knowledge(db, lesson, user_id, n_know, 5, bucket.id),
                _gen_review(db, lesson, user_id, n_dict)]
```

（`_gen_knowledge` 的 `new_ratio` 实参写死为 `5`，保持其旧行为不变；只移除对 `task_new_ratio` 配置键的依赖。）

- [ ] **Step 5: 跑新测试确认通过 + 旧测试回归**

Run: `cd backend && python -m pytest tests/test_task_gen.py -v`
Expected: 新增 3 个测试 PASS；`test_dictation_picks_new_and_due_words` 会失败（该旧测试构造的「第2课」在新「已学课范围」下超出当前课，旧词A/旧词B均不进池），见下一步重写。

- [ ] **Step 6: 重写旧测试 `test_dictation_picks_new_and_due_words`**

该测试（`tests/test_task_gen.py:186-212`）基于旧「跨课取到期词」行为。在新「已学课范围」下，第 2 课（`id > 当前课`）不进池。重写为验证「当前课内：新词 + 到期词都进，且到期词受上限、不硬补」。整段替换为：

```python
def test_dictation_picks_new_and_due_words():
    """当前课内：新词与到期词都进；到期词不足不硬补。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 第1课：白鹭、矗立 两个生词（当前课）
    # 白鹭造一条到期记录，矗立保持新词
    wb_ba = db.query(WordBank).filter_by(lesson_id=l1_id, word="白鹭").first()
    db.add(WordMastery(word_bank_id=wb_ba.id, is_weak=True,
                       next_review_at=datetime.utcnow() - timedelta(days=1),
                       user_id=uid, mastery=0.1, attempts=json.dumps([False]),
                       mistake_count=1))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    assert t is not None
    words = json.loads(t.content)
    got = {w["word"] for w in words}
    # 白鹭（到期）与矗立（新词）都进；只有 2 个候选，不硬补
    assert {"白鹭", "矗立"} <= got
    assert len(words) == 2
    db.close()
```

- [ ] **Step 7: 全量回归 task_gen**

Run: `cd backend && python -m pytest tests/test_task_gen.py -v`
Expected: 全部 PASS。

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/task_gen.py backend/tests/test_task_gen.py
git commit -m "feat(dictation): pick words within learned lessons with rotation review"
```

---

## 任务 3：孩子级听写配置写入口（修复写全局 bug）

**Files:**
- Modify: `backend/app/routers/learning.py`
- Test: `backend/tests/test_dictation_preferences.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_dictation_preferences.py` 末尾追加：

```python
def test_preferences_put_dictation_counts_child_scoped(setup_db):
    session = SessionLocal()
    parent, child, parent_h, child_h = parent_child(session, "dcnt")
    # 另一个孩子（同家长），用于验证不串
    from app.models import User
    other = User(name="other_child", role="child", parent_id=parent.id)
    session.add(other); session.commit()
    other_id = other.id
    session.close()

    r = client.put("/api/learning/preferences",
                   json={"user_id": child.id,
                         "task_dictation_count_语文": 12,
                         "task_dictation_due_cap": 0.6,
                         "task_dictation_new_floor": 0.2},
                   headers=parent_h)
    assert r.status_code == 200

    g = client.get(f"/api/learning/preferences?user_id={child.id}", headers=child_h)
    assert g.json()["task_dictation_count_语文"] == 12
    assert g.json()["task_dictation_due_cap"] == 0.6

    # 另一个孩子未配，回落到默认
    from app.services.child_config import get_child_config_int, get_child_config_float
    s = SessionLocal()
    assert get_child_config_int(s, other_id, "task_dictation_count_语文", 7) == 7
    s.close()


def test_preferences_get_returns_defaults_for_unconfigured_child(setup_db):
    session = SessionLocal()
    _, child, _, child_h = parent_child(session, "ddef")
    session.close()
    r = client.get(f"/api/learning/preferences?user_id={child.id}", headers=child_h)
    body = r.json()
    assert body["dictation_input_mode"] == "paper_photo"
    assert body["task_dictation_due_cap"] == 0.5
    assert body["task_dictation_new_floor"] == 0.3
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_dictation_preferences.py::test_preferences_put_dictation_counts_child_scoped tests/test_dictation_preferences.py::test_preferences_get_returns_defaults_for_unconfigured_child -v`
Expected: FAIL（GET 返回体里没有 `task_dictation_count_语文`/`task_dictation_due_cap` 等键，PUT 不识别这些字段）。

- [ ] **Step 3: 实现 —— 扩展请求模型与读写**

修改 `backend/app/routers/learning.py`。将 `PreferencesReq`（约 460-462 行）改为：

```python
class PreferencesReq(BaseModel):
    user_id: int
    dictation_input_mode: str = ""
    task_dictation_count_语文: int | None = None
    task_dictation_count_英语: int | None = None
    task_dictation_due_cap: float | None = None
    task_dictation_new_floor: float | None = None
```

将 `GET /api/learning/preferences`（约 465-474 行）改为：

```python
@router.get("/api/learning/preferences")
def get_learning_preferences(
    user_id: int = Depends(resolve_target_user_id),
    user: User = Depends(require_learning_user),
    db: Session = Depends(get_db),
):
    ensure_user_access(user, user_id, db)
    from ..services.child_config import (
        get_dictation_input_mode, get_child_config_int, get_child_config_float,
    )

    return {
        "dictation_input_mode": get_dictation_input_mode(db, user_id),
        "task_dictation_count_语文": get_child_config_int(db, user_id, "task_dictation_count_语文", 7),
        "task_dictation_count_英语": get_child_config_int(db, user_id, "task_dictation_count_英语", 7),
        "task_dictation_due_cap": get_child_config_float(db, user_id, "task_dictation_due_cap", 0.5),
        "task_dictation_new_floor": get_child_config_float(db, user_id, "task_dictation_new_floor", 0.3),
    }
```

将 `PUT /api/learning/preferences`（约 477-491 行）改为：

```python
@router.put("/api/learning/preferences")
def put_learning_preferences(
    req: PreferencesReq,
    user: User = Depends(require_role("parent")),
    db: Session = Depends(get_db),
):
    from ..services.child_config import VALID_DICTATION_MODES, set_child_config_str

    child = db.get(User, req.user_id)
    if child is None or child.role != "child" or child.parent_id != user.id:
        raise HTTPException(status_code=404, detail={"error": "child_not_found"})
    if req.dictation_input_mode:
        if req.dictation_input_mode not in VALID_DICTATION_MODES:
            raise HTTPException(status_code=400, detail={"error": "invalid_mode"})
        set_child_config_str(db, req.user_id, "dictation_input_mode", req.dictation_input_mode)
    if req.task_dictation_count_语文 is not None:
        set_child_config_str(db, req.user_id, "task_dictation_count_语文", str(req.task_dictation_count_语文))
    if req.task_dictation_count_英语 is not None:
        set_child_config_str(db, req.user_id, "task_dictation_count_英语", str(req.task_dictation_count_英语))
    if req.task_dictation_due_cap is not None:
        set_child_config_str(db, req.user_id, "task_dictation_due_cap", str(req.task_dictation_due_cap))
    if req.task_dictation_new_floor is not None:
        set_child_config_str(db, req.user_id, "task_dictation_new_floor", str(req.task_dictation_new_floor))
    return {"ok": True}
```

- [ ] **Step 4: 跑测试确认通过 + 旧偏好测试回归**

Run: `cd backend && python -m pytest tests/test_dictation_preferences.py -v`
Expected: 全部 PASS（含新增 2 个；旧 `test_preferences_get_default` 断言 `== {"dictation_input_mode": "paper_photo"}` 会因返回体多了键而失败，见下一步）。

- [ ] **Step 5: 修旧测试 `test_preferences_get_default`**

该测试（`tests/test_dictation_preferences.py:13-19`）断言精确相等。改为子集断言：

```python
def test_preferences_get_default(setup_db):
    session = SessionLocal()
    _, child, _, child_h = parent_child(session, "pref")
    session.close()
    r = client.get(f"/api/learning/preferences?user_id={child.id}", headers=child_h)
    assert r.status_code == 200
    assert r.json()["dictation_input_mode"] == "paper_photo"
```

- [ ] **Step 6: 全量回归**

Run: `cd backend && python -m pytest tests/test_dictation_preferences.py tests/test_child_config.py tests/test_task_gen.py -v`
Expected: 全部 PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/learning.py backend/tests/test_dictation_preferences.py
git commit -m "feat(dictation): child-scoped dictation config (count/due-cap/new-floor)"
```

---

## 任务 4：家长端 UI 增删键 + 分流写入

**Files:**
- Modify: `parent-web/app.js`

- [ ] **Step 1: 改配置 UI（`renderLearningConfigTab`）**

在 `parent-web/app.js` 的 `renderLearningConfigTab()`（约 2366-2370 行），把 `task_new_ratio` 行替换为两个比例行。将：

```js
          ${num('task_new_ratio','5','新/旧比例（新名额）','每日任务里「当天新课」的名额，旧=总量-新')}
```

替换为：

```js
          ${num('task_dictation_due_cap','0.5','到期复习词上限比例','每天到期复习词最多占总量多少（0~1）','0','1','0.1')}
          ${num('task_dictation_new_floor','0.3','新课生词下限比例','每天至少留多少比例给未听写过的生词（0~1）','0','1','0.1')}
```

（`task_dictation_count_语文/英语` 两行保留不动。）

- [ ] **Step 2: 改保存逻辑（`saveLearningConfig`）分流**

在 `parent-web/app.js` 的 `saveLearningConfig()`（约 2386-2408 行），把听写相关键从全局 `POST /api/config` 里拆出，走孩子级 `PUT /api/learning/preferences`。将整个函数体替换为：

```js
async function saveLearningConfig(){
  if(!uid){ toast('请先选择当前孩子'); return; }
  const inputs = document.querySelectorAll('[data-key]');
  // 孩子级键：dictation_input_mode + 听写参数，走 PUT /api/learning/preferences
  const childKeys = new Set([
    'dictation_input_mode',
    'task_dictation_count_语文',
    'task_dictation_count_英语',
    'task_dictation_due_cap',
    'task_dictation_new_floor',
  ]);
  const childBody = { user_id: uid };
  let dictMode = null;
  for(const el of inputs){
    const key = el.dataset.key;
    if(key === 'dictation_input_mode'){
      dictMode = el.value;
      continue;
    }
    let value;
    if(el.type === 'checkbox'){ value = el.checked ? 'true' : 'false'; }
    else { value = el.value; }
    if(childKeys.has(key)){
      // 比例类转数字，其余保持字符串
      const isRatio = (key === 'task_dictation_due_cap' || key === 'task_dictation_new_floor');
      const isCount = (key === 'task_dictation_count_语文' || key === 'task_dictation_count_英语');
      if(isRatio){ childBody[key] = parseFloat(value); }
      else if(isCount){ childBody[key] = parseInt(value, 10); }
      else { childBody[key] = value; }
    } else {
      await api('/api/config', {method:'POST', body:{key, value}});
    }
  }
  if(uid){
    if(dictMode) childBody.dictation_input_mode = dictMode;
    await api('/api/learning/preferences', {method:'PUT', body: childBody});
    if(dictMode) configMap.dictation_input_mode = dictMode;
  }
  toast('学习配置已保存');
  await loadConfig();
  await loadLearningPreferences();
}
```

- [ ] **Step 3: 回显孩子级值**

`loadLearningPreferences()` 现已读 `GET /api/learning/preferences`（返回 `dictation_input_mode`）。扩展它把听写参数也并入 `configMap`，使 UI 回显孩子级值。找到 `loadLearningPreferences` 函数（在 `parent-web/app.js` 中，搜索 `loadLearningPreferences`），把其中读偏好后写入 `configMap` 的部分改为：

```js
async function loadLearningPreferences(){
  if(!uid) return;
  const prefs = await api(`/api/learning/preferences?user_id=${uid}`);
  if(prefs && typeof prefs === 'object'){
    for(const k in prefs){
      configMap[k] = String(prefs[k]);
    }
  }
}
```

（若原函数体结构不同，以「把 prefs 的所有键写进 configMap，值为字符串」为准替换；`dictation_input_mode` 的回显已含在其中。）

- [ ] **Step 4: 语法检查**

Run: `node --check parent-web/app.js`
Expected: 无输出（语法正确）。

- [ ] **Step 5: Commit**

```bash
git add parent-web/app.js
git commit -m "feat(parent): child-scoped dictation config UI (due-cap/new-floor ratios)"
```

---

## 任务 5：收尾 —— 清理废弃键引用与全量回归

**Files:**
- Modify: `backend/app/services/task_gen.py`（确认无残留 `task_new_ratio`）
- 全量测试

- [ ] **Step 1: 确认无残留 `task_new_ratio`**

Run: `cd backend && grep -rn "task_new_ratio" app/ tests/ || echo "no references"`
Expected: 输出 `no references`（若还有引用，删除后重跑）。

- [ ] **Step 2: 全量后端回归**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 全部 PASS（若有与听写取词相关的既有断言失败，按新行为修正断言，不改变新算法语义）。

- [ ] **Step 3: Commit（如有改动）**

```bash
git add -A
git commit -m "chore(dictation): remove deprecated task_new_ratio references"
```

---

## Self-Review

**Spec coverage：**
- 取词算法（已学课范围 + 四档优先级 + 护栏）→ 任务 2 ✓
- `get_child_config_float` → 任务 1 ✓
- 孩子级配置写入口（修复写全局 bug）→ 任务 3 ✓
- 家长端 UI + 分流 → 任务 4 ✓
- 废弃 `task_new_ratio` → 任务 5 ✓
- 测试（已学课范围/到期+错词上限/新词下限/轮转循环/跨用户隔离/配置覆盖/越界夹取）→ 任务 1/2/3 内嵌 ✓

**Placeholder scan：** 无 TBD/TODO；所有代码步骤含完整代码。

**Type consistency：**
- `get_child_config_float(db, child_id, key, fallback)` 签名在任务 1 定义、任务 2/3 调用一致 ✓
- `_gen_dictation(db, lesson, user_id, count, due_cap=0.5, new_floor=0.3)` 签名在任务 2 定义，`generate_tasks_for_user` 调用一致 ✓
- `PreferencesReq` 字段（`task_dictation_count_语文`/`task_dictation_due_cap`/`task_dictation_new_floor`）任务 3 定义，任务 4 前端字段名一致 ✓

**已知风险**：任务 2 的 `test_dictation_fills_with_low_mastery_words` 依赖「轮转词补满 7」——`_setup` 造 2 个新词（白鹭、矗立），再在第 1 课内追加 5 个轮转词，`new_n=2` 占满新词档，5 个轮转词全部进入，总数 7。与算法一致。执行时若其它测试的 `WordMastery` 污染导致轮转词不足，以「运行失败再核」为准，本计划已给出确切断言供对照。另注意 `test_dictation_isolates_due_words_across_users` 现断言 `got == {"白鹭","矗立"}`——新算法下第 2 课（B 的到期词）超当前课不进池，A 只出白鹭/矗立，断言仍成立。
