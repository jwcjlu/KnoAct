# 打通与打磨（掌握度接入错题本/报告）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把阶段 3 的掌握度串进错题本移出判定与家长报告，测验答错收录错题本。复习队列已通过 `next_review_at` 避已掌握，无需改代码。

**Architecture:** 全部改动落在 services/routers/models 层。**不触碰** `core/`、`runtime/`、`tools/` 这三层（它们是并行引入的 agent-native 抽象，本阶段与其正交）。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + SQLite + pytest；前端单文件原生 JS。

**设计文档:** `docs/superpowers/specs/2026-10-27-integration-polish-design.md`

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/models.py` | `Mistake` 加两列 | 修改 |
| `backend/app/routers/mistakes.py` | `mark_correct`/`mark_wrong` 用掌握度 | 修改 |
| `backend/app/routers/quiz.py` | `quiz_submit` 收错题 | 修改 |
| `backend/app/routers/learning.py` | `WrongWord` 加 `word_id`、`dictation_complete` 带 word_id | 修改 |
| `backend/app/routers/mastery.py` | 新增 `/api/mastery/report` | 修改 |
| `backend/app/services/mastery.py` | 无改动（复用 `record_attempt`/`GATE`） | 不改 |
| `frontend/app.js` | `renderReportTab` 加掌握度区块 | 修改 |
| `backend/tests/test_mistakes.py` | 移出判定/去重测试 | 创建 |

---

## Task 1: Mistake 加列 + 错题本移出判定用掌握度

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/routers/mistakes.py`
- Test: `backend/tests/test_mistakes.py`（创建）

- [ ] **Step 1: 加列**

`backend/app/models.py`，在 `Mistake` 类里 `consecutive_correct` 之后追加：

```python
    word_bank_id: Mapped[int] = mapped_column(ForeignKey("word_banks.id"), nullable=True)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True)
```

- [ ] **Step 2: 写失败测试**

创建 `backend/tests/test_mistakes.py`：

```python
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User, WordBank, Lesson, PdfDocument, Mistake
from app.services.mastery import GATE

client = TestClient(app)


def _seed():
    db = SessionLocal()
    for m in (Mistake, WordBank, Lesson, PdfDocument, User):
        db.query(m).delete()
    db.commit()
    u = User(name="孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="y.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l = Lesson(document_id=doc.id, subject="语文", title="第1课",
               start_page=1, end_page=1, extract_status="done", audit_status="approved")
    db.add(l); db.flush()
    wb = WordBank(lesson_id=l.id, subject="语文", word="白鹭", extra="pinyin")
    db.add(wb); db.flush()
    db.commit()
    return u.id, wb.id


def test_mark_correct_with_word_id_removes_only_after_gate(setup_db):
    uid, wbid = _seed()
    db = SessionLocal()
    m = Mistake(user_id=uid, source_type="dictation", question="白鹭",
                your_answer="白露", correct_answer="白鹭", word_bank_id=wbid)
    db.add(m); db.commit(); mid = m.id
    db.close()

    # 第一次答对：掌握度 0.5（封顶），未达标，不移出
    r1 = client.post(f"/api/mistakes/{mid}/correct").json()
    assert r1["removed"] is False
    # 第二次答对：0.8，仍未达标
    r2 = client.post(f"/api/mistakes/{mid}/correct").json()
    assert r2["removed"] is False
    # 第三次答对：1.0 达标，移出
    r3 = client.post(f"/api/mistakes/{mid}/correct").json()
    assert r3["removed"] is True

    db = SessionLocal()
    assert db.get(Mistake, mid) is None
    db.close()


def test_mark_correct_without_id_uses_legacy_threshold(setup_db):
    uid, wbid = _seed()
    db = SessionLocal()
    m = Mistake(user_id=uid, source_type="reading", question="主旨是什么",
                your_answer="A", correct_answer="B")  # 无关联 id
    db.add(m); db.commit(); mid = m.id
    db.close()

    # 旧逻辑：连续答对 3 次移出
    client.post(f"/api/mistakes/{mid}/correct")
    client.post(f"/api/mistakes/{mid}/correct")
    r3 = client.post(f"/api/mistakes/{mid}/correct").json()
    assert r3["removed"] is True
```

