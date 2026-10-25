# 今日任务系统 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「今日学习任务」从前端写死数组升级为数据库任务表 + APScheduler 定时生成 + 双阶段家长审核 + 听写拍照闭环。

**Architecture:** 新增 `Task` 表与 `services/task_gen.py` 生成服务、`routers/tasks.py` 接口；`main.py` 挂 APScheduler 每天 03:00 生成当天任务；家长端新增「任务」tab 做内容审核与完成审核；孩子端首页改读真实任务。

**Tech Stack:** FastAPI + SQLAlchemy（SQLite）+ APScheduler + 原生 JS 前端（无框架，`render*()` 拼 HTML 字符串）。

**参考 spec:** `docs/superpowers/specs/2026-10-25-daily-task-system-design.md`

---

## 文件结构

**后端（新建）：**
- `backend/app/services/task_gen.py` — 任务生成逻辑（纯函数，供定时器 + 手动触发共用）
- `backend/app/routers/tasks.py` — 任务接口（列/审核/修改/删除/新增/提交/上传/确认）

**后端（修改）：**
- `backend/app/models.py` — 加 `Task` 模型
- `backend/app/main.py` — 挂 APScheduler + include tasks router + 启动生成
- `backend/app/routers/home.py` — 已有，确认分科进度口径一致（可能不动）

**前端（修改）：**
- `frontend/app.js` — 孩子端 `renderHome` 改读真实任务；家长端新增「任务」tab 与审核/新增界面
- `frontend/index.html` — 家长端 nav 若需加 tab（实际 nav 在 app.js 里，可能不需改 html）

**测试（新建）：**
- `backend/tests/test_task_gen.py` — 生成逻辑单测
- `backend/tests/test_tasks_router.py` — 接口测试

**依赖：**
- `backend/requirements.txt` — 加 `apscheduler==3.10.4`

---

## 分科当前课口径（关键决策）

`LearningProgress.current_lesson_id` 是单值、不分科。`home.py` 的 `_lesson_progress` 用「按 subject 排序后 current_lesson_id 的位置」反推当前课序号。

**任务生成沿用同一口径**，新增一个 helper 函数 `_current_lesson(db, subject, user_id)`：

- 取 `LearningProgress.current_lesson_id`
- 若该 id 的 lesson 存在且 `subject` 匹配，返回它
- 否则返回该 subject 下 `id` 最小的 lesson（第一课）；无课返回 None

这个 helper 放在 `task_gen.py` 内，供三类任务生成共用。

---

## Task 1: Task 模型 + 生成服务（TDD）

**Files:**
- Modify: `backend/app/models.py`（加 Task 类）
- Create: `backend/app/services/task_gen.py`
- Create: `backend/tests/test_task_gen.py`
- Modify: `backend/requirements.txt`（加 apscheduler）

- [ ] **Step 1: 加 Task 模型**

在 `backend/app/models.py` 末尾追加（`datetime`、`date`、`JSON` 已 import；需补 `from datetime import date` 与 `from sqlalchemy import Date`）：

```python
from datetime import date
from sqlalchemy import Date

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(16))            # '语文' | '英语'
    date: Mapped[date] = mapped_column(Date)                    # 任务所属日期
    task_type: Mapped[str] = mapped_column(String(16))          # dictation|knowledge|review|reading|listening|custom
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(TextCls, default="")   # JSON 文本快照
    points: Mapped[int] = mapped_column(Integer, default=20)
    content_status: Mapped[str] = mapped_column(String(16), default="pending_review")  # pending_review|published
    submit_status: Mapped[str] = mapped_column(String(16), default="not_started")      # not_started|submitted|approved
    photo_path: Mapped[str] = mapped_column(String(512), default="")
    reviewed_by: Mapped[int] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=True)  # 预留，本次恒 null
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

（注意：`models.py` 顶部现在 import 的是 `from datetime import datetime` 和 `from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text as TextCls, ForeignKey, JSON`。需补 `date` 和 `Date`。）

- [ ] **Step 2: 写生成服务的失败测试**

Create `backend/tests/test_task_gen.py`：

```python
import json
from datetime import datetime, date, timedelta
from ..app.database import SessionLocal, Base, engine
from ..app.models import User, PdfDocument, Lesson, WordBank, KnowledgePoint, WordMastery, Text
from ..app.services.task_gen import generate_tasks_for_user, _current_lesson


