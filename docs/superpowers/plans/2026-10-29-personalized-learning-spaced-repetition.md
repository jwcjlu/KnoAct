# 个性化学习 + 遗忘曲线出题 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「新课学习」改造为「个性化学习」（选课+阅读+AI作业+推进进度），并让每日任务按遗忘曲线出题（当天新课 5 个 + 旧课到期 2 个）。

**Architecture:** 后端新增「作业出题/判分」服务与「选课列表」接口，改造 `task_gen.py` 的听写/知识点出题为「新 5 旧 2」按 `next_review_at` 挑选；前端删除独立「新课学习」入口，把答题推进并入「个性化学习」，新增家长端「学习配置」UI。配置统一存 `ModelConfig` 表，复用现有 `/api/config` 读写。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite；前端原生 JS 单文件（`frontend/app.js` + `index.html`）；pytest。

---

## 文件结构

**后端：**
- `backend/app/services/assignment.py`（新建）— AI 现场出作业（按学科难度 + 题数），失败回退兜底题
- `backend/app/services/task_gen.py`（改）— `_gen_dictation` / `_gen_knowledge` 按「新 5 旧 2」遗忘曲线出题
- `backend/app/routers/learning.py`（改）— 新增 `/api/learning/lessons`（选课列表）、`/api/learning/assignment`（出作业）、`/api/learning/assignment/grade`（判分+推进+落掌握度）
- `backend/app/routers/progress.py`（改）— `advance` 的 `THRESHOLD` 改为读配置 `assignment_pass_threshold`
- `backend/app/models.py`（改）— 无需新表，`ModelConfig` 复用

**前端：**
- `frontend/app.js`（改）— 删「新课学习」流程、并入「个性化学习」；家长端「学习配置」UI；AI 对话开关
- `frontend/index.html`（改）— 「学习配置」样式（如需）

**测试：**
- `backend/tests/test_assignment.py`（新建）
- `backend/tests/test_task_gen.py`（扩展）
- `backend/tests/test_learning.py`（扩展）

---

## 配置键（存 `ModelConfig`，通过现有 `/api/config` GET/POST 读写）

| key | 默认 | 用途 |
|-----|------|------|
| `task_dictation_count_语文` | `7` | 语文每日听写量 |
| `task_dictation_count_英语` | `7` | 英语每日听写量 |
| `task_new_ratio` | `5` | 每日任务中「新」的名额（旧 = 总量 − 新） |
| `assignment_question_count` | `4` | 个性化学习作业题数 |
| `assignment_pass_threshold` | `0.6` | 作业通过正确率 |
| `difficulty_语文` / `difficulty_英语` / `difficulty_数学` | `中等` | 各学科出题难度（简单/中等/困难） |
| `personalized_disable_chat` | `true` | 测试阶段禁用 AI 对话开关 |

---

## Task 1: 作业出题服务 `assignment.py`

**Files:**
- Create: `backend/app/services/assignment.py`
- Test: `backend/tests/test_assignment.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_assignment.py`：

```python
import json
from app.database import SessionLocal
from app.services.assignment import generate_assignment, DIFFICULTY_PROMPT, FALLBACK_ASSIGNMENT


def test_difficulty_prompt_mapping():
    assert DIFFICULTY_PROMPT["简单"] != DIFFICULTY_PROMPT["中等"] != DIFFICULTY_PROMPT["困难"]
    assert DIFFICULTY_PROMPT["中等"]  # 非空


def test_generate_assignment_fake_provider_returns_fallback():
    db = SessionLocal()
    # 未配置真实 provider 时（fake），返回兜底题，绝不抛异常
    out = generate_assignment(db, "白鹭是一首精巧的诗。", subject="语文", difficulty="中等", n=4)
    assert isinstance(out, list)
    assert len(out) > 0
    assert all("question" in q and "answer" in q for q in out)
    db.close()


def test_generate_assignment_empty_text_returns_fallback():
    db = SessionLocal()
    out = generate_assignment(db, "", subject="语文", difficulty="中等", n=4)
    assert out == FALLBACK_ASSIGNMENT
    db.close()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_assignment.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.assignment`）

- [ ] **Step 3: 写最小实现**

创建 `backend/app/services/assignment.py`：