- [ ] **Step 3: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_mistakes.py -q
```

Expected: 第二条失败（无关联 id 的旧逻辑当前是 `REMOVE_AFTER=3`，但第一条「有 word_bank_id 用掌握度」尚未实现，会走旧逻辑连答 3 次就移出，第一条的第二次答对 `removed` 应为 False 但当前会 True）。具体以实际输出为准。

- [ ] **Step 4: 改 mark_correct / mark_wrong**

`backend/app/routers/mistakes.py`，替换 `mark_correct`：

```python
@router.post("/{mistake_id}/correct")
def mark_correct(mistake_id: int, db: Session = Depends(get_db)):
    """答对一次：有词/知识点关联时用掌握度判定移出，否则走旧计数逻辑。"""
    m = db.get(Mistake, mistake_id)
    if not m:
        return {"removed": False, "error": "not found"}
    from ..services.mastery import record_attempt, GATE

    removed = False
    if m.word_bank_id:
        mastery = record_attempt(db, m.user_id, "word", m.word_bank_id, True)
        removed = mastery >= GATE
    elif m.knowledge_point_id:
        mastery = record_attempt(db, m.user_id, "knowledge", m.knowledge_point_id, True)
        removed = mastery >= GATE
    else:
        m.consecutive_correct += 1
        removed = m.consecutive_correct >= REMOVE_AFTER

    if removed:
        db.delete(m)
    db.commit()
    return {"removed": removed, "consecutive_correct": 0 if removed else m.consecutive_correct}
```

替换 `mark_wrong`：

```python
@router.post("/{mistake_id}/wrong")
def mark_wrong(mistake_id: int, db: Session = Depends(get_db)):
    """再答错：有词/知识点关联时驱动掌握度下降，否则走旧计数。"""
    m = db.get(Mistake, mistake_id)
    if not m:
        return {"error": "not found"}
    from ..services.mastery import record_attempt

    if m.word_bank_id:
        record_attempt(db, m.user_id, "word", m.word_bank_id, False)
    elif m.knowledge_point_id:
        record_attempt(db, m.user_id, "knowledge", m.knowledge_point_id, False)
    else:
        m.consecutive_correct = 0
    # 错题本自身的计数字段，无论走哪个分支都要更新
    m.mistake_count += 1
    m.consecutive_correct = 0
    db.commit()
    return {"mistake_count": m.mistake_count}
```

（错题本字段 `mistake_count`/`consecutive_correct` 和掌握度对象 `WordMastery`/`KnowledgeMastery` 是两套，都要更新。）

- [ ] **Step 5: 运行**

```bash
cd backend && python -m pytest tests/test_mistakes.py -q
```

Expected: 2 passed。

- [ ] **Step 6: 提交**

```bash
git add backend/app/models.py backend/app/routers/mistakes.py backend/tests/test_mistakes.py
git commit -m "feat: 错题本移出判定改用掌握度分数（保留旧逻辑兜底）"
```

---

## Task 2: 测验答错收录错题本（去重）

**Files:**
- Modify: `backend/app/routers/quiz.py`
- Test: `backend/tests/test_mistakes.py`（追加）

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_mistakes.py` 追加：

```python
def test_record_quiz_mistake_dedup(setup_db):
    from app.services.quiz import record_quiz_mistake
    uid, wbid = _seed()
    db = SessionLocal()

    record_quiz_mistake(db, uid, "作者把白鹭比作什么？", "一幅画", "一首诗", kp_id=None)
    record_quiz_mistake(db, uid, "作者把白鹭比作什么？", "一幅画", "一首诗", kp_id=None)

    rows = db.query(Mistake).filter_by(user_id=uid, question="作者把白鹭比作什么？").all()
    assert len(rows) == 1          # 去重
    assert rows[0].mistake_count == 2  # 累加
    db.close()


def test_record_quiz_mistake_distinct_kp_separate(setup_db):
    from app.services.quiz import record_quiz_mistake
    uid, wbid = _seed()
    db = SessionLocal()
    record_quiz_mistake(db, uid, "Q", "A", "B", kp_id=1)
    record_quiz_mistake(db, uid, "Q", "A", "B", kp_id=2)
    rows = db.query(Mistake).filter_by(user_id=uid, question="Q").all()
    assert len(rows) == 2  # 不同 kp_id 不合并
    db.close()
```

- [ ] **Step 2: 实现去重辅助函数 + 接线**

在 `backend/app/services/quiz.py`（或新建 `services/mistakes.py`）加：

```python
def record_quiz_mistake(db, user_id, question, your_answer, correct_answer, kp_id=None):
    """测验答错收错题本，按 (user_id, kp_id, question) 去重累加。"""
    from ..models import Mistake
    q = db.query(Mistake).filter_by(user_id=user_id, question=question)
    if kp_id is not None:
        q = q.filter_by(knowledge_point_id=kp_id)
    existing = q.first()
    if existing:
        existing.mistake_count += 1
        existing.consecutive_correct = 0
    else:
        db.add(Mistake(
            user_id=user_id, source_type="reading",
            question=question, your_answer=your_answer,
            correct_answer=correct_answer, knowledge_point_id=kp_id,
        ))
    db.commit()
```