def _setup(db):
    # 清空并建一个孩子用户 + 语文两课（一课含生词/知识点/课文）
    db.query(WordMastery).delete()
    db.query(WordBank).delete()
    db.query(KnowledgePoint).delete()
    db.query(Text).delete()
    db.query(Lesson).delete()
    db.query(PdfDocument).delete()
    db.query(User).delete()
    db.commit()
    u = User(name="测试孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l1 = Lesson(document_id=doc.id, subject="语文", title="第1课", start_page=1, end_page=2,
                extract_status="done", audit_status="approved")
    db.add(l1); db.flush()
    for w in ["白鹭", "矗立"]:
        db.add(WordBank(lesson_id=l1.id, subject="语文", word=w, extra="pinyin 释义"))
    db.add(KnowledgePoint(subject="语文", category="字词", content="形近字辨析", lesson_id=l1.id))
    db.add(Text(lesson_id=l1.id, content="白鹭是一首精巧的诗。"))
    db.commit()
    return u.id, l1.id


def test_current_lesson_matches_subject():
    db = SessionLocal()
    uid, l1 = _setup(db)
    # 无 LearningProgress 记录时，应回退到该科第一课
    lesson = _current_lesson(db, "语文", uid)
    assert lesson is not None and lesson.subject == "语文"
    db.close()


def test_generate_tasks_for_user_creates_three_types():
    db = SessionLocal()
    uid, l1 = _setup(db)
    generate_tasks_for_user(db, uid, date.today())
    from ..app.models import Task
    rows = db.query(Task).filter_by(user_id=uid, date=date.today()).all()
    types = {r.task_type for r in rows}
    # 听写 + 基础练习 必然生成；复习仅在到期词存在时生成（此处无 mastery，故只有两类）
    assert "dictation" in types
    assert "knowledge" in types
    db.close()
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_task_gen.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.services.task_gen'`）

- [ ] **Step 4: 实现生成服务**

Create `backend/app/services/task_gen.py`：

