# 听力材料纳入每日任务预生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `/api/listening/material` 的 14s 实时 LLM 调用，改为每日定时任务按孩子已学生词+知识点预生成听力材料，接口读库秒回、未命中实时生成兜底。

**Architecture:** 在 `services/task_gen.py` 新增 `_gen_listening`，英语科生成 `task_type="listening"` 的 `Task` 落库（复用现有唯一约束实现幂等）；`GenerateListeningTool` 增加 `words`/`knowledge_points` 个性化参数；`/api/listening/material` 改为「读当天 Task → 命中返回，未命中实时生成并落库」。

**Tech Stack:** FastAPI + SQLAlchemy（同步 Session），pytest（`cd backend && python -m pytest`）。

**Spec:** `docs/superpowers/specs/2026-10-27-listening-pregeneration-design.md`

---

## 环境事实（必读）

- 测试启动：`cd backend && python -m pytest`（`pyproject.toml` 已设 `pythonpath=["."]`、`testpaths=["tests"]`）。
- 测试库：`conftest.py` 设 `DATABASE_URL=sqlite:///./test.db`，`setup_db` fixture 每次 drop/create 全表。
- provider 降级：测试环境无 ModelConfig，`resolve()` 降级到 `fake` provider，`generate_listening.run()` 会返回兜底文案而非真调 LLM。因此测试里调用 `generate_listening` 不会慢、不会联网。

---

## File Structure

- `backend/app/tools/generation.py` — 修改：`GenerateListeningTool.run` 增 `words`/`knowledge_points` 参数。
- `backend/app/services/task_gen.py` — 修改：新增 `_gen_listening`，接入 `generate_tasks_for_user`。
- `backend/app/routers/learning.py` — 修改：`listening_material` 改读库优先。
- `backend/tests/test_generation_tools.py` — 修改：加个性化参数传递的断言。
- `backend/tests/test_task_gen.py` — 修改：加 listening 生成测试（含英语课 setup）。
- `backend/tests/test_learning.py` — 修改：加接口读库优先的测试。

---

### Task 1: `GenerateListeningTool` 支持个性化参数

**Files:**
- Modify: `backend/app/tools/generation.py:23-48`
- Test: `backend/tests/test_generation_tools.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_generation_tools.py` 末尾追加：

```python
def test_generate_listening_accepts_words_and_points():
    result = generate_listening.run(
        {"words": ["apple", "banana"], "knowledge_points": ["颜色词"]}, _ctx())
    assert "dialogue" in result
    assert "question" in result
    assert "answer" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_generation_tools.py::test_generate_listening_accepts_words_and_points -v`
Expected: 通过（当前 `run` 忽略多余 args，不会失败）——但此测试只验证签名兼容，真正行为验证在 Task 2。**允许此步骤直接 PASS**（这是增量安全网，不是红-绿触发器）。

- [ ] **Step 3: 实现参数拼接**

修改 `backend/app/tools/generation.py` 的 `GenerateListeningTool.run`（替换第 28-48 行整段）：

```python
    def run(self, args, ctx: UnifiedContext) -> dict:
        provider = _get_provider()
        words = args.get("words") or []
        kps = args.get("knowledge_points") or []
        try:
            if words or kps:
                word_s = "、".join(words)
                kp_s = "、".join(kps)
                prompt = (
                    f"用以下已学单词编一段 3 句的英语对话，并出 1 道理解题。\n"
                    f"已学单词：{word_s}\n"
                    f"知识点：{kp_s}\n"
                    '只返回 JSON，格式：{"dialogue":"对话内容","question":"题目","answer":"答案"}'
                )
            else:
                prompt = ('用小学生已学单词编一段 3 句的英语对话，并出 1 道理解题。'
                          '只返回 JSON，格式：{"dialogue":"对话内容","question":"题目","answer":"答案"}')
            text = provider.generate(prompt=prompt, system="你是英语老师。", json_mode=True)
            data = json.loads(text)
            return {
                "dialogue": (data.get("dialogue") or "").strip(),
                "question": (data.get("question") or "").strip(),
                "answer": (data.get("answer") or "").strip(),
            }
        except Exception:
            return {
                "dialogue": "A: What can you do? B: I can sing.",
                "question": "对话里 B 会做什么？",
                "answer": "唱歌",
            }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_generation_tools.py -v`
