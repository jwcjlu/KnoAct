# 题目闭环 + 两端信息架构 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一「生成类」题目模型 + 家长端题目审核台 + 孩子端首页重设计（古诗勉励 + 今日进度 + 学科 tab）。

**Architecture:** 扩展 `Question` 表（加 subject/date/status/extra/task_type）；`task_gen` 每日生成时把生成类题目（knowledge/listening/math）落 Question 表；新增审核接口；家长端加「题目审核台」；孩子端首页重设计（古诗轮换 + 进度 + 学科 tab）。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite；前端原生 JS 单文件；pytest。

---

## 范围说明（重要）

- **生成类题目**（需审核）：knowledge（基础知识）、listening（听力）、math（数学）——每日任务生成，落 Question 表。
- **听写类**（不审核）：dictation（生词/单词）——继续从 WordBank 取，不落 Question，孩子端直接显示。
- **reading（阅读）题**：保持现状（拆课产物 + 教材审核流程），本次不动。

---

## 文件结构

- `backend/app/models.py`（改）— Question 加 5 字段
- `backend/app/services/task_gen.py`（改）— 生成类题目落 Question
- `backend/app/routers/questions.py`（改）— 新增审核接口
- `backend/app/routers/home.py`（改）— 孩子端首页数据（按学科取当日 published 题目 + 听写词）
- `frontend/app.js`（改）— 家长端题目审核台 + 孩子端首页重设计
- `frontend/index.html`（改）— 样式 + 缓存版本号
- `backend/tests/`（扩展）

---

## Task 1: Question 模型扩展 + 迁移

**Files:**
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_models.py`（或 test_question_model）

- [ ] **Step 1: 写失败测试**

测试新增字段存在且可写入：

```python
def test_question_has_new_fields(db):
    from app.models import Question
    q = Question(lesson_id=1, qtype="knowledge", question="测试",
                 subject="语文", status="pending", extra='{"keywords":["a"]}', task_type="knowledge")
    db.add(q); db.flush()
    assert q.subject == "语文"
    assert q.status == "pending"
    assert q.extra == '{"keywords":["a"]}'
    assert q.task_type == "knowledge"
    assert q.date is not None or q.date is None  # date 可空
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: FAIL（新字段不存在）

- [ ] **Step 3: 改 models.py**

`Question` 类新增字段：

```python
class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    qtype: Mapped[str] = mapped_column(String(16), default="reading")   # knowledge | listening | reading | math
    question: Mapped[str] = mapped_column(TextCls)
    answer: Mapped[str] = mapped_column(TextCls, default="")
    subject: Mapped[str] = mapped_column(String(16), default="")        # 新增
    date: Mapped[date] = mapped_column(Date, nullable=True)             # 新增
    status: Mapped[str] = mapped_column(String(16), default="published") # 新增（老数据默认 published，避免孩子端看不到）
    extra: Mapped[str] = mapped_column(TextCls, default="")             # 新增
    task_type: Mapped[str] = mapped_column(String(16), default="reading") # 新增
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

注意：`date` 用 `Date` 类型，需要 `from datetime import date`（models.py 顶部可能已有 `from datetime import datetime`，补 `date`）。

- [ ] **Step 4: 迁移数据库**

因为 SQLite 的 `create_all` 不会自动加列，需要手动 ALTER 或删库重建。最稳妥：写一个迁移脚本或直接对现有 zhixueban.db 执行 ALTER：

```bash
cd backend && python -c "
import sqlite3
c = sqlite3.connect('zhixueban.db')
for col, ddl in [
    ('subject', 'VARCHAR(16) DEFAULT \"\"'),
    ('date', 'DATE'),
    ('status', 'VARCHAR(16) DEFAULT \"published\"'),
    ('extra', 'TEXT DEFAULT \"\"'),
    ('task_type', 'VARCHAR(16) DEFAULT \"reading\"'),
]:
    try:
        c.execute(f'ALTER TABLE questions ADD COLUMN {col} {ddl}')
        print('added', col)
    except Exception as e:
        print('skip', col, e)
c.commit(); c.close()
"
```

（先检查字段是否已存在，幂等。）

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat: Question 表扩展 subject/date/status/extra/task_type 字段"
```

---

## Task 2: task_gen 生成类题目落 Question 表

**Files:**
- Modify: `backend/app/services/task_gen.py`
- Test: `backend/tests/test_task_gen.py`

- [ ] **Step 1: 写失败测试**

