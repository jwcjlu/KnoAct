# 精通之路 · 双层掌握度 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 KnoAct 里实现双层掌握度——词级（扩展 `WordMastery`）与知识点级（新建 `KnowledgeMastery`），算法逐字复制 DeepTutor 的 `compute_mastery` + `grade_answer`。

**Architecture:** `services/mastery.py` 承载复制的评分算法与 `record_attempt`；`routers/mastery.py` 暴露 overview/record；测验出题注入知识点列表返回 `knowledge_point_id`；`quiz_submit` 与 `dictation_grade` 作为答题证据接入点。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + SQLite + pytest；前端单文件原生 JS。依赖阶段 2 的 `Quiz`/`generate_quiz`/`quiz_submit` 与阶段 1 的 `resolve`/`get_provider`。

**设计文档:** `docs/superpowers/specs/2026-10-27-mastery-path-design.md`

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/models.py` | `KnowledgeMastery` 新表 + `WordMastery` 加三列 | 修改 |
| `backend/app/services/mastery.py` | compute_mastery / grade_answer / record_attempt（复制 DeepTutor） | 创建 |
| `backend/app/routers/mastery.py` | overview / record 接口 | 创建 |
| `backend/app/routers/quiz.py` | generate_quiz 注入知识点、quiz_submit 驱动掌握度 | 修改 |
| `backend/app/routers/learning.py` | dictation_grade 驱动词掌握度 | 修改 |
| `backend/app/main.py` | 挂载 mastery router | 修改 |
| `backend/app/seed.py` | 注册新表 | 修改 |
| `backend/tests/test_mastery.py` | 评分/记录/接口测试 | 创建 |
| `backend/tests/test_quiz.py` | 扩展：knowledge_point_id | 修改 |

**测试运行**：`cd backend && python -m pytest ...`。Bash `python`（Python310），勿用终端面板 conda python。

---

## Task 1: 数据模型 + mastery 服务（评分算法）

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/services/mastery.py`
- Test: `backend/tests/test_mastery.py`（先写纯函数测试）

- [ ] **Step 1: 追加/扩展模型**

`backend/app/models.py`：

在末尾（`Quiz` 之后）追加：

```python
class KnowledgeMastery(Base):
    """知识点级掌握度。"""
    __tablename__ = "knowledge_mastery"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"))
    attempts: Mapped[str] = mapped_column(TextCls, default="[]")  # JSON：[true, false, ...]
    mastery: Mapped[float] = mapped_column(Float, default=0.0)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    next_review_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

在 `WordMastery` 类里，`next_review_at` 之后追加三列：

```python
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)  # 迁移回填
    attempts: Mapped[str] = mapped_column(TextCls, default="[]")
    mastery: Mapped[float] = mapped_column(Float, default=0.0)
```

- [ ] **Step 2: 写失败测试（compute_mastery + grade_answer）**

创建 `backend/tests/test_mastery.py`：

```python
from app.services.mastery import compute_mastery, grade_answer, is_mastered, GATE


def test_compute_mastery_empty_is_zero():
    assert compute_mastery([]) == 0.0


def test_compute_mastery_single_correct_is_capped_at_half():
    assert compute_mastery([True]) == 0.5


def test_compute_mastery_two_correct_capped_at_point_eight():
    assert compute_mastery([True, True]) == 0.8


def test_compute_mastery_recovers_after_mistakes():
    # 早期错、最近对 → 掌握度应回升
    assert compute_mastery([False, True, True, True]) > 0.8


def test_compute_mastery_three_plus_correct_reaches_gate():
    m = compute_mastery([True, True, True])
    assert m >= GATE


def test_grade_answer_choice_normalized():
    assert grade_answer("A", "A", "choice") is True
    assert grade_answer("a b", "ab", "choice") is True
    assert grade_answer("A", "B", "choice") is False


def test_grade_answer_short_similarity():
    assert grade_answer("白鹭", "白鹭", "short") is True
    # short：相等即对；明显不同即错（临界相似度不测，ratio 随内容而定）
    assert grade_answer("完全不同的答案", "白鹭", "short") is False