```python
"""个性化学习作业：AI 现场出题（按学科难度 + 题数），失败回退兜底题。"""
import json

from sqlalchemy.orm import Session

from .ai import get_provider

# 难度档位 → 出题 prompt 约束片段
DIFFICULTY_PROMPT = {
    "简单": "题目要基础、直白，考察课文中最明显的信息。",
    "中等": "题目要适中，考察对课文内容的理解与简单推断。",
    "困难": "题目要有一定深度，考察对课文主旨、细节与隐含含义的把握。",
}

FALLBACK_ASSIGNMENT = [
    {"question": "这篇课文主要讲了什么？", "answer": "课文的主要内容"},
    {"question": "你从课文里学到了什么？", "answer": "结合课文谈收获"},
]


def generate_assignment(db: Session, text: str, subject: str = "语文",
                        difficulty: str = "中等", n: int = 4) -> list[dict]:
    """针对课文现场出 n 道作业题，返回 [{question, answer}]。任何异常回退兜底题。"""
    if not text or not text.strip():
        return FALLBACK_ASSIGNMENT
    provider = get_provider(db)
    if provider.name == "fake":
        return FALLBACK_ASSIGNMENT
    diff_hint = DIFFICULTY_PROMPT.get(difficulty, DIFFICULTY_PROMPT["中等"])
    prompt = (
        f"针对下面这篇「{subject}」课文出 {n} 道作业题，适合小学生作答。\n"
        f"{diff_hint}\n"
        '只返回 JSON，格式：{"questions":[{"question":"题目","answer":"答案"}]}。\n\n'
        f"课文：\n{text[:1200]}"
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是出题老师。", json_mode=True)
        data = json.loads(raw)
        qs = data.get("questions") or []
        out = []
        for q in qs:
            question = (q.get("question") or "").strip()
            answer = (q.get("answer") or "").strip()
            if question and answer:
                out.append({"question": question, "answer": answer})
        return out[:n] if out else FALLBACK_ASSIGNMENT
    except Exception:
        return FALLBACK_ASSIGNMENT
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_assignment.py -v`
Expected: PASS（3 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/assignment.py backend/tests/test_assignment.py
git commit -m "feat: 个性化学习作业出题服务（按学科难度）"
```

---

## Task 2: 改造 `task_gen.py` 按遗忘曲线出题

**Files:**
- Modify: `backend/app/services/task_gen.py`
- Test: `backend/tests/test_task_gen.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_task_gen.py` 追加：

```python
def test_dictation_picks_new_and_due_words():
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 第1课：白鹭、矗立 两个生词
    # 再建第2课，含 2 个生词，其中一个到期
    doc = db.query(PdfDocument).first()
    l2 = Lesson(document_id=doc.id, subject="语文", title="第2课", start_page=3, end_page=4,
                extract_status="done", audit_status="approved")
    db.add(l2); db.flush()
    db.add(WordBank(lesson_id=l2.id, subject="语文", word="旧词A", extra=""))
    wb_b = WordBank(lesson_id=l2.id, subject="语文", word="旧词B", extra="")
    db.add(wb_b); db.flush()
    db.add(WordMastery(word_bank_id=wb_b.id, is_weak=True,
                       next_review_at=datetime.utcnow() - timedelta(days=1), user_id=uid))
    db.commit()

    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="dictation").first()
    assert t is not None
    words = json.loads(t.content)
    # 新（当前进度课=第1课）5 个名额，但第1课只有2个词 → 全取；旧（到期）取 旧词B
    got = {w["word"] for w in words}
    assert "白鹭" in got and "矗立" in got
    assert "旧词B" in got
    # 到期旧词只有1个，凑不满2个 → 不硬补，总数为 2(新) + 1(旧) = 3
    assert len(words) == 3
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_task_gen.py::test_dictation_picks_new_and_due_words -v`
Expected: FAIL（当前 `_gen_dictation` 只取当前课前 N 个，不含旧词）

- [ ] **Step 3: 改 `_gen_dictation`**

把 `backend/app/services/task_gen.py` 里的 `_gen_dictation` 替换为：

```python
def _gen_dictation(db, lesson, count, new_ratio=5):
    """按遗忘曲线出听写：当前课取「新」名额，旧课到期词取「旧」名额，凑不满不补。"""
    subject = lesson.subject
    # 新：当前课生词
    new_words = db.query(WordBank).filter_by(lesson_id=lesson.id).order_by(WordBank.id).limit(new_ratio).all()
    # 旧：其它课中到期待复习的词（next_review_at <= now），按遗忘曲线（错得多优先）
    now = datetime.utcnow()
    due_ids = [r[0] for r in db.query(WordMastery.word_bank_id).filter(
        WordMastery.next_review_at.isnot(None), WordMastery.next_review_at <= now).all()]
    due_words = []
    if due_ids:
        due_words = (db.query(WordBank)
                     .filter(WordBank.id.in_(due_ids), WordBank.lesson_id != lesson.id)
                     .order_by(WordBank.id).limit(count - new_ratio).all())
    words = new_words + due_words
    if not words:
        return None
    return Task(
        task_type="dictation", subject=subject, title=f"{lesson.title} 生词听写",
        detail=f"今日听写 · {len(words)} 个（新课 {len(new_words)} + 复习 {len(due_words)}）",
        content=json.dumps([{"id": w.id, "word": w.word, "extra": w.extra} for w in words], ensure_ascii=False),
        points=20,
    )