在 `routers/quiz.py` 的 `quiz_submit`，判分后、`db.commit()` 前，追加：

```python
    if quiz.user_id:
        from ..services.quiz import record_quiz_mistake
        for q, r in zip(questions, results):
            if not r["is_correct"]:
                # 找到孩子选的选项文本
                sel = next((a.get("selected_index") for a in req.answers
                            if a.get("question_id") == q["id"]), None)
                your = q["choices"][sel] if isinstance(sel, int) and 0 <= sel < len(q["choices"]) else ""
                correct = q["choices"][q["correct_index"]]
                record_quiz_mistake(db, quiz.user_id, q["prompt"], your, correct, q.get("knowledge_point_id"))
```

（`q["correct_index"]` 在 `questions`（json.loads 出的 stored）里有，但在 `results`/前端看不到；`quiz_submit` 里 `questions = json.loads(quiz.questions)` 是服务端全量数据，含 `correct_index`，可用。）

- [ ] **Step 3: 运行**

```bash
cd backend && python -m pytest tests/test_mistakes.py -q
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/quiz.py backend/app/routers/quiz.py backend/tests/test_mistakes.py
git commit -m "feat: 测验答错收录错题本（按 user/kp/题去重）"
```

---

## Task 3: 家长掌握度报告

**Files:**
- Modify: `backend/app/routers/mastery.py`
- Modify: `frontend/app.js`
- Test: `backend/tests/test_mastery_api.py`（追加）

- [ ] **Step 1: 追加接口测试**

在 `backend/tests/test_mastery_api.py` 追加：

```python
def test_mastery_report_counts(setup_db):
    uid, kpid = _seed()  # 复用已有 _seed（返回 uid, kpid）
    db = SessionLocal()
    # 一个知识点答 3 次达标，另一个答 1 次未达标
    record_attempt(db, uid, "knowledge", kpid, True)
    db.close()
    r = client.get(f"/api/mastery/report?user_id={uid}&subject=语文")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert data["mastered"] + data["weak"] >= 1
    assert len(data["rows"]) >= 1
```

- [ ] **Step 2: 实现 /api/mastery/report**

在 `backend/app/routers/mastery.py` 追加：

```python
@router.get("/report")
def report(user_id: int, subject: str = "", db: Session = Depends(get_db)):
    """掌握度报告：已掌握 / 薄弱 / 总数。"""
    kp_q = db.query(KnowledgePoint)
    if subject:
        kp_q = kp_q.filter(KnowledgePoint.subject == subject)
    all_kps = kp_q.all()
    total = len(all_kps)

    rows = []
    mastered = 0
    weak = 0
    for kp in all_kps:
        km = (db.query(KnowledgeMastery)
              .filter_by(user_id=user_id, knowledge_point_id=kp.id).first())
        if km is None:
            continue  # 未答过，不计入 weak
        attempts = json.loads(km.attempts or "[]")
        rows.append({
            "knowledge_point_id": kp.id,
            "title": kp.content,
            "category": kp.category,
            "mastery": km.mastery,
            "mastered": km.mastered,
            "attempts_count": len(attempts),
        })
        if km.mastered:
            mastered += 1
        else:
            weak += 1
    rows.sort(key=lambda r: r["mastery"])
    return {"mastered": mastered, "weak": weak, "total": total, "rows": rows}
```

（文件顶部需 `import json`，若没有则加。）

- [ ] **Step 3: 前端 renderReportTab 加掌握度区块**

`frontend/app.js` 的 `renderReportTab`，在现有薄弱报告面板后追加一个 panel。加载数据：

```javascript
let masteryReport = null;
async function loadMasteryReport(){
  masteryReport = await api(`/api/mastery/report?user_id=${uid}`);
  return masteryReport;
}
```

在 `renderReportTab` 返回的 `<div class="parent-grid">` 里追加：