```python
"""今日任务生成：对每个孩子、每科，按当前课生成听写/基础练习/复习任务。"""
import json
from datetime import date, datetime

from sqlalchemy.orm import Session

from ..models import User, Lesson, LearningProgress, WordBank, KnowledgePoint, WordMastery, Task


def _current_lesson(db: Session, subject: str, user_id: int):
    """按科返回当前课：LearningProgress.current_lesson_id 匹配该科则用它，否则回退该科第一课。"""
    prog = db.query(LearningProgress).filter_by(user_id=user_id).first()
    lessons = db.query(Lesson).filter_by(subject=subject).order_by(Lesson.id).all()
    if not lessons:
        return None
    if prog and prog.current_lesson_id:
        for l in lessons:
            if l.id == prog.current_lesson_id:
                return l
    return lessons[0]


def _default_count(db: Session, key: str, fallback: int) -> int:
    from ..models import ModelConfig
    row = db.query(ModelConfig).filter_by(key=key).first()
    try:
        return int(row.value) if row and row.value else fallback
    except ValueError:
        return fallback


def _gen_dictation(db, lesson, count):
    words = db.query(WordBank).filter_by(lesson_id=lesson.id).limit(count).all()
    if not words:
        return None
    return Task(
        task_type="dictation", subject=lesson.subject, title=f"{lesson.title} 生词听写",
        detail=f"今日新学 · {len(words)} 个重点生词",
        content=json.dumps([{"id": w.id, "word": w.word, "extra": w.extra} for w in words], ensure_ascii=False),
        points=20,
    )


def _gen_knowledge(db, lesson, count):
    pts = db.query(KnowledgePoint).filter_by(lesson_id=lesson.id).limit(count).all()
    if not pts:
        return None
    return Task(
        task_type="knowledge", subject=lesson.subject, title=f"{lesson.title} 基础知识",
        detail=f"重点巩固 · {len(pts)} 个知识点",
        content=json.dumps([{"id": p.id, "content": p.content, "category": p.category} for p in pts], ensure_ascii=False),
        points=20,
    )


def _gen_review(db, lesson, count):
    # 到期词：WordMastery.next_review_at <= now
    now = datetime.utcnow()
    weak_ids = [r[0] for r in db.query(WordMastery.word_bank_id).filter(
        WordMastery.next_review_at.isnot(None), WordMastery.next_review_at <= now).all()]
    if not weak_ids:
        return None
    words = db.query(WordBank).filter(WordBank.id.in_(weak_ids), WordBank.subject == lesson.subject).limit(count).all()
    if not words:
        return None
    return Task(
        task_type="review", subject=lesson.subject, title="到期复习",
        detail=f"遗忘曲线 · {len(words)} 个到期生词",
        content=json.dumps([{"id": w.id, "word": w.word, "extra": w.extra} for w in words], ensure_ascii=False),
        points=25,
    )


def generate_tasks_for_user(db: Session, user_id: int, day: date):
    """为单个孩子生成当天两科任务。幂等：同 (user_id, subject, date) 已存在则跳过。"""
    subjects = ["语文", "英语"]
    for subject in subjects:
        exists = db.query(Task).filter_by(user_id=user_id, subject=subject, date=day).first()
        if exists:
            continue
        lesson = _current_lesson(db, subject, user_id)
        if not lesson:
            continue
        n_dict = _default_count(db, "task_dictation_count", 15)
        n_know = _default_count(db, "task_knowledge_count", 5)
        n_review = _default_count(db, "task_review_count", 15)
        for gen in (_gen_dictation(db, lesson, n_dict),
                    _gen_knowledge(db, lesson, n_know),
                    _gen_review(db, lesson, n_review)):
            if gen is not None:
                gen.user_id = user_id
                gen.date = day
                db.add(gen)
    db.commit()


def generate_daily_tasks(db: Session, day: date):
    """定时任务入口：为所有孩子生成当天任务。"""
    for (uid,) in db.query(User.id).filter_by(role="child").all():
        generate_tasks_for_user(db, uid, day)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_task_gen.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 加依赖并提交**

在 `backend/requirements.txt` 追加 `apscheduler==3.10.4`。

```bash
cd backend && pip install apscheduler==3.10.4
git add backend/app/models.py backend/app/services/task_gen.py backend/tests/test_task_gen.py backend/requirements.txt
git commit -m "feat: Task 模型 + 任务生成服务（听写/基础/复习，分科幂等）"
```

---

## Task 2: 任务接口 routers/tasks.py（TDD）

**Files:**
- Create: `backend/app/routers/tasks.py`
- Create: `backend/tests/test_tasks_router.py`
- Modify: `backend/app/main.py`（include router）

- [ ] **Step 1: 写接口失败测试**

Create `backend/tests/test_tasks_router.py`：

```python
from datetime import date
from fastapi.testclient import TestClient
from ..app.main import app
from ..app.database import SessionLocal
from ..app.models import User, Task
from ..app.services.task_gen import generate_tasks_for_user


client = TestClient(app)


def _seed():
    db = SessionLocal()
    db.query(Task).delete()
    db.query(User).delete()
    db.commit()
    u = User(name="金宇轩", role="child")
    db.add(u); db.commit()
    return u.id


def test_list_tasks_published_only_for_child():
    uid = _seed()
    generate_tasks_for_user(SessionLocal(), uid, date.today())
    r = client.get(f"/api/tasks?user_id={uid}&date={date.today()}&role=child")
    assert r.status_code == 200
    # 初始 pending_review，孩子端应看不到
    assert r.json() == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_tasks_router.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.routers.tasks'`）

- [ ] **Step 3: 实现接口**

Create `backend/app/routers/tasks.py`：