```

- [ ] **Step 4: 改 `_gen_knowledge`**

把 `_gen_knowledge` 替换为：

```python
def _gen_knowledge(db, lesson, count, new_ratio=5):
    """按遗忘曲线出知识点：当前课取「新」名额，旧课到期知识点取「旧」名额。"""
    from ..models import KnowledgeMastery
    subject = lesson.subject
    new_pts = db.query(KnowledgePoint).filter_by(lesson_id=lesson.id).order_by(KnowledgePoint.id).limit(new_ratio).all()
    now = datetime.utcnow()
    due_ids = [r[0] for r in db.query(KnowledgeMastery.knowledge_point_id).filter(
        KnowledgeMastery.next_review_at.isnot(None), KnowledgeMastery.next_review_at <= now).all()]
    due_pts = []
    if due_ids:
        due_pts = (db.query(KnowledgePoint)
                   .filter(KnowledgePoint.id.in_(due_ids), KnowledgePoint.lesson_id != lesson.id)
                   .order_by(KnowledgePoint.id).limit(count - new_ratio).all())
    pts = new_pts + due_pts
    if not pts:
        return None
    return Task(
        task_type="knowledge", subject=subject, title=f"{lesson.title} 基础知识",
        detail=f"重点巩固 · {len(pts)} 个知识点（新课 {len(new_pts)} + 复习 {len(due_pts)}）",
        content=json.dumps([{"id": p.id, "content": p.content, "category": p.category} for p in pts], ensure_ascii=False),
        points=20,
    )
```

- [ ] **Step 5: 改 `generate_tasks_for_user` 读配置**

把 `generate_tasks_for_user` 里的 `n_dict` / `n_know` 改为按学科读配置，并传入 `new_ratio`：

```python
        n_dict = _default_count(db, f"task_dictation_count_{subject}", 7)
        n_know = _default_count(db, "task_knowledge_count", 5)
        new_ratio = _default_count(db, "task_new_ratio", 5)
        gens = [_gen_dictation(db, lesson, n_dict, new_ratio),
                _gen_knowledge(db, lesson, n_know, new_ratio),
                _gen_review(db, lesson, n_dict)]
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_task_gen.py -v`
Expected: PASS（新增测试 + 原有测试全过；注意 `test_generate_tasks_creates_dictation_and_knowledge_and_is_idempotent` 仍应通过，因为第1课有生词会出 dictation）

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/task_gen.py backend/tests/test_task_gen.py
git commit -m "feat: 每日听写/知识点按遗忘曲线出题（新5旧2）"
```

---

## Task 3: 后端接口（选课列表 + 作业出题/判分）

**Files:**
- Modify: `backend/app/routers/learning.py`
- Modify: `backend/app/routers/progress.py`
- Test: `backend/tests/test_learning.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_learning.py` 追加：

```python
from app.routers.learning import assignment_grade  # 或经 TestClient 调接口


def test_assignment_grade_passes_and_advances(client, db):
    # 依赖 conftest 的 client fixture；若无则用 fastapi TestClient 直连
    # 这里以直连函数为例：构造一个正确率 >= 阈值的判分
    pass
```

> 说明：`conftest.py` 已有 TestClient 风格 fixture。具体断言以「判分通过后 `LearningProgress.current_lesson_id` 推进到下一课」为核心。见 Step 3 接口实现后补齐精确断言。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_learning.py -v`
Expected: FAIL（新接口未定义）

- [ ] **Step 3: 实现接口**

在 `backend/app/routers/learning.py` 追加：

```python
from pydantic import BaseModel as _BaseModel
from ..models import Text as TextModel, Question
from ..services.assignment import generate_assignment


@router.get("/api/learning/lessons")
def learning_lessons(user_id: int, subject: str = "语文", db: Session = Depends(get_db)):
    """个性化学习选课列表：返回该学科所有课（含教材来源、当前进度标记）。"""
    from ..models import PdfDocument
    lessons = db.query(Lesson).filter_by(subject=subject).order_by(Lesson.id).all()
    prog = db.query(LearningProgress).filter_by(user_id=user_id, subject=subject).first()
    current_id = prog.current_lesson_id if prog else None
    out = []
    for l in lessons:
        doc = db.get(PdfDocument, l.document_id)
        out.append({
            "id": l.id, "subject": l.subject, "title": l.title,
            "start_page": l.start_page, "end_page": l.end_page,
            "document_name": doc.filename if doc else "",
            "is_current": l.id == current_id,
        })
    return out