```python
def test_generated_questions_land_in_question_table():
    db = SessionLocal()
    uid, l1_id = _setup(db)
    generate_tasks_for_user(db, uid, date.today())
    # knowledge 题目应落到 questions 表
    qs = db.query(Question).filter_by(task_type="knowledge", date=date.today(), status="pending").all()
    assert len(qs) >= 1
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_task_gen.py::test_generated_questions_land_in_question_table -v`
Expected: FAIL（题目没落 Question 表）

- [ ] **Step 3: 改 task_gen**

在 `generate_tasks_for_user` 里，生成「生成类」任务（knowledge/listening/math）时，同时把题目落 Question 表。

在 `_gen_knowledge` 里（把知识点转问答后），额外落 Question：

```python
# _gen_knowledge 里，qs 生成后：
from ..models import Question
for item in qs:
    db.add(Question(
        lesson_id=lesson.id, qtype="knowledge",
        question=item.get("question") or item.get("content") or "",
        answer=item.get("answer") or "",
        subject=subject, date=datetime.utcnow().date(),
        status="pending", task_type="knowledge",
        extra=json.dumps({"keywords": item.get("keywords") or [], "content": item.get("content") or ""}, ensure_ascii=False),
    ))
```

同理 `_gen_listening`（听力：question=理解题、extra=对话）和 `_gen_math_practice`（数学题）。

**注意**：`date` 用 `datetime.utcnow().date()`，而不是 `date.today()`（保持 UTC 口径一致，虽然本地测试两者同一天）。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_task_gen.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/task_gen.py backend/tests/test_task_gen.py
git commit -m "feat: 每日生成类题目落 Question 表（pending 待审核）"
```

---

## Task 3: 题目审核接口

**Files:**
- Modify: `backend/app/routers/questions.py`
- Test: `backend/tests/test_questions.py`（或 test_pdf_router）

- [ ] **Step 1: 写失败测试**

```python
def test_review_questions_by_subject(client, db):
    # 造几道 pending 题目（不同学科/课程）
    # GET /api/questions/review?date=今天&subject=语文 → 返回按课程分组的待审题
    # POST /api/questions/{id}/approve → status=published
    # POST /api/questions/approve-by-subject → 该学科全部 published
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_questions.py -v`
Expected: FAIL（接口不存在）

- [ ] **Step 3: 实现接口**

在 `questions.py` 新增：

```python
@router.get("/review")
def review_questions(date: date, subject: str = "", db: Session = Depends(get_db)):
    """待审核题目，按学科→课程分组。"""
    q = db.query(Question).filter(Question.status == "pending")
    if date:
        q = q.filter(Question.date == date)
    if subject:
        q = q.filter(Question.subject == subject)
    qs = q.order_by(Question.subject, Question.lesson_id, Question.id).all()
    # 按 lesson 分组
    grouped = {}
    for item in qs:
        grouped.setdefault((item.subject, item.lesson_id), []).append({
            "id": item.id, "qtype": item.qtype, "question": item.question,
            "answer": item.answer, "extra": item.extra, "task_type": item.task_type,
        })
    return {"groups": [
        {"subject": subj, "lesson_id": lid, "questions": items}
        for (subj, lid), items in grouped.items()
    ]}