```python
from datetime import date
from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Task, Point
from ..services.task_gen import generate_tasks_for_user, generate_daily_tasks

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
def list_tasks(user_id: int, date: date, role: str = "child", db: Session = Depends(get_db)):
    q = db.query(Task).filter_by(user_id=user_id, date=date)
    if role == "child":
        q = q.filter_by(content_status="published")
    return [{"id": t.id, "subject": t.subject, "task_type": t.task_type, "title": t.title,
             "detail": t.detail, "content": t.content, "points": t.points,
             "content_status": t.content_status, "submit_status": t.submit_status,
             "photo_path": t.photo_path} for t in q.order_by(Task.id).all()]


@router.post("/generate")
def generate(d: date, db: Session = Depends(get_db)):
    generate_daily_tasks(db, d)
    return {"ok": True}


@router.post("/{task_id}/approve")
def approve(task_id: int, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if t:
        t.content_status = "published"
        db.commit()
        return {"ok": True}
    return {"ok": False}


class ApproveAllReq(BaseModel):
    user_id: int
    date: date

@router.post("/approve-all")
def approve_all(req: ApproveAllReq, db: Session = Depends(get_db)):
    db.query(Task).filter_by(user_id=req.user_id, date=req.date, content_status="pending_review").update(
        {"content_status": "published"}, synchronize_session=False)
    db.commit()
    return {"ok": True}


class EditReq(BaseModel):
    title: str = ""
    detail: str = ""
    content: str = ""

@router.put("/{task_id}")
def edit(task_id: int, req: EditReq, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    if req.title: t.title = req.title
    if req.detail: t.detail = req.detail
    if req.content: t.content = req.content
    db.commit()
    return {"ok": True}


@router.delete("/{task_id}")
def delete(task_id: int, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if t:
        db.delete(t); db.commit()
        return {"ok": True}
    return {"ok": False}


class AddReq(BaseModel):
    user_id: int
    date: date
    subject: str = "语文"
    task_type: str = "custom"   # custom=手写；其余类型由前端传 title/detail/content 或留空
    title: str = ""
    detail: str = ""
    content: str = ""
    points: int = 20

@router.post("")
def add(req: AddReq, db: Session = Depends(get_db)):
    t = Task(user_id=req.user_id, subject=req.subject, date=req.date, task_type=req.task_type,
             title=req.title, detail=req.detail, content=req.content, points=req.points,
             content_status="published")
    db.add(t); db.commit(); db.refresh(t)
    return {"id": t.id}


@router.post("/{task_id}/submit")
def submit(task_id: int, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if t:
        t.submit_status = "submitted"
        db.commit()
        return {"ok": True}
    return {"ok": False}


@router.post("/{task_id}/upload-photo")
async def upload_photo(task_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    import os
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    os.makedirs("uploads/task_photos", exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    path = f"uploads/task_photos/task_{task_id}{ext}"
    with open(path, "wb") as f:
        f.write(await file.read())
    t.photo_path = path
    db.commit()
    return {"ok": True, "path": path}


@router.post("/{task_id}/confirm")
def confirm(task_id: int, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    t.submit_status = "approved"
    db.add(Point(user_id=t.user_id, delta=t.points, reason=f"任务完成：{t.title}"))
    db.commit()
    return {"ok": True, "points": t.points}
```

- [ ] **Step 4: 挂载 router**

在 `backend/app/main.py`：
- import 行加 `tasks`
- 加 `app.include_router(tasks.router)`

```python
from .routers import auth, config_router, pdf, progress, notes, points, learning, goals, mistakes, knowledge, questions, tts_router, annotations, home, tasks
# ...
app.include_router(tasks.router)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_tasks_router.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/tasks.py backend/tests/test_tasks_router.py backend/app/main.py
git commit -m "feat: 任务接口（列/审核/改/删/增/提交/上传/确认）"
```

---

## Task 3: APScheduler 定时生成

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: 挂 BackgroundScheduler**

在 `backend/app/main.py` 文件**最末尾**（所有 `app.include_router(...)` 之后）追加：

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date
from .database import SessionLocal
from .services.task_gen import generate_daily_tasks


