# 听写出词重写（遗忘曲线动态挑词 + 护栏 + 孩子级配置）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `_gen_dictation` 从「当前课按 id 盲取前 N」改为「遗忘曲线 + 掌握度动态挑词，到期上限/新词下限护栏」，并让听写参数支持孩子级配置（修复家长端写全局、读孩子的 bug）。

**Architecture:** 重写 `task_gen.py::_gen_dictation` 的取词：候选池 = 孩子绑定教材下所有 `approved` 课的生词，按「到期 > 新词 > 补位」三档 + 比例护栏填充。新增 `get_child_config_float` 读浮点配置；新增孩子级配置写入口（复用 `dictation_input_mode` 的 `ChildConfig` 存储）；家长端 UI 增删键并分流写入。

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
    # 第2课放 3 个词，全部到期
    l2 = Lesson(document_id=doc.id, subject="语文", title="第2课",
                start_page=3, end_page=4, extract_status="done", audit_status="approved")
    db.add(l2); db.flush()
    _add_words(db, l2, ["到期A", "到期B", "到期C"])
    for wb in db.query(WordBank).filter_by(lesson_id=l2.id).all():
        db.add(WordMastery(word_bank_id=wb.id, is_weak=True,
                           next_review_at=datetime.utcnow() - timedelta(days=1),
                           user_id=uid, mastery=0.1, attempts=json.dumps([False])))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    words = json.loads(t.content)
    got = {w["word"] for w in words}
    # count=7, due_cap=0.5 → 到期上限 ceil(3.5)=4；3 个到期词都进
    assert {"到期A", "到期B", "到期C"} <= got
    # 新词下限 max(1, floor(7*0.3))=2：白鹭、矗立 保留
    assert {"白鹭", "矗立"} <= got
    # 无补位词，凑不满 7 → 总数为 3 + 2 = 5，不硬补
    assert len(words) == 5
    db.close()