```

- [ ] **Step 3: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_mastery.py -q
```

Expected: FAIL（`ModuleNotFoundError: app.services.mastery`）。

- [ ] **Step 4: 实现 services/mastery.py**

创建 `backend/app/services/mastery.py`（含 DeepTutor 出处注释）：

```python
"""精通之路：掌握度评分 + 确定性判分。

compute_mastery 与 grade_answer 逐字复制自 DeepTutor（Apache-2.0）：
  - deeptutor/learning/mastery.py   (compute_mastery)
  - deeptutor/learning/grading.py   (grade_answer)
"""
import json
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from ..models import KnowledgeMastery, WordMastery
from .scheduler import next_review_after

_RECENCY_WEIGHTS = (0.5, 0.7, 0.85, 0.95, 1.0)
_CONFIDENCE_CAP = {1: 0.5, 2: 0.8}

GATE = 0.9


def compute_mastery(correctness: list[bool | float]) -> float:
    """0..1 掌握度：recency 加权 + 前 2 次封顶。"""
    if not correctness:
        return 0.0
    recent = correctness[-len(_RECENCY_WEIGHTS):]
    weights = _RECENCY_WEIGHTS[-len(recent):]
    score = sum(w * max(0.0, min(1.0, float(c)))
                for c, w in zip(recent, weights, strict=True)) / sum(weights)
    return min(score, _CONFIDENCE_CAP.get(len(recent), 1.0))


def grade_answer(user_answer: str, expected_answer: str, question_type: str = "choice") -> bool:
    user = user_answer.strip().lower()
    expected = expected_answer.strip().lower()
    if not expected:
        return False
    if question_type == "choice":
        return user.replace(" ", "") == expected.replace(" ", "")
    if question_type == "short":
        if user == expected:
            return True
        if len(expected) <= 30:
            return SequenceMatcher(None, user, expected).ratio() >= 0.85
        return False
    if question_type == "open":
        keywords = [k.strip() for k in re.split(r"[,;，；。\n]+", expected) if k.strip()]
        if not keywords:
            return False
        matched = sum(1 for kw in keywords if kw in user)
        return matched / len(keywords) >= 0.6
    return False


def is_mastered(mastery: float) -> bool:
    return mastery >= GATE


def _append(attempts: list, is_correct: bool) -> tuple[float, bool, datetime]:
    attempts.append(bool(is_correct))
    mastery = compute_mastery(attempts)
    mastered = is_mastered(mastery)
    now = datetime.utcnow()
    if mastered:
        nxt = next_review_after(6, now)   # 达标：末档 60 天
    else:
        streak = 0
        for c in reversed(attempts):
            if c:
                streak += 1
            else:
                break
        nxt = next_review_after(streak, now)
    return mastery, mastered, nxt


def record_attempt(db: Session, user_id: int, target_type: str,
                   target_id: int, is_correct: bool) -> float:
    """记录一次答题，更新对应掌握度。返回新 mastery。

    target_type: 'knowledge' | 'word'
    """
    if target_type == "knowledge":
        row = (db.query(KnowledgeMastery)
               .filter_by(user_id=user_id, knowledge_point_id=target_id).first())
        if not row:
            row = KnowledgeMastery(user_id=user_id, knowledge_point_id=target_id)
            db.add(row)
    else:
        row = (db.query(WordMastery)
               .filter_by(user_id=user_id, word_bank_id=target_id).first())
        if not row:
            row = WordMastery(user_id=user_id, word_bank_id=target_id,
                              correct_count=0, mistake_count=0, is_weak=False)
            db.add(row)

    attempts = json.loads(row.attempts or "[]")
    mastery, mastered, nxt = _append(attempts, is_correct)
    row.attempts = json.dumps(attempts)
    row.mastery = mastery
    if target_type == "knowledge":
        row.mastered = mastered
    row.next_review_at = nxt
    # 词层同时维护旧字段，供旧复习调度（select_words 依赖 mistake_count）
    if target_type == "word":
        if is_correct:
            row.correct_count += 1
            row.is_weak = False
        else:
            row.mistake_count += 1
            row.is_weak = True
            row.correct_count = 0
    db.commit()
    return mastery
```