```javascript
<div class="parent-panel" style="grid-column:1/-1">
  <div class="head"><div class="ic purple">${icon('brain',20)}</div>
    <div><h3>掌握度报告</h3><div class="sub">知识点掌握情况（阶段 3 打通）</div></div></div>
  <div class="bd">
    <div style="display:flex;gap:16px;align-items:center;margin-bottom:16px">
      <span style="font-size:13px;color:var(--gray2)">已掌握 <b style="color:var(--green2)">${masteryReport?.mastered||0}</b> ·
      薄弱 <b style="color:var(--orange2)">${masteryReport?.weak||0}</b> · 共 ${masteryReport?.total||0}</span>
    </div>
    ${(masteryReport?.rows||[]).map(r=>`
      <div class="weak-row">
        <span class="w-name">${escapeAttr(r.category)} · ${escapeAttr(r.title)}</span>
        <div class="w-bar"><div class="w-fill" style="width:${Math.round(r.mastery*100)}%;background:${r.mastered?'var(--green2)':'var(--orange2)'}"></div></div>
        <span class="w-val">${r.mastered?'✓ ':''}${Math.round(r.mastery*100)}%</span>
      </div>`).join('') || '<p style="font-size:13px;color:var(--gray2)">暂无掌握度记录</p>'}
  </div>
</div>
```

并在「报告」tab 的加载逻辑（`parentTab==='报告'` 分支）里，除了现有 `loadReport()` 外也 `loadMasteryReport()`（看现有报告 tab 如何加载 `reportRows`，照它的方式并行加载 `masteryReport`）。

- [ ] **Step 4: 运行 + node 检查**

```bash
cd backend && python -m pytest tests/test_mastery_api.py -q
cd /d/workspace/github/KnoAct && node --check frontend/app.js && echo SYNTAX_OK
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/mastery.py frontend/app.js backend/tests/test_mastery_api.py
git commit -m "feat: 家长掌握度报告（接口 + 报告页区块）"
```

---

## Task 4: dictation 错词带 word_id + 端到端

**Files:**
- Modify: `backend/app/routers/learning.py`
- 前端 `finishDictation`（可选，传 word_id）

- [ ] **Step 1: WrongWord 加 word_id + dictation_complete 带 id**

`backend/app/routers/learning.py`，`WrongWord` 加字段：

```python
class WrongWord(BaseModel):
    word: str
    your_answer: str = ""
    word_id: int = 0
```

`dictation_complete` 收错词时，写入 `Mistake.word_bank_id`：

```python
    for ww in req.wrong_words:
        db.add(Mistake(
            user_id=req.user_id, source_type="dictation",
            question=f"听写词语：{ww.word}",
            your_answer=ww.your_answer, correct_answer=ww.word,
            word_bank_id=ww.word_id if ww.word_id else None,
        ))
```

（当前代码是 `db.add(Mistake(...))`，找到它并加 `word_bank_id` 参数。）

- [ ] **Step 2: 前端 finishDictation 传 word_id（可选但推荐）**

`frontend/app.js` 的 `finishDictation`（约 line 585），`wrongWords` 目前 `s.wrong.map(x=>({word:x.word, your_answer:x.yours}))`。若 `s.wrong` 项里有 `id`，加上 `word_id:x.id`。查 `dictState.wrong` 的项结构再定；若没有 id 就不改（后端 `word_id` 默认为 0，仍能收错题，只是不关联掌握度）。

- [ ] **Step 3: 全套测试 + 真实库迁移**

```bash
cd backend && python -m pytest -q 2>&1 | tail -6
```

Expected: 仅剩两条既有失败。

真实库迁移 `Mistake` 加两列：

```bash
cd backend && python -c "
import sqlite3
c = sqlite3.connect('zhixueban.db')
for col, ddl in [
    ('word_bank_id', 'ALTER TABLE mistakes ADD COLUMN word_bank_id INTEGER'),
    ('knowledge_point_id', 'ALTER TABLE mistakes ADD COLUMN knowledge_point_id INTEGER'),
]:
    try: c.execute(ddl); print('added', col)
    except sqlite3.OperationalError as e: print('skip', col, e)
c.commit()
cols = [r[1] for r in c.execute('pragma table_info(mistakes)')]
print('mistakes cols:', cols)
c.close()
"
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/routers/learning.py frontend/app.js
git commit -m "feat: 听写错词带 word_id 关联词掌握度"
```

---

## 完成标准

- [ ] `Mistake` 加 `word_bank_id`/`knowledge_point_id`，`WrongWord` 加 `word_id`
- [ ] `mark_correct`/`mark_wrong` 用掌握度分数判定移出（无 id 时走旧逻辑兜底）
- [ ] `quiz_submit` 答错收错题本，按 `(user, kp, question)` 去重累加
- [ ] `/api/mastery/report` + 报告页掌握度区块
- [ ] 复习队列不改（已通过 `next_review_at` 避已掌握）
- [ ] 全套测试仅剩两条既有失败