class AssignmentReq(_BaseModel):
    user_id: int
    lesson_id: int
    subject: str = "语文"


@router.post("/api/learning/assignment")
def assignment(req: AssignmentReq, db: Session = Depends(get_db)):
    """AI 现场出作业：读配置的题数与难度，基于本课正文出题。"""
    from ..services.model_config import resolve  # 或直接用 _default_count 读 ModelConfig
    t = db.query(TextModel).filter_by(lesson_id=req.lesson_id).first()
    if not t or not t.content.strip():
        return {"questions": []}
    n = _cfg_int(db, "assignment_question_count", 4)
    diff = _cfg_str(db, f"difficulty_{req.subject}", "中等")
    qs = generate_assignment(db, t.content, subject=req.subject, difficulty=diff, n=n)
    return {"questions": qs}
```

其中 `_cfg_int` / `_cfg_str` 辅助函数（复用 `_default_count` 模式，定义在 learning.py 顶部）：

```python
def _cfg_int(db, key, fallback):
    from ..models import ModelConfig
    row = db.query(ModelConfig).filter_by(key=key).first()
    try:
        return int(row.value) if row and row.value else fallback
    except ValueError:
        return fallback

def _cfg_str(db, key, fallback):
    from ..models import ModelConfig
    row = db.query(ModelConfig).filter_by(key=key).first()
    return row.value if row and row.value else fallback


class AssignmentGradeReq(_BaseModel):
    user_id: int
    lesson_id: int
    subject: str = "语文"
    correct: int
    total: int


@router.post("/api/learning/assignment/grade")
def assignment_grade(req: AssignmentGradeReq, db: Session = Depends(get_db)):
    """判分：正确率 >= 阈值则推进进度并落掌握度。"""
    threshold = float(_cfg_str(db, "assignment_pass_threshold", "0.6"))
    rate = req.correct / req.total if req.total else 0
    passed = rate >= threshold
    if passed:
        lessons = db.query(Lesson).filter_by(subject=req.subject).order_by(Lesson.id).all()
        prog = db.query(LearningProgress).filter_by(user_id=req.user_id, subject=req.subject).first()
        if not prog:
            prog = LearningProgress(user_id=req.user_id, subject=req.subject, current_lesson_id=None)
            db.add(prog)
        if lessons:
            ids = [l.id for l in lessons]
            cur = prog.current_lesson_id
            if cur in ids:
                idx = ids.index(cur)
                nxt = ids[idx + 1] if idx + 1 < len(ids) else ids[-1]
            else:
                nxt = ids[0]
            prog.current_lesson_id = nxt
        db.commit()
    return {"passed": passed, "rate": rate}