- [ ] **Step 5: 运行测试**

```bash
cd backend && python -m pytest tests/test_mastery.py -q
```

Expected: 通过（注意 Step 2 里「白露 vs 白鹭」的 ratio < 0.85，需按真实 ratio 修正该测试——改为「相等即对 + 明显不同即错」两个断言，不测临界相似度）。

- [ ] **Step 6: 提交**

```bash
git add backend/app/models.py backend/app/services/mastery.py backend/tests/test_mastery.py
git commit -m "feat: 掌握度服务（复制 DeepTutor compute_mastery/grade_answer）"
```

---

## Task 2: record_attempt 完整测试（含落库）

**Files:**
- Test: `backend/tests/test_mastery.py`（追加）

- [ ] **Step 1: 追加落库测试**

在 `backend/tests/test_mastery.py` 末尾追加：

```python
from app.database import SessionLocal
from app.models import User, KnowledgePoint, Lesson, PdfDocument, WordBank, KnowledgeMastery, WordMastery


def _seed_kp():
    db = SessionLocal()
    for m in (KnowledgeMastery, WordMastery, WordBank, KnowledgePoint, Lesson, PdfDocument, User):
        db.query(m).delete()
    db.commit()
    u = User(name="孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="y.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l = Lesson(document_id=doc.id, subject="语文", title="第1课",
               start_page=1, end_page=1, extract_status="done", audit_status="approved")
    db.add(l); db.flush()
    kp = KnowledgePoint(subject="语文", category="字词", content="形近字辨析", lesson_id=l.id)
    db.add(kp); db.flush()
    wb = WordBank(lesson_id=l.id, subject="语文", word="白鹭", extra="pinyin")
    db.add(wb); db.flush()
    db.commit()
    return u.id, kp.id, wb.id


def test_record_attempt_knowledge_persists(setup_db):
    from app.services.mastery import record_attempt
    uid, kpid, wbid = _seed_kp()
    db = SessionLocal()
    m = record_attempt(db, uid, "knowledge", kpid, True)
    assert m == 0.5  # 首次答对封顶
    row = db.query(KnowledgeMastery).filter_by(user_id=uid, knowledge_point_id=kpid).first()
    assert row.mastery == 0.5
    assert row.mastered is False
    assert json.loads(row.attempts) == [True]
    db.close()


def test_record_attempt_word_reaches_gate_after_three(setup_db):
    from app.services.mastery import record_attempt
    uid, kpid, wbid = _seed_kp()
    db = SessionLocal()
    for _ in range(3):
        record_attempt(db, uid, "word", wbid, True)
    row = db.query(WordMastery).filter_by(user_id=uid, word_bank_id=wbid).first()
    assert row.mastery >= GATE
    assert len(json.loads(row.attempts)) == 3
    db.close()
```

（`import json` 需在测试文件顶部已存在；若没有则加。）

- [ ] **Step 2: 运行**

```bash
cd backend && python -m pytest tests/test_mastery.py -q
```

Expected: 全部通过。

- [ ] **Step 3: 提交**

```bash
git add backend/tests/test_mastery.py
git commit -m "test: 掌握度落库（knowledge/word 两层）"
```

---

## Task 3: mastery 接口 + 接线

**Files:**
- Create: `backend/app/routers/mastery.py`
- Modify: `backend/app/main.py`（挂载）、`backend/app/seed.py`（注册表）
- Modify: `backend/app/routers/quiz.py`（generate 注入知识点、submit 驱动）
- Modify: `backend/app/routers/learning.py`（dictation_grade 驱动）
- Test: `backend/tests/test_mastery.py`（追加接口测试）、`backend/tests/test_quiz.py`（扩展）