def test_dictation_excludes_mastered_words():
    """mastery>=0.9 的词不进入任何一档。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 白鹭、矗立
    for wb in db.query(WordBank).filter_by(lesson_id=l1_id).all():
        db.add(WordMastery(word_bank_id=wb.id, is_weak=False,
                           next_review_at=datetime.utcnow() + timedelta(days=30),
                           user_id=uid, mastery=0.95,
                           attempts=json.dumps([True, True, True])))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    # 两个词都掌握且未到期 → 听写任务应为 None（无词可出）
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    assert t is None
    db.close()


def test_dictation_fills_with_low_mastery_words():
    """到期+新词不足 count 时，用低 mastery 补位词补到 count。"""
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 白鹭、矗立 两个新词
    doc = db.query(PdfDocument).first()
    l2 = Lesson(document_id=doc.id, subject="语文", title="第2课",
                start_page=3, end_page=4, extract_status="done", audit_status="approved")
    db.add(l2); db.flush()
    # 第2课 5 个「已学未掌握未到期」词
    _add_words(db, l2, ["巩固1", "巩固2", "巩固3", "巩固4", "巩固5"])
    for wb in db.query(WordBank).filter_by(lesson_id=l2.id).all():
        db.add(WordMastery(word_bank_id=wb.id, is_weak=False,
                           next_review_at=datetime.utcnow() + timedelta(days=3),
                           user_id=uid, mastery=0.4, attempts=json.dumps([True])))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    words = json.loads(t.content)
    # 新词 2 个 + 补位 5 个 = 7，补满 count
    assert len(words) == 7
    db.close()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_task_gen.py::test_dictation_due_cap_and_new_floor tests/test_task_gen.py::test_dictation_excludes_mastered_words tests/test_task_gen.py::test_dictation_fills_with_low_mastery_words -v`
Expected: FAIL（旧算法 `test_dictation_excludes_mastered_words` 会得到任务而非 None；`test_dictation_due_cap_and_new_floor` 旧算法旧课到期词按 `count-new_ratio=2` 只取 2 个到期词，断言 `3 个都进` 失败）。

注意：`_setup` 里 `new_ratio` 旧逻辑默认 5，旧算法在「新词=2、到期=3」时 `max(0, count-new_ratio)=2`，到期只取 2 个 → 新测试断言 3 个到期词全进，旧代码 FAIL。

- [ ] **Step 3: 实现**

替换 `backend/app/services/task_gen.py` 的 `_gen_dictation`（第 37-60 行整段）为：

```python
def _gen_dictation(db, lesson, user_id, count, due_cap=0.5, new_floor=0.3):
    """按遗忘曲线 + 掌握度出听写：
    - 候选池：孩子绑定教材下所有 approved 课的本学科生词（跨课）。
    - 到期词（next_review_at<=now）按 mastery 升序，最多 ceil(count*due_cap) 个。
    - 新词（无 WordMastery 或 attempts 为空）按 id 升序，至少 max(1, floor(count*new_floor)) 个。
    - 不足 count 时用「已学未掌握未到期」词按 mastery 升序补位；仍不足不硬补。
    - mastery>=0.9 视为已掌握，不进任何一档。
    """
    import math
    subject = lesson.subject
    now = datetime.utcnow()

    # 候选池：绑定教材下所有 approved 课的生词
    bound_doc_ids = [r[0] for r in db.query(UserDocument.document_id).filter_by(user_id=user_id).all()]
    lesson_ids = [r[0] for r in db.query(Lesson.id).filter(
        Lesson.subject == subject,
        Lesson.document_id.in_(bound_doc_ids),
        Lesson.audit_status == "approved").all()]
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

    def _is_new(wb):
        m = mrows.get(wb.id)
        if m is None:
            return True
        try:
            return not json.loads(m.attempts or "[]")
        except (ValueError, TypeError):
            return True

    def _mastery_of(wb):
        m = mrows.get(wb.id)
        return m.mastery if m else 0.0

    def _is_due(wb):
        m = mrows.get(wb.id)
        return bool(m and m.next_review_at and m.next_review_at <= now)

    def _is_mastered(wb):
        return _mastery_of(wb) >= 0.9

    due_n = int(math.ceil(count * due_cap))
    new_n = max(1, int(math.floor(count * new_floor)))

    due_words = sorted((w for w in words if _is_due(w) and not _is_mastered(w)),
                       key=_mastery_of)[:due_n]
    new_words = [w for w in words if _is_new(w)][:new_n]

    picked = due_words + new_words
    picked_ids = {w.id for w in picked}
    if len(picked) < count:
        fill = sorted((w for w in words
                       if not _is_mastered(w)
                       and not _is_due(w)
                       and not _is_new(w)
                       and w.id not in picked_ids),
                      key=_mastery_of)
        picked += fill[:count - len(picked)]

    if not picked:
        return None
    return Task(
        task_type="dictation", subject=subject, title=f"{lesson.title} 生词听写",
        detail=f"今日听写 · {len(picked)} 个（到期复习 {len(due_words)} + 新课 {len(new_words)} + 巩固 {len(picked)-len(due_words)-len(new_words)}）",
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
Expected: 新增 3 个测试 PASS；`test_dictation_picks_new_and_due_words` 会失败（旧测试断言旧算法「2 新 + 1 旧 = 3」的具体数量），见下一步修复。

- [ ] **Step 6: 修旧测试 `test_dictation_picks_new_and_due_words`**

该测试（`tests/test_task_gen.py:186-212`）断言旧行为。改为断言新行为：到期词进、新词保留、不硬补。替换其断言段：

```python
    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    assert t is not None
    words = json.loads(t.content)
    got = {w["word"] for w in words}
    # 新词（当前课白鹭、矗立）与到期旧词（旧词B）都进；到期上限 4、新词下限 2，总词数 = 2 新 + 1 到期 = 3，不硬补
    assert {"白鹭", "矗立", "旧词B"} <= got
    assert len(words) == 3
```

（原测试的「旧词A」非到期、无 mastery → 是「新词」档，但新词下限 `new_n=2` 已由白鹭/矗立占满，故旧词A不进；断言只要求「白鹭/矗立/旧词B」三词在，且总数 3。）

- [ ] **Step 7: 全量回归 task_gen**

Run: `cd backend && python -m pytest tests/test_task_gen.py -v`
Expected: 全部 PASS。

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/task_gen.py backend/tests/test_task_gen.py
git commit -m "feat(dictation): pick words by forgetting curve + mastery with due/new guards"
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
- 取词算法（候选池 + 三档 + 护栏）→ 任务 2 ✓
- `get_child_config_float` → 任务 1 ✓
- 孩子级配置写入口（修复写全局 bug）→ 任务 3 ✓
- 家长端 UI + 分流 → 任务 4 ✓
- 废弃 `task_new_ratio` → 任务 5 ✓
- 测试（到期上限/新词下限/掌握移出/补位/跨用户隔离/配置覆盖/越界夹取）→ 任务 1/2/3 内嵌 ✓

**Placeholder scan：** 无 TBD/TODO；所有代码步骤含完整代码。

**Type consistency：**
- `get_child_config_float(db, child_id, key, fallback)` 签名在任务 1 定义、任务 2/3 调用一致 ✓
- `_gen_dictation(db, lesson, user_id, count, due_cap=0.5, new_floor=0.3)` 签名在任务 2 定义，`generate_tasks_for_user` 调用一致 ✓
- `PreferencesReq` 字段（`task_dictation_count_语文`/`task_dictation_due_cap`/`task_dictation_new_floor`）任务 3 定义，任务 4 前端字段名一致 ✓

**已知风险**：任务 2 的 `test_dictation_fills_with_low_mastery_words` 依赖「补位词补满 7」——若 `_setup` 只造 2 个新词、第 2 课 5 个补位词，`new_n=2` 占满新词档，5 个补位词全部进入，总数 7。与算法一致。执行时若 `WordBank` 排序导致补位词不足（其它测试污染），以「运行失败再核」为准，本计划已给出确切断言供对照。
