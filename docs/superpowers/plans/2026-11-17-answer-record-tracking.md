# 当天做题明细跟踪与监管 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 家长端「报告」Tab 新增「当天做题明细」——新建 `AnswerRecord` 表，四个做题入口（题库/边读边问/每日任务/专项训练）判分后逐题写入，家长按科目/模块分组查看题目、孩子答案、标准答案、对错、耗时、难度。

**Architecture:** 纯后端新增一张 `answer_records` 表 + 写入 helper + 查询接口，四个既有判分端点各加几行埋点；前端家长端报告 Tab 加一块明细视图，学生端做题页加前端计时。与现有 `Mistake`（错题本）并存，不破坏既有逻辑。

**Tech Stack:** FastAPI + SQLAlchemy；parent-web 原生 JS 单文件；Flutter（audioplayers 无关，本次只改做题页计时）。

**设计文档：** `docs/superpowers/specs/2026-11-17-answer-record-tracking-design.md`

---

## 文件结构

- 修改 `backend/app/models.py` —— 新增 `AnswerRecord` 表。
- 新增 `backend/app/services/answer_record.py` —— `record_answer()` 写入 helper。
- 新增 `backend/app/routers/answer_records.py` —— `GET /api/answer-records` 查询接口。
- 修改 `backend/app/main.py` —— `include_router(answer_records.router)`。
- 修改 `backend/app/routers/bank.py` / `quiz.py` / `tasks.py` —— 埋点写入。
- 修改 `parent-web/app.js` —— 报告 Tab 加明细视图 + `loadAnswerRecords()`。
- 修改 `backend/tests/` —— 模型/接口/埋点单测。

> 说明：`duration_ms` 由前端计时传入，但前端（Flutter）改动独立成 Task 8，后端埋点默认 `duration_ms=None`，不影响主链路。专项训练是「回忆式」作答（无文本答案），埋点时 `student_answer`/`correct_answer` 取空串或 `common_mistake` 里的 correct。

---

## Task 1: `AnswerRecord` 模型 + 写入 helper

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/services/answer_record.py`
- Test: `backend/tests/test_answer_record.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_answer_record.py`：

```python
from app.models import AnswerRecord


def test_answer_record_fields(setup_db, db):
    r = AnswerRecord(user_id=1, subject="英语", module="dictation",
                     question="apple", student_answer="apple", correct_answer="apple",
                     is_correct=True, difficulty="easy", duration_ms=3200,
                     source_type="word_bank", source_id=7)
    db.add(r); db.commit()
    got = db.query(AnswerRecord).filter_by(user_id=1).one()
    assert got.subject == "英语"
    assert got.module == "dictation"
    assert got.is_correct is True
    assert got.duration_ms == 3200
    assert got.source_type == "word_bank"
    assert got.source_id == 7
    assert got.created_at is not None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_answer_record.py -q`
Expected: FAIL（`AnswerRecord` 未定义）。

- [ ] **Step 3: 实现模型**

在 `backend/app/models.py` 末尾（`TrainingPlan` 类之后）追加：

```python
class AnswerRecord(Base):
    """做题明细：每次作答一行，家长端「当天做题明细」监管用。"""
    __tablename__ = "answer_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(16), default="")        # 语文/英语/数学
    module: Mapped[str] = mapped_column(String(32), default="")          # dictation/reading/listening/quiz/drill/practice
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=True)
    question: Mapped[str] = mapped_column(LongText)
    student_answer: Mapped[str] = mapped_column(LongText, default="")
    correct_answer: Mapped[str] = mapped_column(LongText, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    difficulty: Mapped[str] = mapped_column(String(16), default="")      # easy/medium/hard
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)     # 前端计时
    source_type: Mapped[str] = mapped_column(String(16), default="")     # question|word_bank|training_item|quiz|task
    source_id: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

（`String`/`LongText`/`Boolean`/`Integer`/`DateTime`/`datetime` 均已在该文件顶部 import，无需新增 import。）

- [ ] **Step 4: 实现写入 helper**