- [ ] **Step 1: 写失败测试（接口）**

追加到 `backend/tests/test_mastery.py`：

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_mastery_overview_by_subject(setup_db):
    uid, kpid, wbid = _seed_kp()
    from app.services.mastery import record_attempt
    db = SessionLocal()
    record_attempt(db, uid, "knowledge", kpid, True)
    db.close()
    r = client.get(f"/api/mastery/overview?user_id={uid}&subject=语文")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["knowledge_point_id"] == kpid
    assert data[0]["mastery"] == 0.5


def test_mastery_record_endpoint(setup_db):
    uid, kpid, wbid = _seed_kp()
    r = client.post("/api/mastery/record", json={
        "user_id": uid, "target_type": "knowledge", "target_id": kpid, "is_correct": True,
    })
    assert r.status_code == 200
    assert r.json()["mastery"] == 0.5
```

运行确认失败（404 路由不存在）：
```bash
cd backend && python -m pytest tests/test_mastery.py -q
```

- [ ] **Step 2: 实现 routers/mastery.py**

```python
"""精通之路：掌握度总览与记录。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import KnowledgeMastery, KnowledgePoint
from ..services.mastery import record_attempt as _record

router = APIRouter(prefix="/api/mastery", tags=["mastery"])


class RecordReq(BaseModel):
    user_id: int
    target_type: str   # 'knowledge' | 'word'
    target_id: int
    is_correct: bool


@router.get("/overview")
def overview(user_id: int, subject: str = "", db: Session = Depends(get_db)):
    q = (db.query(KnowledgeMastery, KnowledgePoint)
         .join(KnowledgePoint, KnowledgeMastery.knowledge_point_id == KnowledgePoint.id)
         .filter(KnowledgeMastery.user_id == user_id))
    if subject:
        q = q.filter(KnowledgePoint.subject == subject)
    rows = q.all()
    return [{
        "knowledge_point_id": kp.id,
        "title": kp.content,
        "category": kp.category,
        "mastery": km.mastery,
        "mastered": km.mastered,
        "due": km.next_review_at is not None and km.next_review_at <= datetime.utcnow(),
    } for km, kp in rows]


@router.post("/record")
def record(req: RecordReq, db: Session = Depends(get_db)):
    mastery = _record(db, req.user_id, req.target_type, req.target_id, req.is_correct)
    return {"mastery": mastery}
```

（`routers/mastery.py` 顶部需 `from datetime import datetime`，用于 `datetime.utcnow()`。）

- [ ] **Step 3: 挂载路由 + 注册表**

`main.py`：import 加 `mastery`，`app.include_router(mastery.router)` 加在 quiz 之后。
`seed.py`：`from .models import ...` 那行追加 `KnowledgeMastery`（已有一条 import 追加行，在末尾追加）。

- [ ] **Step 4: 接线测验（quiz.py）**

`generate_quiz`：在 `services/quiz.py` 的 `generate_quiz` 里，把当前课的知识点列表注入提示词。需先改 `services/quiz.py` 的 `generate_quiz` 签名，接收 `knowledge_points: list[dict]`（`[{id, category, content}]`），提示词加：

```
下面还有本课的知识点列表（id + 类别 + 内容）：
{json}
每道题额外返回 "knowledge_point_id"，从列表里选最相关的一个；若都不匹配则填 null。
```

`_validate` 里解析 `knowledge_point_id`（可空，int 或 None），存进返回的每道题 dict。

`routers/quiz.py` 的 `quiz_generate`：查 `KnowledgePoint.filter_by(lesson_id=...)`，传给 `generate_quiz`。

`quiz_submit`：判分后，对每题若有 `knowledge_point_id` 且非空，调 `record_attempt(db, quiz.user_id, 'knowledge', kpid, is_correct)`。注意：`quiz.user_id` 可能是 0（阶段 2 默认），此时不驱动掌握度（或需前端传 user_id）。**决策：quiz_generate 的 body 加 `user_id`，落库到 Quiz.user_id；quiz_submit 用 quiz.user_id，为 0 则跳过掌握度。**

- [ ] **Step 5: 接线听写（learning.py）**

`dictation_grade`：在更新 `WordMastery` 的现有逻辑里，追加 `record_attempt` 的调用。当前 `dictation_grade` 已按 `word_id`/`word` 定位 `w` 并维护 `m`（WordMastery）。改为：定位到 `w` 后，调 `record_attempt(db, req.user_id, 'word', w.id, correct)`，替代手写的 `correct_count`/`mistake_count` 逻辑（但保留 `is_weak`/`correct_count` 供旧复习调度用——`record_attempt` 内部也维护这些字段的话则完全替代）。

**关键取舍**：`record_attempt` 目前不更新 `correct_count`/`mistake_count`/`is_weak`。为不破坏旧复习调度（`select_words` 依赖 `mistake_count`/`next_review_at`），让 `record_attempt` 在 `target_type='word'` 时**同时**维护这三个旧字段。实现时在 `record_attempt` 的 word 分支里补：

```python
if is_correct:
    row.correct_count += 1
    row.is_weak = False
else:
    row.mistake_count += 1
    row.is_weak = True
    row.correct_count = 0
```

这样 `dictation_grade` 可以**完全**改成调 `record_attempt`，删掉手写逻辑。

- [ ] **Step 6: 运行全套**

```bash
cd backend && python -m pytest tests/test_mastery.py tests/test_quiz.py tests/test_learning.py -q
```

Expected: 全部通过（注意 `test_learning.py` 里可能断言了 `WordMastery` 的旧字段，若 `record_attempt` 维护了旧字段则不应破坏）。

- [ ] **Step 7: 提交**

```bash
git add backend/app/routers/mastery.py backend/app/main.py backend/app/seed.py backend/app/routers/quiz.py backend/app/services/quiz.py backend/app/routers/learning.py backend/app/services/mastery.py backend/tests/test_mastery.py backend/tests/test_quiz.py
git commit -m "feat: 掌握度接口 + 测验/听写接入掌握度记录"
```

---

## Task 4: 端到端验证

- [ ] **Step 1: 全套测试**

```bash
cd backend && python -m pytest -q 2>&1 | tail -8
```

Expected: 仅剩两条既有失败（`test_seed.py` 知识点计数、`test_pdf_router.py` KeyError）。

- [ ] **Step 2: 真实 AI 走查**

配好真实 provider 后：
1. 出题（`/api/quiz/generate`）→ 题目带 `knowledge_point_id`（打开 network 看响应）
2. 判分（`/api/quiz/submit`）→ 知识点掌握度更新（查 `/api/mastery/overview`）
3. 听写逐词判分 → 词掌握度更新
4. 三次答对 → `mastered=True`，`next_review_at` 拉长

- [ ] **Step 3: 迁移真实库**

`WordMastery` 加三列：用一次性 `ALTER TABLE` 或 `create_all` + 回填。确认真实库的 `word_mastery` 表有 `user_id`/`attempts`/`mastery` 三列，老行 `user_id` 回填为 4。

- [ ] **Step 4: 确认无残留**

```bash
git status --short
```

---

## 完成标准

- [ ] `compute_mastery` / `grade_answer` 逐字复制 DeepTutor，有出处注释
- [ ] `KnowledgeMastery` 新表 + `WordMastery` 补 `user_id`/`attempts`/`mastery`
- [ ] `record_attempt` 正确 append + 重算 + mastered 翻转 + next_review_at 更新，同时维护旧字段（word 层）
- [ ] `/api/mastery/overview` + `/api/mastery/record` 接口
- [ ] 测验题带 `knowledge_point_id`，判分后驱动知识点掌握度
- [ ] 听写逐词判分驱动词掌握度
- [ ] 达标（≥0.9）后 `mastered=True`、复习间隔拉长到 60 天
- [ ] 全套测试仅剩两条既有失败