def _scheduled_generate():
    db = SessionLocal()
    try:
        generate_daily_tasks(db, date.today())
    finally:
        db.close()


# 测试环境（pytest import main）不启动常驻调度器，避免后台线程干扰测试
import sys
if "pytest" not in sys.modules:
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_scheduled_generate, CronTrigger(hour=3, minute=0), id="daily_tasks",
                       replace_existing=True, misfire_grace_time=3600)
    _scheduler.start()
```

注意：uvicorn `--reload` 会 fork 出 worker，导致 scheduler 可能在多个进程启动；`replace_existing=True` + 固定 job id 可避免同一进程内重复，跨进程重复则靠「幂等生成」（同 `(user_id, subject, date)` 只生成一次）兜底。

- [ ] **Step 2: 手动验证定时任务可触发**

Run: `cd backend && python -c "from app.main import _scheduled_generate; _scheduled_generate(); print('ok')"`
Expected: 打印 `ok`，不报错（会为数据库里所有 child 用户生成当天任务）。

- [ ] **Step 3: 提交**

```bash
git add backend/app/main.py
git commit -m "feat: APScheduler 每天 03:00 定时生成当天任务"
```

---

## Task 4: 孩子端首页接真（renderHome）

**Files:**
- Modify: `frontend/app.js`（renderHome 里 taskCards 部分 + 完成任务逻辑）

- [ ] **Step 1: 加加载与完成任务函数**

在 `frontend/app.js` 里（`let homeSnapshot` 附近）加全局状态：

```javascript
let dailyTasks = [];   // 当天已发布任务
```

加加载函数（放在 `loadHome` 附近）：

```javascript
async function loadTasks(){
  const today = new Date();
  const d = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
  dailyTasks = await api(`/api/tasks?user_id=${uid}&date=${d}&role=child`);
  return dailyTasks;
}
```

- [ ] **Step 2: renderHome 里 taskCards 改为读 dailyTasks**

把 `renderHome` 里的：

```javascript
const taskCards = tasks.map(t=>{
  const done = completed.includes(t.id);
  const detail = t.id===1 ? t.detail.replace('15', String(dictCount > 0 ? dictCount : 15)) : t.detail;
  return `<article class="task-card">...`;
}).join('');
```

替换为（保留原有卡片 HTML 结构，只换数据源与点击行为）：

```javascript
const taskTypeMeta = {
  dictation:{icon:'pen',color:'blue',tag:'当前进度',tagColor:'blue',meta:'约 8 分钟'},
  knowledge:{icon:'brain',color:'green',tag:'重点巩固',tagColor:'green',meta:'约 10 分钟'},
  review:{icon:'brain',color:'green',tag:'遗忘曲线',tagColor:'green',meta:'约 10 分钟'},
  reading:{icon:'book',color:'orange',tag:'阅读理解',tagColor:'orange',meta:'约 12 分钟'},
  listening:{icon:'headphones',color:'blue',tag:'听力理解',tagColor:'blue',meta:'约 8 分钟'},
  custom:{icon:'sparkles',color:'orange',tag:'自定义',tagColor:'orange',meta:''},
};
const taskCards = dailyTasks.map(t=>{
  const m = taskTypeMeta[t.task_type] || taskTypeMeta.custom;
  const approved = t.submit_status === 'approved';
  const submitted = t.submit_status === 'submitted';
  const btn = approved
    ? `<button class="task-btn done">${icon('check',17)}已完成</button>`
    : submitted
      ? `<button class="task-btn done">${icon('clock',17)}等待家长确认</button>`
      : `<button class="task-btn todo" onclick="doTask(${t.id},'${t.task_type}')">开始练习</button>`;
  return `<article class="task-card">
    <div class="top">
      <div class="task-ic ${m.color}">${icon(m.icon,23)}</div>
      <div style="min-width:0;flex:1">
        <div class="t-head"><span class="task-tag badge-${m.tagColor}">${m.tag}</span></div>
        <h3>${t.title}</h3>
        <div class="detail">${t.detail}</div>
      </div>
    </div>
    <div class="foot">
      <span class="task-meta">${icon('clock',14)}${m.meta}</span>
      <span class="task-points">${icon('star',14)}+${t.points}</span>
    </div>
    ${btn}
  </article>`;
}).join('');