创建 `backend/app/services/answer_record.py`：

```python
"""做题明细写入 helper：各做题入口判分后逐题调用。"""
from sqlalchemy.orm import Session

from ..models import AnswerRecord


def record_answer(
    db: Session,
    *,
    user_id: int,
    subject: str,
    module: str,
    question: str,
    student_answer: str = "",
    correct_answer: str = "",
    is_correct: bool = False,
    difficulty: str = "",
    duration_ms: int | None = None,
    source_type: str = "",
    source_id: int | None = None,
    lesson_id: int | None = None,
    bucket_id: int | None = None,
) -> AnswerRecord:
    row = AnswerRecord(
        user_id=user_id, bucket_id=bucket_id, subject=subject or "",
        module=module, lesson_id=lesson_id, question=question or "",
        student_answer=student_answer or "", correct_answer=correct_answer or "",
        is_correct=is_correct, difficulty=difficulty or "",
        duration_ms=duration_ms, source_type=source_type, source_id=source_id,
    )
    db.add(row)
    return row
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_answer_record.py -q`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/services/answer_record.py backend/tests/test_answer_record.py
git commit -m "feat(db): AnswerRecord 做题明细表 + 写入 helper"
```

---

## Task 2: 查询接口 `GET /api/answer-records`

**Files:**
- Create: `backend/app/routers/answer_records.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_answer_records_api.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_answer_records_api.py`：

```python
from datetime import date, datetime, timedelta
from app.models import User, AnswerRecord
from app.services.answer_record import record_answer


def _child(db, name="晨晨"):
    u = User(name=name, role="child"); db.add(u); db.commit(); return u


