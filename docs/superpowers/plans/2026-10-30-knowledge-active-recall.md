# 基础知识主动复习（简答+遗忘曲线闭环）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「基础知识复习」从主观自评改为逐题简答主动回忆，判分结果（对/错）驱动 `KnowledgeMastery` 遗忘曲线。

**Architecture:** 新建 `knowledge_quiz.py`（知识点→简答题 + 混合判分）；`task_gen._gen_knowledge` 预生成时把知识点转成问答存进 task.content；`tasks.py` 的 `knowledge-review` 接收孩子答案、判分、落掌握度；前端 `renderKnowledge` 改成「输入答案→判分→标准答案→答错重答」。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite；前端原生 JS 单文件；pytest。

---

## 文件结构

- `backend/app/services/knowledge_quiz.py`（新建）— 知识点→简答题出题 + 混合判分
- `backend/app/services/task_gen.py`（改）— `_gen_knowledge` 出题转问答
- `backend/app/routers/tasks.py`（改）— `knowledge-review` 接收答案、判分、落掌握度
- `frontend/app.js`（改）— `renderKnowledge` 简答交互
- `backend/tests/test_knowledge_quiz.py`（新建）
- `backend/tests/test_task_gen.py`（扩展）
- `backend/tests/test_tasks_router.py`（扩展）

---

## Task 1: 知识点→简答题出题 + 混合判分服务

**Files:**
- Create: `backend/app/services/knowledge_quiz.py`
- Test: `backend/tests/test_knowledge_quiz.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_knowledge_quiz.py`：

```python
from app.database import SessionLocal
from app.services.knowledge_quiz import generate_knowledge_questions, grade_knowledge_answer, FALLBACK_QUESTION


def test_generate_fake_provider_returns_fallback():
    db = SessionLocal()
    pts = [{"id": 1, "content": "圆的周长公式", "category": "公式"}]
    out = generate_knowledge_questions(db, pts, subject="数学")
    assert isinstance(out, list) and len(out) == 1
    # fake provider 回退：question 为空，保留 id/content
    assert out[0]["id"] == 1
    assert "content" in out[0]
    db.close()


def test_grade_knowledge_answer_rule_keyword_match():
    # 关键词命中 → 判对（规则，不走 AI）
    keywords = ["π", "直径", "周长"]
    ok, _ = grade_knowledge_answer("周长等于π乘以直径", keywords, answer="周长=π×直径")
    assert ok is True


def test_grade_knowledge_answer_rule_keyword_miss():
    # 关键词全不命中 → 判错（规则）
    ok, _ = grade_knowledge_answer("不知道", keywords=["π", "直径"], answer="周长=π×直径")
    assert ok is False


def test_grade_knowledge_answer_partial_uses_ai(mocker):
    # 命中率落在中间（0<命中<阈值）→ 走 AI 兜底（这里 mock AI 判对）
    db = SessionLocal()
    mocker.patch("app.services.knowledge_quiz._ai_grade", return_value=True)
    ok, used_ai = grade_knowledge_answer("大约是3.14乘直径", keywords=["π", "直径"], answer="周长=π×直径", db=db)
    assert ok is True
    assert used_ai is True
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_knowledge_quiz.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 写最小实现**

创建 `backend/app/services/knowledge_quiz.py`：

```python
"""知识点主动复习：知识点→简答题出题 + 混合判分（规则优先，AI 兜底）。"""
import json

from sqlalchemy.orm import Session

from .ai import get_provider
from .mastery import grade_answer

FALLBACK_QUESTION = ""   # 无 AI 时 question 为空，判分退化关键词匹配

# 规则判分关键词命中阈值（与 mastery.grade_answer 的 open 题型一致）
_HIT_THRESHOLD = 0.6