if(taskCards === ''){ /* 无任务时的空态 */ }
```

- [ ] **Step 3: 加 doTask 函数与 renderHome 调用 loadTasks**

```javascript
async function doTask(id, type){
  if(type==='dictation'){ await startDictation(); return; }
  if(type==='reading'){ await loadCenter(); centerTab='阅读理解'; setPage('学习中心'); return; }
  if(type==='listening'){ await loadCenter(); centerTab='听力理解'; setPage('学习中心'); return; }
  if(type==='knowledge' || type==='review'){ setPage('学习中心'); return; }
  // custom / 其余：标记提交，等待家长确认
  await api(`/api/tasks/${id}/submit`, {method:'POST'});
  toast('已提交，等待家长确认');
  render();
}
```

`renderHome` 开头 `await loadHome();` 后加 `await loadTasks();`。

- [ ] **Step 4: 浏览器验证**

刷新前端页面，确认首页任务卡来自后端（此时若无已审核任务，任务区应显示空态）。

- [ ] **Step 5: 提交**

```bash
git add frontend/app.js
git commit -m "feat: 孩子端首页任务卡改读后端真实任务"
```

---

## Task 5: 家长端「任务」tab（内容审核 + 完成审核 + 新增）

**Files:**
- Modify: `frontend/app.js`（家长端 tab 与渲染函数）

- [ ] **Step 1: 加家长端任务 tab**

在家长端 tab 数组（`renderParent` 里，现有 教材/知识点/目标/报告/规则/设置）加「任务」。找到 `parentTab` 相关渲染，加 `'任务'` 项。具体：`renderParent` 里 tab 列表处追加 `['任务','check']`（图标名需在 ICONS 里存在，可用 'check' 或 'sparkles'）。

- [ ] **Step 2: 加加载与渲染函数**

```javascript
let parentTaskDate = '';
let childUserId = 0;   // 当前孩子的 user_id（系统目前单孩子，init 登录后赋值 uid）
async function loadParentTasks(){
  if(!parentTaskDate){
    const t = new Date();
    parentTaskDate = `${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,'0')}-${String(t.getDate()).padStart(2,'0')}`;
  }
  return await api(`/api/tasks?user_id=${childUserId || uid}&date=${parentTaskDate}&role=parent`);
}
async function renderParentTasks(){
  const list = await loadParentTasks();
  const typeName = {dictation:'听写',knowledge:'基础练习',review:'复习',reading:'阅读理解',listening:'听力理解',custom:'自由任务'};
  const rows = list.map(t=>`
    <div class="task-row">
      <div class="tr-main">
        <span class="tr-type">${typeName[t.task_type]||t.task_type}</span>
        <span class="tr-title">${t.title}</span>
        <span class="tr-detail">${t.detail}</span>
        <span class="tr-status">${t.content_status==='pending_review'?'待审核':(t.submit_status==='submitted'?'待完成审核':(t.submit_status==='approved'?'已完成':'已发布'))}</span>
      </div>
      <div class="tr-actions">
        ${t.content_status==='pending_review'?`<button onclick="approveTask(${t.id})">通过</button>`:''}
        ${t.submit_status==='submitted'?`<button onclick="confirmTask(${t.id})">确认完成</button>`:''}
        ${t.submit_status==='submitted'&&t.photo_path?`<a href="/${t.photo_path}" target="_blank">查看照片</a>`:''}
        <button onclick="deleteTask(${t.id})">删除</button>
      </div>
    </div>`).join('');
  return `
  <header class="page-head"><div><h1>今日任务</h1><p class="desc">凌晨自动生成，审核后孩子可见。</p></div>
    <div style="display:flex;gap:8px">
      <button class="btn-primary" onclick="approveAllTasks()">全部通过</button>
      <button class="btn-primary" onclick="showAddTask()">新增任务</button>
    </div>
  </header>
  <div class="task-list">${rows||'<p style="color:#8e9691;padding:32px 0;text-align:center">暂无任务</p>'}</div>`;
}
```

- [ ] **Step 3: 加操作函数**

```javascript
async function approveTask(id){ await api(`/api/tasks/${id}/approve`,{method:'POST'}); renderParent(); }
async function approveAllTasks(){ await api(`/api/tasks/approve-all`,{method:'POST',body:{user_id:childUserId||uid,date:parentTaskDate}}); renderParent(); }
async function deleteTask(id){ await api(`/api/tasks/${id}`,{method:'DELETE'}); renderParent(); }
async function confirmTask(id){ await api(`/api/tasks/${id}/confirm`,{method:'POST'}); toast('已确认，积分已发放'); renderParent(); }
async function showAddTask(){
  // 简化：直接新增一条自由任务，或弹窗选类型（类型选择留作交互增强）
  const title = prompt('任务标题');
  if(!title) return;
  await api(`/api/tasks`,{method:'POST',body:{user_id:childUserId||uid,date:parentTaskDate,task_type:'custom',title:title,detail:'',points:20}});
  renderParent();
}
```

（注：`childUserId` 在 `init()` 登录成功后赋值 `childUserId = u.id`，与 `uid` 同源；系统目前单孩子。）

- [ ] **Step 4: 接线 renderParent**

在 `renderParent()` 里，当 `parentTab==='任务'` 时返回 `renderParentTasks()` 的异步结果（需 `renderParent` 支持 await 该分支）。

- [ ] **Step 5: 浏览器验证 + 提交**

```bash
git add frontend/app.js
git commit -m "feat: 家长端任务审核 tab（内容审核/完成审核/新增）"
```

---

## Task 6: 听写拍照上传闭环

**Files:**
- Modify: `frontend/app.js`（孩子端听写完成后拍照上传）

- [ ] **Step 1: 听写完成时拍照上传**

修改 `finishDictation()`，在提交完成前弹出拍照/选图，上传到任务：

```javascript
async function finishDictation(){
  const s = dictState;
  const wrongWords = s.wrong.map(x=>({word:x.word, your_answer:x.yours}));
  const d = await api('/api/dictation/complete', {method:'POST', body:{user_id:uid, correct:s.correct, wrong:s.wrong.length, wrong_words:wrongWords}});
  // 拍照上传：找当天听写任务并上传照片
  const today = new Date();
  const day = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
  const tasks = await api(`/api/tasks?user_id=${uid}&date=${day}&role=child`);
  const dict = tasks.find(t=>t.task_type==='dictation' && t.submit_status!=='approved');
  if(dict){
    await api(`/api/tasks/${dict.id}/submit`, {method:'POST'});
    // 拍照：简单起见用 prompt 说明，实际用文件选择器
    if(confirm('请拍照上传你的听写字迹，家长核对后发放积分。现在上传？')){
      const input = document.createElement('input');
      input.type='file'; input.accept='image/*';
      input.onchange = async ()=>{
        const fd = new FormData();
        fd.append('file', input.files[0]);
        await fetch(`${API}/api/tasks/${dict.id}/upload-photo`, {method:'POST', body:fd});
        toast('已上传，等待家长确认');
      };
      input.click();
    }
  }
  await loadPoints();
  setPage('学习首页');
  toast(`完成打卡，获得 ${d.points_awarded} 积分`);
}
```

- [ ] **Step 2: 浏览器验证**

完成一次听写，确认上传照片路径正确、家长端能看到照片链接。

- [ ] **Step 3: 提交**

```bash
git add frontend/app.js
git commit -m "feat: 听写完成拍照上传，家长核对后发积分"
```

---

## 完成标准

- [ ] 后端：`Task` 表 + 生成服务 + 接口 + 定时任务全部可用，单测通过
- [ ] 孩子端首页任务来自后端，按科目、真实内容展示
- [ ] 家长端能审核（通过/全部通过/删除/新增）、完成审核（看照片发积分）
- [ ] 听写拍照上传 → 家长核对 → 积分闭环打通