def test_list_today_records(client, setup_db, db):
    child = _child(db)
    today = datetime.utcnow()
    record_answer(db, user_id=child.id, subject="英语", module="dictation",
                  question="apple", student_answer="apple", correct_answer="apple",
                  is_correct=True, source_type="word_bank", source_id=1)
    # 昨天的一条不应出现在「当天」
    old = AnswerRecord(user_id=child.id, subject="英语", module="dictation",
                       question="banana", is_correct=False,
                       created_at=today - timedelta(days=1))
    db.add(old); db.commit()

    resp = client.get(f"/api/answer-records?user_id={child.id}&date={date.today().isoformat()}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["records"][0]["question"] == "apple"
    assert data["records"][0]["is_correct"] is True
```

> 依赖 `client` 与 `setup_db`/`db` fixture（conftest.py 已有）。若 `client` fixture 名不同，以 conftest.py 为准。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_answer_records_api.py -q`
Expected: FAIL（路由不存在 → 404）。

- [ ] **Step 3: 实现接口**

创建 `backend/app/routers/answer_records.py`：

```python
"""做题明细查询：家长/管理员查某孩子某天的逐题作答。"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.deps import require_role
from ..database import get_db
from ..models import AnswerRecord, User

router = APIRouter(prefix="/api/answer-records", tags=["answer-records"])


@router.get("")
def list_answer_records(
    user_id: int,
    date: date | None = None,
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    child = db.get(User, user_id)
    if child is None or child.role != "child":
        raise HTTPException(status_code=404, detail="孩子不存在")
    # 「当天」按东八区（Asia/Shanghai）切：UTC 当日 0 点 + 8h 偏移
    d = date or datetime.utcnow().date()
    day_start_utc = datetime(d.year, d.month, d.day) - timedelta(hours=8)
    day_end_utc = day_start_utc + timedelta(days=1)
    rows = (
        db.query(AnswerRecord)
        .filter(AnswerRecord.user_id == user_id,
                AnswerRecord.created_at >= day_start_utc,
                AnswerRecord.created_at < day_end_utc)
        .order_by(AnswerRecord.created_at)
        .all()
    )
    records = [
        {
            "id": r.id, "subject": r.subject, "module": r.module,
            "question": r.question, "student_answer": r.student_answer,
            "correct_answer": r.correct_answer, "is_correct": r.is_correct,
            "difficulty": r.difficulty, "duration_ms": r.duration_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return {"total": len(records), "records": records}
```

- [ ] **Step 4: 注册路由**

在 `backend/app/main.py` 的 `include_router` 区（`include_router(knowledge_pool.router)` 附近）加：

```python
app.include_router(answer_records.router)
```

并在顶部 import 区加 `from .routers import answer_records`（与其它 router import 并列）。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_answer_records_api.py -q`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/answer_records.py backend/app/main.py backend/tests/test_answer_records_api.py
git commit -m "feat(api): GET /api/answer-records 当天做题明细查询"
```

---

## Task 3: 题库练习埋点（bank.py submit）

**Files:**
- Modify: `backend/app/routers/bank.py:355-392`

- [ ] **Step 1: 埋点写入**

在 `submit_bank` 里，判分后对**每一题**（不只错题）写 `AnswerRecord`。在现有 `if r["is_correct"] is False:` 写 Mistake 的循环里，改成对每道题都写明细。

在函数顶部 import 区（第 24 行附近）加：

```python
from ..services.answer_record import record_answer
```

把 `submit_bank` 的判分循环（第 366-389 行）改为：

```python
    for a in req.answers:
        qid = a.get("question_id")
        qq = by_id.get(qid)
        if qq is None:
            results.append({"question_id": qid, "is_correct": False})
            continue
        answer_json = json.loads(qq.answer_json or "{}")
        student = {k: a.get(k) for k in ("selected_index", "blanks", "pairs", "text") if a.get(k) is not None}
        if qq.qtype_category == "subjective":
            r = grade_subjective_with_ai(db, answer_json, student)
        else:
            r = grade_question(qq.qtype_category, answer_json, student)
        results.append({"question_id": qq.id, "is_correct": r["is_correct"],
                        "correct_answer_text": r["correct_answer_text"], "detail": r["detail"]})
        # 做题明细：每题一行
        record_answer(
            db, user_id=user.id, subject=qq.subject or "",
            module="practice", lesson_id=qq.lesson_id,
            question=qq.question,
            student_answer=_format_student_answer(a, qq),
            correct_answer=r.get("correct_answer_text") or qq.answer,
            is_correct=r["is_correct"] is True,
            difficulty=qq.difficulty or "",
            duration_ms=a.get("duration_ms"),
            source_type="question", source_id=qq.id,
        )
        if r["is_correct"] is False:
            bid = resolve_bucket_id(db, user.id, None)
            db.add(Mistake(
                user_id=user.id,
                source_type="bank",
                question=qq.question,
                your_answer=_format_student_answer(a, qq),
                correct_answer=r.get("correct_answer_text") or qq.answer,
                bucket_id=bid,
            ))
```

（`BankSubmitReq.answers` 里的每个 dict 现在可额外带 `duration_ms`，前端 Task 8 会带上。）

- [ ] **Step 2: analyze + 测试**

Run: `cd backend && python -m pytest tests/test_bank.py -q`（若存在；否则 `python -c "import ast; ast.parse(open('app/routers/bank.py',encoding='utf-8').read())"`）
Expected: 无报错。

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/bank.py
git commit -m "feat(bank): 题库练习判分后写 AnswerRecord 明细"
```

---

## Task 4: 边读边问埋点（quiz.py submit）

**Files:**
- Modify: `backend/app/routers/quiz.py:83-134`

- [ ] **Step 1: 埋点写入**

在 `quiz_submit` 的 `record_quiz_mistake` 循环（第 121-131 行）处，改为对每题都写明细。

函数顶部 import（第 10 行附近）加：

```python
from ..services.answer_record import record_answer
```

把 `if quiz.user_id:` 下那个 `for q, r in zip(questions, results): if r["is_correct"]: continue ...` 的错题循环，改为：

```python
    if quiz.user_id:
        from ..services.quiz import record_quiz_mistake
        for q, r in zip(questions, results):
            sel = next((a.get("selected_index") for a in req.answers
                        if a.get("question_id") == q["id"]), None)
            your = (q["choices"][sel]
                    if isinstance(sel, int) and 0 <= sel < len(q["choices"]) else "")
            correct = q["choices"][q["correct_index"]]
            record_answer(
                db, user_id=quiz.user_id, subject="", module="quiz",
                lesson_id=quiz.lesson_id,
                question=q["prompt"], student_answer=your,
                correct_answer=correct, is_correct=r["is_correct"] is True,
                source_type="quiz", source_id=q["id"],
                duration_ms=next((a.get("duration_ms") for a in req.answers
                                  if a.get("question_id") == q["id"]), None),
                bucket_id=quiz.bucket_id,
            )
            if not r["is_correct"]:
                record_quiz_mistake(db, quiz.user_id, q["prompt"], your, correct,
                                    q.get("knowledge_point_id"),
                                    bucket_id=quiz.bucket_id)
```

（`subject` 取空串：quiz 未直接存学科，可后续从 lesson 推导，先留空。）

- [ ] **Step 2: 测试**

Run: `cd backend && python -c "import ast; ast.parse(open('app/routers/quiz.py',encoding='utf-8').read()); print('ok')"`
Expected: ok。

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/quiz.py
git commit -m "feat(quiz): 边读边问判分后写 AnswerRecord 明细"
```

---

## Task 5: 每日任务·基础知识埋点（tasks.py knowledge-review）

**Files:**
- Modify: `backend/app/routers/tasks.py:216-254`

- [ ] **Step 1: 埋点写入**

在 `knowledge_review` 的判分循环里（第 238-248 行），每题写明细。import 加：

```python
from ..services.answer_record import record_answer
```

把循环改为（在 `record_attempt` 之后追加）：

```python
    for a in req.answers:
        p = by_id.get(a.get("id"))
        if p is None:
            continue
        user_answer = (a.get("user_answer") or "").strip()
        is_correct, _ = grade_knowledge_answer(
            user_answer, p.get("keywords") or [], p.get("answer") or "", db=db)
        if p.get("id"):
            record_attempt(db, req.user_id, "knowledge", p["id"], is_correct,
                           bucket_id=bid)
        record_answer(
            db, user_id=req.user_id, subject="", module="knowledge",
            question=p.get("question") or p.get("content") or "",
            student_answer=user_answer,
            correct_answer=p.get("answer") or "",
            is_correct=is_correct,
            source_type="knowledge_point", source_id=p.get("id"),
            duration_ms=a.get("duration_ms"), bucket_id=bid,
        )
        p["last_correct"] = is_correct
        results.append({"id": p.get("id"), "is_correct": is_correct, "answer": p.get("answer") or ""})
```

> 说明：`p` 是 task content JSON 里的知识点 dict，字段以实际为准（可能是 `content`/`question`/`answer`/`keywords`）。若字段名不同，以 `tasks.py` 里 `_gen_knowledge` 生成的实际 key 为准；计划里的 `p.get("question") or p.get("content")` 是兜底写法。

- [ ] **Step 2: 测试**

Run: `cd backend && python -c "import ast; ast.parse(open('app/routers/tasks.py',encoding='utf-8').read()); print('ok')"`
Expected: ok。

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/tasks.py
git commit -m "feat(tasks): 基础知识任务判分后写 AnswerRecord 明细"
```

---

## Task 6: 专项训练埋点（tasks.py drill-complete）

**Files:**
- Modify: `backend/app/routers/tasks.py:469-511`

- [ ] **Step 1: 埋点写入**

`drill_complete` 的 `req.results` 是 `{item_id: is_correct}`，无文本答案。在判分循环里（第 485-502 行）加埋点，题目/标准答案从 `TrainingItem` 查。

在循环内（`m.next_review_at = ...` 之后、`if nh:` 之前）追加：

```python
        from ..models import TrainingItem
        item = db.get(TrainingItem, int(item_id))
        if item is not None:
            record_answer(
                db, user_id=user.id, subject="", module="drill",
                question=item.primary,
                student_answer="",  # 回忆式作答，无文本答案
                correct_answer=(item.common_mistake or ""),
                is_correct=bool(is_correct),
                difficulty="", source_type="training_item",
                source_id=int(item_id), bucket_id=t.bucket_id,
            )
```

（`record_answer` 已在 Task 5 import；若 Task 5 与 6 分开执行，需各自确保 import 存在。）

- [ ] **Step 2: 测试**

Run: `cd backend && python -c "import ast; ast.parse(open('app/routers/tasks.py',encoding='utf-8').read()); print('ok')"`
Expected: ok。

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/tasks.py
git commit -m "feat(tasks): 专项训练完成后写 AnswerRecord 明细"
```

---

## Task 7: 家长端报告视图（parent-web）

**Files:**
- Modify: `parent-web/app.js`（`renderReportTab` 约 2479 行、`loadReport` 区、状态区）

- [ ] **Step 1: 加状态 + 加载函数**

在状态声明区（`let reportRows = []` 附近，第 77 行）加：

```js
let answerRecords = [];   // 当天做题明细 [{subject,module,question,student_answer,correct_answer,is_correct,difficulty,duration_ms,created_at}]
```

在 `loadReport` 附近加：

```js
async function loadAnswerRecords(){
  if(!uid){ answerRecords = []; return; }
  const u = uid;
  const today = new Date();
  const d = today.toISOString().slice(0,10);
  const r = await api(`/api/answer-records?user_id=${u}&date=${d}`);
  if(u === uid) answerRecords = Array.isArray(r?.records) ? r.records : [];
}
```

在切换 Tab 的 `loadReport` 调用处（第 277/451 行），把「报告」分支改为同时加载：

```js
  else if(parentTab==='报告') await Promise.all([loadReport(), loadMasteryReport(), loadAnswerRecords()]);
```

（两处都要改：第 277 行的 `switchTab` 内、第 451 行的 `if(t==='报告')` 内。）

- [ ] **Step 2: 渲染明细面板**

在 `renderReportTab()` 返回的 `parent-grid` 里，「掌握度报告」panel 之后追加一个 panel：

```js
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic blue">${icon('list',20)}</div>
        <div><h3>当天做题明细</h3><div class="sub">按科目/模块分组，逐题查看题目、孩子答案与标准答案</div></div></div>
      <div class="bd">${renderAnswerRecords()}</div>
    </div>
```

新增渲染函数（放在 `renderReportTab` 之后）：

```js
function renderAnswerRecords(){
  if(!answerRecords.length) return '<p style="font-size:13px;color:var(--gray2)">今天还没有做题记录</p>';
  // 按 subject → module 分组，组内按题目聚合轨迹
  const groups = {};
  for(const r of answerRecords){
    const s = r.subject || '其他';
    const m = r.module || '其他';
    (groups[s] ??= {})[m] ??= [];
    groups[s][m].push(r);
  }
  const MODULE_LABEL = {dictation:'听写',reading:'阅读',listening:'听力',quiz:'边读边问',drill:'专项训练',practice:'题库练习',knowledge:'基础知识'};
  return Object.entries(groups).map(([subject, modules])=>`
    <div style="margin-bottom:16px">
      <div style="font-size:14px;font-weight:700;color:var(--ink2);margin-bottom:8px">${escapeAttr(subject)}</div>
      ${Object.entries(modules).map(([module, rs])=>`
        <div style="margin-left:12px;margin-bottom:10px">
          <div style="font-size:13px;font-weight:600;color:var(--gray2);margin-bottom:6px">${MODULE_LABEL[module]||module} · ${rs.length} 题</div>
          ${rs.map((r,i)=>`
            <div style="padding:8px 10px;border-radius:8px;background:var(--bg2);margin-bottom:6px;font-size:13px">
              <div style="display:flex;gap:8px;align-items:flex-start">
                <span style="color:${r.is_correct?'var(--green2)':'var(--orange2)'};font-weight:700">${r.is_correct?'✓':'✗'}</span>
                <div style="flex:1">
                  <div>${escapeAttr(r.question)}</div>
                  ${r.student_answer?`<div style="color:var(--gray2)">你的答案：${escapeAttr(r.student_answer)}</div>`:''}
                  <div style="color:var(--gray2)">标准答案：${escapeAttr(r.correct_answer)}</div>
                  ${r.duration_ms?`<span style="color:#8e9691;font-size:12px">${Math.round(r.duration_ms/1000)}s</span>`:''}
                </div>
              </div>
            </div>`).join('')}
        </div>`).join('')}
    </div>`).join('');
}
```

- [ ] **Step 3: 手动验证**

Run: `python -m http.server 8767 --directory parent-web`（从仓库根），浏览器打开 `http://127.0.0.1:8767`，登录家长账号 → 「报告」Tab，确认出现「当天做题明细」面板。

- [ ] **Step 4: Commit**

```bash
git add parent-web/app.js
git commit -m "feat(parent-web): 报告 Tab 新增当天做题明细"
```

---

## Task 8: 学生端做题页前端计时（duration_ms）

**Files:**
- Modify: `student-app/lib/features/...`（各做题页：题库练习、边读边问、专项训练、每日任务）

- [ ] **Step 1: 定位做题提交点**

用 `grep -rn "submit\|/submit\|duration" student-app/lib/features/` 找到各做题页的提交函数。对每个提交，在进入做题页时记录 `DateTime.now()`，提交时算 `duration_ms = 差值.inMilliseconds`，随请求体带上。

- [ ] **Step 2: 逐页加计时 + 提交带 duration_ms**

以题库练习页为例（路径以实际为准），模式如下：

```dart
// 进入页面/加载题目时
final _startedAt = DateTime.now();

// 提交时
final durationMs = DateTime.now().difference(_startedAt).inMilliseconds;
// 请求体 answers 每项或顶层带上 duration_ms
```

> 具体文件路径与字段名在执行时以 `grep` 结果为准；本步骤是「模式复制」而非精确到行的改动，各做题页结构类似。

- [ ] **Step 3: analyze + 测试**

Run: `cd student-app && E:/dev/flutter/bin/flutter.bat analyze && E:/dev/flutter/bin/flutter.bat test`
Expected: 无 error；测试全绿。

- [ ] **Step 4: Commit**

```bash
git add student-app/lib/features/
git commit -m "feat(student-app): 做题页前端计时并随提交带 duration_ms"
```

---

## Task 9: 收尾验证

- [ ] **Step 1: 全量后端测试**

Run: `cd backend && python -m pytest -q`
Expected: 全绿（含新增 answer_record 相关测试）。

- [ ] **Step 2: 端到端手测**

1. 启动后端 `cd backend && python -m uvicorn app.main:app --port 8010`。
2. 孩子端做几道题（题库/边读边问/听写/专项训练）。
3. 家长端「报告」Tab 看「当天做题明细」，确认题目/答案/标准答案/对错齐全，先错后对折叠展示正确。

- [ ] **Step 3: 对照设计文档核对**

核对 `docs/superpowers/specs/2026-11-17-answer-record-tracking-design.md`：表字段、四入口埋点、报告视图、耗时/难度、先错后对轨迹。列出未覆盖项（若有）。

---

## 自检记录（Self-Review）

- **Spec 覆盖**：AnswerRecord 表（Task 1）→ 查询接口（Task 2）→ 四入口埋点（Task 3-6）→ 报告视图（Task 7）→ 前端计时（Task 8）→ 收尾（Task 9）。全部设计章节有对应任务。
- **类型一致性**：`record_answer` 签名（Task 1）与各埋点调用（Task 3-6）参数名一致；`AnswerRecord` 字段名与查询接口返回、前端读取一致。
- **已知降级**：quiz 的 `subject` 留空（未存学科）；专项训练无文本答案（`student_answer=""`、`correct_answer` 取 common_mistake）；Task 8 前端计时是模式描述而非精确行号（执行时 grep 定位）。