Expected: 3 个测试全部 PASS（含原有的 `test_generate_listening_returns_structure` 和 `test_generate_diagnostic_questions_returns_questions`）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/tools/generation.py backend/tests/test_generation_tools.py
git commit -m "feat(listening): generate_listening 支持已学生词+知识点个性化参数"
```

---

### Task 2: `task_gen.py` 新增 `_gen_listening` 并接入

**Files:**
- Modify: `backend/app/services/task_gen.py:32-93`
- Test: `backend/tests/test_task_gen.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_task_gen.py` 追加英语课 setup 与 listening 断言。先扩 `_setup` 让其同时造英语课，避免影响现有测试：

在文件末尾追加一个新 fixture 函数和测试（不动原 `_setup`）：

```python
def _setup_english(db):
    db.query(WordMastery).delete()
    db.query(WordBank).delete()
    db.query(KnowledgePoint).delete()
    db.query(Text).delete()
    db.query(Lesson).delete()
    db.query(PdfDocument).delete()
    db.query(Task).delete()
    db.query(User).delete()
    db.commit()
    u = User(name="测试孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="英语.pdf", subject="英语", storage_path="")
    db.add(doc); db.flush()
    l1 = Lesson(document_id=doc.id, subject="英语", title="Unit 1", start_page=1, end_page=2,
                extract_status="done", audit_status="approved")
    db.add(l1); db.flush()
    for w in ["apple", "banana"]:
        db.add(WordBank(lesson_id=l1.id, subject="英语", word=w, extra="释义"))
    db.add(KnowledgePoint(subject="英语", category="词汇", content="颜色词", lesson_id=l1.id))
    db.commit()
    return u.id, l1.id


def test_generate_tasks_creates_listening_for_english():
    db = SessionLocal()
    uid, l1 = _setup_english(db)
    generate_tasks_for_user(db, uid, date.today())
    listening = db.query(Task).filter_by(
        user_id=uid, subject="英语", date=date.today(), task_type="listening").all()
    assert len(listening) == 1
    content = json.loads(listening[0].content)
    assert "dialogue" in content and "question" in content and "answer" in content
    db.close()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_task_gen.py::test_generate_tasks_creates_listening_for_english -v`
Expected: FAIL（`Task` 无 listening 行，`len(listening) == 0`）。

- [ ] **Step 3: 实现 `_gen_listening` 并接入**

修改 `backend/app/services/task_gen.py`：

(3a) 在 `_gen_review` 之后（约第 71 行 `return Task(...)` 块之后）新增函数：

```python
def _gen_listening(db, lesson):
    words = [w.word for w in db.query(WordBank).filter_by(lesson_id=lesson.id).all()]
    kps = [p.content for p in db.query(KnowledgePoint).filter_by(lesson_id=lesson.id).all()]
    if not words:
        return None
    from ..tools.generation import generate_listening
    from ..core.context import UnifiedContext
    ctx = UnifiedContext(user_id=0, lesson_id=lesson.id, question="")
    result = generate_listening.run({"words": words, "knowledge_points": kps}, ctx)
    return Task(
        task_type="listening", subject=lesson.subject, title="英语听力练习",
        detail=f"基于 {len(words)} 个已学生词",
        content=json.dumps(result, ensure_ascii=False),
        points=15,
        content_status="published",
    )
```

(3b) 修改 `generate_tasks_for_user` 的生成循环（第 86-92 行），改为：

```python
        gens = [_gen_dictation(db, lesson, n_dict),
                _gen_knowledge(db, lesson, n_know),
                _gen_review(db, lesson, n_review)]
        if subject == "英语":
            gens.append(_gen_listening(db, lesson))
        for gen in gens:
            if gen is not None:
                gen.user_id = user_id
                gen.date = day
                db.add(gen)
```

注意：`_gen_listening` 里构造 `Task` 时未设 `user_id`/`date`，由循环统一回填（与现有 `_gen_*` 一致）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_task_gen.py -v`
Expected: 全部 PASS（新增 listening 测试 + 原有 4 个测试；原 `_setup` 只有语文课，英语无课所以 `test_generate_tasks_creates_dictation_and_knowledge_and_is_idempotent` 的 types 集合不会多出 listening，幂等断言仍成立）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/task_gen.py backend/tests/test_task_gen.py
git commit -m "feat(listening): 每日任务为英语科预生成听力材料并落库"
```

---

### Task 3: `/api/listening/material` 改为读库优先

**Files:**
- Modify: `backend/app/routers/learning.py:118-127`
- Test: `backend/tests/test_learning.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_learning.py` 末尾追加：

```python
def test_listening_material_reads_pregenerated_task(setup_db):
    import json
    from datetime import date
    from app.models import Task
    from app.database import SessionLocal
    s = SessionLocal()
    s.add(Task(
        user_id=1, subject="英语", date=date.today(), task_type="listening",
        title="英语听力练习", content_status="published",
        content=json.dumps({"dialogue": "A: Hi B: Hello", "question": "B 说了什么？", "answer": "Hello"}, ensure_ascii=False),
    ))
    s.commit(); s.close()

    resp = _client().get("/api/listening/material?user_id=1")
    data = resp.json()
    assert data["text"] == "A: Hi B: Hello"
    assert data["questions"][0]["answer"] == "Hello"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_learning.py::test_listening_material_reads_pregenerated_task -v`
Expected: FAIL（当前实现忽略 `Task`，实时生成返回兜底文案，`data["text"]` 不等于 `"A: Hi B: Hello"`）。

- [ ] **Step 3: 实现读库优先**

替换 `backend/app/routers/learning.py` 的 `listening_material`（第 118-127 行）为：

```python
@router.get("/api/listening/material")
def listening_material(user_id: int, db: Session = Depends(get_db)):
    import json as _json
    from datetime import date as _date
    from ..models import Task
    from ..tools.generation import generate_listening
    from ..core.context import UnifiedContext

    row = db.query(Task).filter_by(
        user_id=user_id, subject="英语", date=_date.today(), task_type="listening"
    ).order_by(Task.id).first()
    if row and row.content:
        try:
            data = _json.loads(row.content)
            if data.get("dialogue"):
                return {
                    "text": data["dialogue"],
                    "questions": [{"question": data.get("question", ""), "answer": data.get("answer", "")}],
                }
        except Exception:
            pass

    ctx = UnifiedContext(user_id=user_id, lesson_id=0, question="")
    result = generate_listening.run({}, ctx)
    db.add(Task(
        user_id=user_id, subject="英语", date=_date.today(), task_type="listening",
        title="英语听力练习", content_status="published",
        content=_json.dumps(result, ensure_ascii=False),
    ))
    db.commit()
    return {
        "text": result["dialogue"],
        "questions": [{"question": result["question"], "answer": result["answer"]}],
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_learning.py -v`
Expected: 全部 PASS（新增读库优先测试 + 原 `test_listening_material`；后者在无预生成时走实时生成+落库分支，返回结构仍含 `text`/`questions`）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/learning.py backend/tests/test_learning.py
git commit -m "feat(listening): 听力接口读当天预生成材料，未命中实时生成并落库"
```

---

## Self-Review 结论

- **Spec 覆盖**：3 个改动点（generation 参数 / task_gen 落库 / 接口读库）各对应一个 Task；「content_status=published」「英语才生成」「未命中兜底」均已在代码中体现。
- **占位符**：无 TBD/TODO，所有步骤含完整代码与命令。
- **类型一致性**：`generate_listening.run` 的返回 dict 键 `dialogue/question/answer` 在 Task 1、2、3 中一致；`Task` 字段 `user_id/subject/date/task_type/title/content/points/content_status` 与 `models.py` 定义一致；`_gen_listening` 的 `lesson.subject` 即 `"英语"`。
- **幂等一致性**：`generate_tasks_for_user` 的 `exists` 检查覆盖 `task_type="listening"`（唯一约束含 task_type），Task 2 的第二次调用不新增行由现有幂等测试间接保障。