def generate_knowledge_questions(db: Session, points: list[dict], subject: str) -> list[dict]:
    """把知识点列表转成简答题，返回 [{id, content, category, question, answer, keywords}]。

    任何异常/fake provider 回退：question 为空字符串，answer 空，keywords 空。
    """
    provider = get_provider(db)
    if provider.name == "fake":
        return [{"id": p.get("id"), "content": p.get("content", ""),
                 "category": p.get("category", ""), "question": FALLBACK_QUESTION,
                 "answer": "", "keywords": []} for p in points]
    prompt = (
        f"针对下面每个知识点出一道简答题，让孩子凭记忆作答，检验是否真正掌握。\n"
        f"知识点列表（JSON，含 id / content / category）：\n"
        f"{json.dumps(points, ensure_ascii=False)}\n"
        '只返回 JSON：{"questions":[{"id":知识点id,"question":"问题","answer":"标准答案",'
        '"keywords":["判分关键词1","关键词2"]}]}。keywords 是判断孩子答对所需的关键词，3~5 个。'
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是出题老师。", json_mode=True)
        data = json.loads(raw)
        qmap = {q.get("id"): q for q in (data.get("questions") or [])}
    except Exception:
        qmap = {}
    out = []
    for p in points:
        q = qmap.get(p.get("id"), {})
        out.append({
            "id": p.get("id"), "content": p.get("content", ""),
            "category": p.get("category", ""),
            "question": (q.get("question") or "").strip(),
            "answer": (q.get("answer") or "").strip(),
            "keywords": [k.strip() for k in (q.get("keywords") or []) if k.strip()],
        })
    return out


def _hit_rate(user_answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    matched = sum(1 for kw in keywords if kw in user_answer)
    return matched / len(keywords)


def _ai_grade(db: Session, user_answer: str, answer: str) -> bool:
    provider = get_provider(db)
    if provider.name == "fake":
        return False
    try:
        raw = provider.generate(
            prompt=f"孩子的答案是「{user_answer}」，标准答案是「{answer}」。孩子答对了吗？只返回 true 或 false。",
            system="你是判分老师。", json_mode=False)
        return raw.strip().lower().startswith("true")
    except Exception:
        return False


def grade_knowledge_answer(user_answer: str, keywords: list[str], answer: str,
                           db: Session | None = None) -> tuple[bool, bool]:
    """混合判分。返回 (is_correct, used_ai)。

    - 关键词命中 >= 阈值 → 判对（规则）
    - 关键词全不命中且答案为空 → 判错（规则）
    - 中间态（0 < 命中 < 阈值）→ AI 兜底
    """
    ua = (user_answer or "").strip()
    if not ua:
        return False, False
    rate = _hit_rate(ua, keywords)
    if rate >= _HIT_THRESHOLD:
        return True, False
    if rate == 0.0:
        return False, False
    # 中间态：走 AI 兜底（db 提供时）
    if db is not None:
        return _ai_grade(db, ua, answer), True
    return False, False
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_knowledge_quiz.py -v`
Expected: PASS（4 个测试全过；注意 `mocker` 来自 pytest-mock，确认 conftest 或环境有 pytest-mock，若没有则改用 monkeypatch）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/knowledge_quiz.py backend/tests/test_knowledge_quiz.py
git commit -m "feat: 知识点→简答题出题 + 混合判分（规则优先 AI 兜底）"
```

---

## Task 2: `_gen_knowledge` 预生成转问答

**Files:**
- Modify: `backend/app/services/task_gen.py`
- Test: `backend/tests/test_task_gen.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_task_gen.py` 追加：

```python
def test_gen_knowledge_content_has_question_fields():
    db = SessionLocal()
    uid, l1_id = _setup(db)  # 第1课含 1 个知识点 "形近字辨析"
    generate_tasks_for_user(db, uid, date.today())
    t = db.query(Task).filter_by(user_id=uid, subject="语文", date=date.today(),
                                 task_type="knowledge").first()
    assert t is not None
    content = json.loads(t.content)
    assert len(content) >= 1
    p = content[0]
    # fake provider 下 question 为空字符串，但字段必须存在
    assert "question" in p and "answer" in p and "keywords" in p
    assert "id" in p and "content" in p
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_task_gen.py::test_gen_knowledge_content_has_question_fields -v`
Expected: FAIL（当前 content 是 `[{id, content, category}]`，无 question/answer/keywords 字段）

- [ ] **Step 3: 改 `_gen_knowledge`**

把 `_gen_knowledge` 里构造 `content` 的部分改为先调 `generate_knowledge_questions`：

当前（`task_gen.py:74-82`）：
```python
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

改为：
```python
    pts = new_pts + due_pts
    if not pts:
        return None
    from .knowledge_quiz import generate_knowledge_questions
    raw = [{"id": p.id, "content": p.content, "category": p.category} for p in pts]
    qs = generate_knowledge_questions(db, raw, subject)
    return Task(
        task_type="knowledge", subject=subject, title=f"{lesson.title} 基础知识",
        detail=f"重点巩固 · {len(pts)} 个知识点（新课 {len(new_pts)} + 复习 {len(due_pts)}）",
        content=json.dumps(qs, ensure_ascii=False),
        points=20,
    )
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_task_gen.py -v`
Expected: PASS（新增 + 既有全过）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/task_gen.py backend/tests/test_task_gen.py
git commit -m "feat: 基础知识任务预生成知识点问答"
```

---

## Task 3: `knowledge-review` 接口接收答案判分落掌握度

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Test: `backend/tests/test_tasks_router.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_tasks_router.py` 追加（先读该文件了解现有 client/fixture 风格）：

```python
def test_knowledge_review_grade_records_mastery(client, db):
    # 造一个 knowledge 任务，content 含 question/answer/keywords，且知识点有 id
    # POST /api/tasks/{id}/knowledge-review body {user_id, answers:[{id, user_answer}]}
    # 断言：返回 results 含 is_correct，KnowledgeMastery 落记录
    ...
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_tasks_router.py -v`
Expected: FAIL（接口签名还是 remembered）

- [ ] **Step 3: 改接口**

把 `tasks.py` 的 `KnowledgeReviewReq` 和 `knowledge_review` 改造：

```python
class KnowledgeReviewReq(BaseModel):
    user_id: int
    answers: list[dict] = []   # [{id: 知识点id, user_answer: 孩子答案}]


@router.post("/{task_id}/knowledge-review")
def knowledge_review(task_id: int, req: KnowledgeReviewReq, db: Session = Depends(get_db)):
    from ..services.mastery import record_attempt
    from ..services.knowledge_quiz import grade_knowledge_answer
    t = db.get(Task, task_id)
    if not t or t.task_type != "knowledge":
        return {"ok": False, "error": "任务不存在"}
    if t.submit_status == "approved":
        return {"ok": False, "error": "家长已确认，不能再修改"}
    try:
        points = json.loads(t.content or "[]")
    except ValueError:
        points = []
    by_id = {p.get("id"): p for p in points}
    results = []
    for a in req.answers:
        p = by_id.get(a.get("id"))
        if p is None:
            continue
        user_answer = (a.get("user_answer") or "").strip()
        is_correct, _ = grade_knowledge_answer(
            user_answer, p.get("keywords") or [], p.get("answer") or "", db=db)
        if p.get("id"):
            record_attempt(db, req.user_id, "knowledge", p["id"], is_correct)
        p["last_correct"] = is_correct
        results.append({"id": p.get("id"), "is_correct": is_correct, "answer": p.get("answer") or ""})
    t.content = json.dumps(points, ensure_ascii=False)
    t.submit_status = "submitted"
    db.commit()
    correct = sum(1 for r in results if r["is_correct"])
    return {"ok": True, "results": results, "correct": correct, "total": len(results)}
```

注意：`record_attempt` 每次内部会 `db.commit()`（`mastery.py:114`），所以最后 `t.content` 更新后要再 commit 一次（上面代码已含）。确认 `record_attempt` 的 commit 不会导致 `t` 对象失效——`t` 是已加载对象，`record_attempt` commit 后 `t` 仍可用，最后统一 commit 没问题。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_tasks_router.py tests/test_task_gen.py tests/test_knowledge_quiz.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/tasks.py backend/tests/test_tasks_router.py
git commit -m "feat: 基础知识复习接收简答并混合判分落掌握度"
```

---

## Task 4: 前端简答交互

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1: 改 `renderKnowledge` 和 `startKnowledge`**

`startKnowledge`（当前 line 733-741）解析 content 后，现在 content 结构变了（含 question/answer/keywords），且 `picks` 语义从「boolean 记住」改为「用户输入答案」。改：

```javascript
function startKnowledge(taskId){
  const t = dailyTasks.find(x => x.id === taskId);
  let points = [];
  try { points = JSON.parse(t?.content || '[]'); } catch(e){ points = []; }
  if(!Array.isArray(points) || !points.length){ toast('本次任务暂无知识点'); return; }
  const inputs = points.map(() => '');
  knowState = {taskId, title: t.title, points, inputs, results: points.map(()=>null), done: false};
  setPage('知识点复习');
}
```

`renderKnowledge` 改成逐题简答交互：

```javascript
function renderKnowledge(){
  const s = knowState;
  if(!s) return '<div class="placeholder-page"><h2>基础知识复习</h2><p>请从首页点击任务进入。</p></div>';
  const items = s.points.map((p,i)=>{
    const r = s.results[i];  // null=未答, {is_correct, answer}
    if(r){
      return `<div class="center-question">
        <div class="cq-q">${i+1}. ${p.question || p.content}</div>
        <div class="cq-ans ${r.is_correct?'right':'wrong'}">${icon('check',15)} ${r.is_correct?'答对了':'答错了'} · 标准答案：${escapeAttr(r.answer || '(无标准答案)')}</div>
        ${!r.is_correct ? `<div class="cq-form"><input class="cq-input" placeholder="再看一遍答案，重新作答" value="${escapeAttr(s.inputs[i])}" oninput="knowInput(${i}, this.value)"/><button class="cq-btn" onclick="knowReAnswer(${i})">重新作答</button></div>` : ''}
      </div>`;
    }
    return `<div class="center-question">
      <div class="cq-q">${i+1}. ${p.question || p.content}</div>
      <div class="cq-form"><input class="cq-input" placeholder="凭记忆作答…" value="${escapeAttr(s.inputs[i])}" oninput="knowInput(${i}, this.value)"/><button class="cq-btn" onclick="knowSubmit(${i})">提交</button></div>
    </div>`;
  }).join('');
  // ... 其余（done 态统计 + 提交按钮）参考现有结构
}
```

新增辅助函数：

```javascript
function knowInput(i, v){ if(knowState){ knowState.inputs[i] = v; } }
async function knowSubmit(i){
  const s = knowState;
  const p = s.points[i];
  const d = await api(`/api/tasks/${s.taskId}/knowledge-review`, {method:'POST', body:{user_id:uid, answers:[{id:p.id, user_answer:s.inputs[i]}]}});
  const r = (d.results && d.results[0]) || {is_correct:false, answer:''};
  s.results[i] = r;
  render();
}
async function knowReAnswer(i){
  const s = knowState;
  const p = s.points[i];
  const d = await api(`/api/tasks/${s.taskId}/knowledge-review`, {method:'POST', body:{user_id:uid, answers:[{id:p.id, user_answer:s.inputs[i]}]}});
  const r = (d.results && d.results[0]) || {is_correct:false, answer:''};
  s.results[i] = r;
  render();
}
```

注意：`knowState` 需要改成含 `inputs` 和 `results` 字段（而非旧的 `picks`）。同时 `submitKnowledge`（旧的「提交」按钮，把所有题一次性提交）改为「全部答完后」的提交，或者干脆逐题提交（`knowSubmit` 每题独立调接口），最后统一标记任务完成。为简单，采用**逐题独立提交判分**（每题调一次接口），全部答完后再走一次提交标记 `submit_status`（或由最后一道题的提交自然标记 submitted）。

- [ ] **Step 2: `node --check` 验证**

Run: `cd /d/workspace/github/KnoAct && node --check frontend/app.js`
Expected: 无语法错误

- [ ] **Step 3: 更新缓存版本号**

`frontend/index.html` 里 `app.js?v=28` 改为 `app.js?v=29`。

- [ ] **Step 4: 提交**

```bash
git add frontend/app.js frontend/index.html
git commit -m "feat: 基础知识复习改为逐题简答主动回忆"
```

---

## 自审

**Spec 覆盖：**
- 出题（知识点→简答题）→ Task 1（knowledge_quiz.py）+ Task 2（_gen_knowledge）
- 判分（混合）→ Task 1（grade_knowledge_answer）
- 交互（逐题作答+标准答案+答错重答）→ Task 4
- 落掌握度（遗忘曲线闭环）→ Task 3

**占位符扫描：** Task 3 的测试（Step 1）写的是「先读该文件了解风格」+ `...`，需要 implementer 补全具体断言。其余无 TBD。

**类型一致性：**
- `generate_knowledge_questions(db, points, subject)` → Task 1 定义、Task 2 调用一致
- `grade_knowledge_answer(user_answer, keywords, answer, db)` → Task 1 定义、Task 3 调用一致
- `KnowledgeReviewReq.answers` → Task 3 定义、Task 4 前端调用一致
- `knowState` 字段（inputs/results 替代 picks）→ Task 4 内部一致

**一个需要 implementer 注意的点**：Task 4 里 `submitKnowledge` 旧函数（一次性提交所有题）的语义变了。逐题提交后，「全部答完」如何标记任务完成需要 implementer 在实现时想清楚——最简单是每题独立调接口（后端每题落掌握度 + 标记 submitted），最后一道题答完自然 submitted。计划里已按「逐题独立提交」设计，implementer 需确保旧的 `submitKnowledge` 不再被引用（grep 确认）。