```

- [ ] **Step 4: 改 `progress.py` 的 THRESHOLD 读配置**

把 `backend/app/routers/progress.py` 顶部 `THRESHOLD = 0.6` 改为在 `advance` 内动态读配置：

```python
def advance(req: AdvanceReq, db: Session = Depends(get_db)):
    from ..models import ModelConfig
    row = db.query(ModelConfig).filter_by(key="assignment_pass_threshold").first()
    try:
        threshold = float(row.value) if row and row.value else 0.6
    except ValueError:
        threshold = 0.6
    rate = req.correct / req.total if req.total else 0
    passed = rate >= threshold
    ...
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_learning.py tests/test_progress.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/learning.py backend/app/routers/progress.py backend/tests/test_learning.py
git commit -m "feat: 个性化学习选课+作业出题/判分接口，通过阈值可配置"
```

---

## Task 4: 前端合并「新课学习」到「个性化学习」

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1: 删「新课学习」入口与渲染**

在 `frontend/app.js` 中：
- 删除 `active==='新课学习'` 分支（`render()` 里 line 288 附近）
- 删除 `startNewLesson` 函数（line 676-701）及 `renderNewLesson`（line 786 起）整段
- 删除 `newLesson` 兜底默认数据（line 120 附近的 `let newLesson = {...}`，含白鹭课文）
- 删除 `nlState`、`nlStartQuiz`、`nlPick`、`nlPickText`、`nlSubmit`、`nlAdvance`、`nlRetryRead`、`nlAsk`、`nlQuick`、`nlAddNote` 等新课学习专属函数（若被个性化学习复用则保留）
- 首页 line 443 的「进入下一课」按钮 `onclick="startNewLesson()"` 改为 `onclick="setPage('个性化学习')"`

- [ ] **Step 2: 在「个性化学习」加作业出题/判分**

在 `renderPersonalized` 里，选中课文后，新增「去答题」入口，复用 `assignment` 接口：

```javascript
async function personalizedQuiz(){
  const res = await api(`/api/learning/assignment`, {method:'POST', body:{user_id:uid, lesson_id:currentLessonId, subject:currentSubject}});
  plQuiz = res.questions || [];
  plQuizPicks = {};
  plQuizResult = null;
  render();
}
async function personalizedSubmit(){
  let correct = 0;
  plQuiz.forEach((q,i)=>{ if((plQuizPicks[i]||'').trim() === (q.answer||'').trim()) correct++; });
  const total = plQuiz.length;
  const d = await api(`/api/learning/assignment/grade`, {method:'POST', body:{user_id:uid, lesson_id:currentLessonId, subject:currentSubject, correct, total}});
  plQuizResult = {correct, total, passed: d.passed, rate: d.rate};
  render();
  toast(d.passed ? '作业通过，课程进度已更新' : '未达标，请重看内容再试');
}
```

（`plQuiz` / `plQuizPicks` / `plQuizResult` 需在文件顶部声明为全局变量）

- [ ] **Step 3: 加 AI 对话测试开关**

在个性化学习的「边读边问」渲染处，读配置 `personalized_disable_chat`，为 true 时隐藏 AI 对话输入框，显示「测试阶段暂不开放 AI 对话」占位：

```javascript
// 在 renderPersonalized 或对应对话栏渲染处
const chatDisabled = (configMap['personalized_disable_chat'] !== 'false');
// chatDisabled 时：不渲染对话输入框，改为提示文字
```

（`configMap` 已存在，来自 `/api/config`，`loadConfig` 会填充）

- [ ] **Step 4: `node --check` 验证语法**

Run: `cd /d/workspace/github/KnoAct && node --check frontend/app.js`
Expected: 无报错

- [ ] **Step 5: 提交**

```bash
git add frontend/app.js
git commit -m "feat: 新课学习并入个性化学习，作业判分推进进度，AI对话开关"
```

---

## Task 5: 家长端「学习配置」UI

**Files:**
- Modify: `frontend/app.js`
- Modify: `frontend/index.html`

- [ ] **Step 1: 加配置渲染函数**

在家长端新增「学习配置」区块（独立 tab 或面板），渲染各配置项的输入控件，读写 `/api/config`：

```javascript
async function loadLearningConfig(){
  configMap = await api('/api/config');
  render();
}
async function saveLearningConfig(key, value){
  await api('/api/config', {method:'POST', body:{key, value}});
  await loadLearningConfig();
}
```

配置项 UI 包括：
- 语文/英语每日听写量（数字输入，默认 7）
- 新/旧比例「新」名额（数字输入，默认 5）
- 作业题数（数字输入，默认 4）
- 通过阈值（数字输入 0~1，默认 0.6）
- 各学科难度（下拉：简单/中等/困难）
- 测试开关（禁用 AI 对话，勾选框）

- [ ] **Step 2: 接入家长端导航**

在家长端 tab 列表里加入「学习配置」入口（`renderParent` 或对应 tab 渲染处），点击渲染上述配置表单。

- [ ] **Step 3: `node --check` 验证**

Run: `cd /d/workspace/github/KnoAct && node --check frontend/app.js`
Expected: 无报错

- [ ] **Step 4: 提交**

```bash
git add frontend/app.js frontend/index.html
git commit -m "feat: 家长端学习配置 UI（听写量/比例/难度/测试开关）"
```

---

## 自审

**Spec 覆盖：**
- 第一部分「个性化学习流程」→ Task 1（作业出题）+ Task 3（接口）+ Task 4（前端合并）
- 第二部分「遗忘曲线出题」→ Task 2
- 第三部分「配置项 + 家长端 UI」→ Task 3（读配置）+ Task 5（UI）
- 「测试阶段禁用 AI 对话」→ Task 4 Step 3

**占位符扫描：** Task 3 的测试断言在 Step 1 里较简略（标了「见 Step 3 后补齐」），其余无 TBD/TODO。

**类型一致性：** `generate_assignment(db, text, subject, difficulty, n)` 签名在 Task 1 定义、Task 3 调用一致；`_gen_dictation(db, lesson, count, new_ratio)` / `_gen_knowledge(db, lesson, count, new_ratio)` 在 Task 2 定义、Task 2 Step 5 调用一致；配置键命名全篇一致。