@router.post("/{question_id}/approve")
def approve_question(question_id: int, db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    q.status = "published"
    db.commit()
    return {"ok": True}


@router.post("/{question_id}/reject")
def reject_question(question_id: int, db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    q.status = "rejected"
    db.commit()
    return {"ok": True}


@router.post("/approve-by-lesson")
def approve_by_lesson(lesson_id: int, date: date, db: Session = Depends(get_db)):
    db.query(Question).filter_by(lesson_id=lesson_id, date=date, status="pending").update(
        {"status": "published"}, synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.post("/approve-by-subject")
def approve_by_subject(subject: str, date: date, db: Session = Depends(get_db)):
    db.query(Question).filter_by(subject=subject, date=date, status="pending").update(
        {"status": "published"}, synchronize_session=False)
    db.commit()
    return {"ok": True}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_questions.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/questions.py backend/tests/test_questions.py
git commit -m "feat: 题目审核接口（单题/按课/按学科批量）"
```

---

## Task 4: 家长端题目审核台 UI

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1: 改造「题目」tab**

把 `renderQuestionTab` 从「逐课管理阅读理解题」改为「题目审核台」（按学科→课程分组，审 pending 题目）。

参考原型 `docs/superpowers/prototype-parent-portal.html` 的结构。

新增状态和函数：

```javascript
let reviewGroups = [];   // [{subject, lesson_id, questions:[...]}]

async function loadReviewQuestions(){
  const today = /* 今天日期 yyyy-mm-dd */;
  const d = await api(`/api/questions/review?date=${today}`);
  reviewGroups = d.groups || [];
}
```

渲染：按 subject 分三栏（语文/英语/数学），每栏下按 lesson 分组，每课可展开看题，每题「通过/驳回」按钮，顶部「通过本课」「通过本学科全部」。

- [ ] **Step 2: 加审核操作函数**

```javascript
async function approveQuestion(id){ await api(`/api/questions/${id}/approve`, {method:'POST'}); await loadReviewQuestions(); render(); }
async function rejectQuestion(id){ await api(`/api/questions/${id}/reject`, {method:'POST'}); await loadReviewQuestions(); render(); }
async function approveByLesson(lessonId){ ... }
async function approveBySubject(subject){ ... }
```

- [ ] **Step 3: node --check 验证**

Run: `cd /d/workspace/github/KnoAct && node --check frontend/app.js`
Expected: 无语法错误

- [ ] **Step 4: 提交**

```bash
git add frontend/app.js
git commit -m "feat: 家长端题目审核台（按学科/课程审题，批量通过）"
```

---

## Task 5: 孩子端首页重设计

**Files:**
- Modify: `frontend/app.js`
- Modify: `frontend/index.html`

- [ ] **Step 1: 古诗轮换数据 + 渲染**

新增四君子古诗数据（竹兰梅菊），按日期轮换：

```javascript
const POEMS = [
  {name:'竹', title:'竹石', text:'咬定青山不放松，立根原在破岩中。\n千磨万击还坚劲，任尔东西南北风。', author:'清 · 郑板桥', bg:'bamboo'},
  {name:'兰', title:'幽兰', text:'……', author:'……', bg:'orchid'},
  {name:'梅', title:'梅花', text:'墙角数枝梅，凌寒独自开。\n遥知不是雪，为有暗香来。', author:'宋 · 王安石', bg:'plum'},
  {name:'菊', title:'菊花', text:'不是花中偏爱菊，此花开尽更无花。', author:'唐 · 元稹', bg:'chrys'},
];
function todayPoem(){ const d = new Date(); return POEMS[Math.floor(d.getTime()/86400000) % 4]; }
```

- [ ] **Step 2: 今日进度总览 + 学科 tab**

改 `renderHome`：
- 顶部渲染古诗区（`todayPoem()` + 对应 bg class）
- 「今日任务」区改为：总进度卡（完成 N/M + 进度条）+ 学科 tab（语文/英语/数学，带待完成角标）
- 当前学科的任务列表：待完成高亮 + 已完成置灰

孩子端任务数据来源：`dailyTasks`（已有），按 `subject` 过滤分组。已完成 = `submit_status === 'approved'`，待完成 = `not_started` 或 `submitted`。

- [ ] **Step 3: index.html 加古诗区样式**

在 `frontend/index.html` 加 `.hero-poem` 及四君子背景的 CSS（竹/兰/梅/菊四个渐变）。

- [ ] **Step 4: node --check + 缓存版本号**

Run: `cd /d/workspace/github/KnoAct && node --check frontend/app.js`
更新 `index.html` 的 `app.js?v=` 版本号 +1。

- [ ] **Step 5: 提交**

```bash
git add frontend/app.js frontend/index.html
git commit -m "feat: 孩子端首页重设计（古诗勉励+今日进度+学科tab）"
```

---

## 自审

**Spec 覆盖：**
- 统一题目模型 → Task 1（Question 扩展）
- 每日生成落 Question → Task 2
- 审核接口 → Task 3
- 家长端审核台 → Task 4
- 孩子端首页 → Task 5

**占位符扫描：** 兰花的诗我在 Task 5 里用了「……」，需要 implementer 补一首真实的兰花诗（或用陶渊明《饮酒·幽兰》）。这是唯一占位，其余完整。

**类型一致性：**
- Question 新字段名：subject/date/status/extra/task_type，Task 1 定义、Task 2/3 使用一致
- 审核接口 URL：`/api/questions/review`、`/{id}/approve`、`/{id}/reject`、`/approve-by-lesson`、`/approve-by-subject`，Task 3 定义、Task 4 调用一致
- 孩子端学科 tab 用 `dailyTasks` 按 subject 分组，与现有数据一致

**一个需要 implementer 注意的点**：孩子端首页现有的 `renderHome` 已经有学科切换（`setSubject`）和任务卡片渲染，Task 5 是**重构**这部分，不是从零写。implementer 需先读现有 `renderHome` 完整逻辑，在保留数据加载（loadHome/loadTasks）的基础上改渲染。
