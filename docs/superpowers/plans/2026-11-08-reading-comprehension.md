# 阅读理解组题（语文/英语）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用「材料表 + 子题外键」落地阅读理解组题：家长可建一篇短文+若干子题，三来源都能产出同一结构，孩子端先读材料再逐题作答；子题复用现有 taxonomy 与判分，不新增 qtype。

**Architecture:** 新增 `ReadingPassage` 表，`Question.passage_id` 可空外键。独立题 `passage_id IS NULL` 行为不变。`POST /api/passages` 一次写入材料+子题；OCR/第三方经 `QuestionDraft.passage_title/passage_content` 在 `_persist_drafts` 里按材料去重建 `ReadingPassage`。材料正文用白名单轻量标记（`#`/`**`/`*`/`<u>`/`/音标/`/`____`），家长端与学生端各写同一套渲染器——**不引入完整 Markdown 库**（避免把链接/列表也解析掉，违反「白名单外一律当纯文本」）。判分零改动。

**Tech Stack:** Python 3 + FastAPI + SQLAlchemy；pytest；`parent-web` 原生 JS；`student-app` Flutter（Riverpod + go_router）。不新增 Flutter 依赖。

**Spec:** `docs/superpowers/specs/2026-11-08-reading-comprehension-design.md`

**关键约束（来自 AGENTS.md，勿违反）：**
- 后端启动/测试必须从 `backend/` 目录跑。测试已在 `backend/tests/conftest.py` 强制 `sqlite:///./test.db`。
- 所有测试命令在 `backend/` 下：`python -m pytest tests/<file>::<test> -v`。
- 跑后端用 Bash 的 `python`，不要用 PowerShell 的 conda python。
- **不改** `services/grade_question.py` 的 `grade_question()` / `grade_subjective_with_ai()`。
- **不改** `CATEGORY_OF_QTYPE` / `QTYPE_LABELS`（阅读理解不是 qtype）。
- 不收编现有 `Quiz`（边读边问）与 `question_gen.py`。

---

## File Structure（新增/改动清单）

**后端（新增）：**
- `backend/app/core/passage_markup.py` — `count_blanks()` / `blanks_aligned()` / `FILL_BLANK_QTYPES`
- `backend/app/routers/passages.py` — 建材料（可带子题）、列材料、拉材料+子题
- `backend/app/migrate_reading_passage.py` — 建表（create_all 已覆盖新表）+ 给存量 `questions` 补 `passage_id` 列
- `backend/tests/test_passage_markup.py`、`backend/tests/test_passages.py`

**后端（改动）：**
- `backend/app/models.py` — `ReadingPassage`；`Question.passage_id`
- `backend/app/main.py` — include `passages.router`；启动时跑迁移补列
- `backend/app/routers/questions.py` — `AddReq.passage_id`；审核按 `passage_id` 分组；`approve-by-passage`
- `backend/app/routers/bank.py` — 拉题嵌入 `passage`；`_persist_drafts` 按材料去重建 `ReadingPassage`
- `backend/app/core/source_adapter.py` — `QuestionDraft` 加 `passage_title` / `passage_content`
- `backend/app/services/ocr_import.py` — LLM 结构化支持 `passages[]`
- `backend/app/core/tiku_cn_adapter.py` — `item_to_draft` 读取 `passage`/`article`/`material`（学库宝复用此函数，一并覆盖）

**前端（改动）：**
- `parent-web/app.js` — 白名单渲染 + 阅读理解录入 + 审核台展示材料
- `parent-web/index.html` — 材料预览/挖空/音标样式
- `student-app/lib/features/bank_exercise/data/bank_models.dart` — `passageId` + `ReadingPassageInfo`
- `student-app/lib/features/bank_exercise/passage_markup.dart` — 白名单 tokenizer + widget
- `student-app/lib/features/bank_exercise/ui/bank_exercise_page.dart` — 按材料分组展示
- `student-app/test/bank_exercise_test.dart`、`student-app/test/features/bank_exercise/passage_markup_test.dart`

---

## Phase 0：模型 + 挖空对齐

### Task 1: `ReadingPassage` 表 + `Question.passage_id`

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_models.py` 追加（文件顶部已有 `from app.models import Question, QuestionBank`，改为同时 import `ReadingPassage`；`make_user` 从 `conftest` 引入）：

```python
from conftest import make_lesson, make_user
from app.models import Question, QuestionBank, ReadingPassage


def test_reading_passage_table():
    cols = {c.name for c in inspect(ReadingPassage).columns}
    for name in ("user_id", "bank_id", "subject", "title", "content", "grade", "status", "created_at"):
        assert name in cols, f"ReadingPassage 缺列 {name}"
    assert ReadingPassage.__table__.c.bank_id.nullable is True
    assert ReadingPassage.__table__.c.grade.nullable is True


def test_question_passage_id_nullable():
    assert "passage_id" in {c.name for c in inspect(Question).columns}
    assert Question.__table__.c.passage_id.nullable is True


def test_reading_passage_roundtrip(db):
    parent = make_user(db, name="rp_parent", role="parent")
    p = ReadingPassage(
        user_id=parent.id, subject="语文", title="春天", content="春天来了。",
        status="pending",
    )
    db.add(p)
    db.flush()
    q = Question(
        passage_id=p.id, qtype="short_answer", qtype_category="subjective",
        question="写了什么季节？", answer="春天", status="pending",
    )
    db.add(q)
    db.commit()
    got = db.get(ReadingPassage, p.id)
    assert got.content == "春天来了。"
    assert db.get(Question, q.id).passage_id == p.id
```

`test_create_all_tables` 的 `expected` 集合追加 `"reading_passages"`、`"questions"`（`questions` 已在 metadata 里，不必改 expected 里那份旧子集；只加 `reading_passages`）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_models.py::test_reading_passage_table tests/test_models.py::test_question_passage_id_nullable tests/test_models.py::test_reading_passage_roundtrip -v`

Expected: FAIL，`ImportError` / `ReadingPassage` 未定义 / `Question` 无 `passage_id`

- [ ] **Step 3: 实现模型**

在 `backend/app/models.py` 的 `Question` 上、`bank_id` 那一行后面加：

```python
    passage_id: Mapped[int] = mapped_column(ForeignKey("reading_passages.id"), nullable=True)  # 阅读材料子题；独立题为 NULL
```

在 `QuestionBank` 类**后面**追加（`reading_passages` 必须先于 `questions.passage_id` 的 FK 被 metadata 注册——SQLAlchemy 用字符串 `"reading_passages.id"`，表类定义顺序只要在同一 `Base` 上即可。为阅读清晰，放在 `QuestionBank` 之后）：

```python
class ReadingPassage(Base):
    """阅读理解材料。子题挂 Question.passage_id，不新增 qtype。"""
    __tablename__ = "reading_passages"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(16), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(LongText, default="")
    grade: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | published
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

> SQLite 测试走 `create_all`，新表+新列都会建出来。已有 dev/prod 库不会补列，见 Task 2。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_models.py -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat(passage): add ReadingPassage and Question.passage_id"
```

---

### Task 2: 存量库补 `passage_id` 列

**Files:**
- Create: `backend/app/migrate_reading_passage.py`
- Modify: `backend/app/main.py`（startup 调用）

> `create_all` 不会给已存在的 `questions` 补列。与 `migrate_question_bank.py` 同模式：缺列才 `ALTER`。新表 `reading_passages` 由 startup 里已有的 `Base.metadata.create_all` 创建。

- [ ] **Step 1: 写迁移脚本**

```python
"""一次性迁移：给存量 questions 表补 passage_id。

create_all 不会给已存在的表补列。运行：cd backend && python -m app.migrate_reading_passage
幂等：列已存在则跳过。不建 FK（对齐 bank_id）。
"""
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .database import engine, SessionLocal


def migrate(db: Session) -> None:
    insp = inspect(engine)
    if "questions" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("questions")}
    if "passage_id" not in cols:
        db.execute(text("ALTER TABLE questions ADD COLUMN passage_id INTEGER"))
        db.commit()


if __name__ == "__main__":
    db = SessionLocal()
    try:
        from .models import Base
        from .database import engine as _engine
        Base.metadata.create_all(bind=_engine)
        migrate(db)
        print("迁移完成")
    finally:
        db.close()
```

- [ ] **Step 2: startup 调用**

`backend/app/main.py` 的 `_ensure_db_tables` 在 `_sqlite_relax_questions_lesson_id(db)` 之后追加：

```python
        from .migrate_reading_passage import migrate as _migrate_reading_passage
        _migrate_reading_passage(db)
```

把现有 `except` 的 warning 文案扩成也能覆盖这次迁移，或再包一层 try/except：

```python
    try:
        from .migrate_reading_passage import migrate as _migrate_reading_passage
        _migrate_reading_passage(db)
    except Exception as exc:
        _log.warning("questions.passage_id 迁移失败: %s", exc)
```

放在 `finally: db.close()` 之前、现有 lesson_id try 块之后（可共用同一个 `db`）。

- [ ] **Step 3: 提交**

```bash
git add backend/app/migrate_reading_passage.py backend/app/main.py
git commit -m "feat(passage): migrate questions.passage_id on existing DBs"
```

---

### Task 3: 挖空计数与对齐

**Files:**
- Create: `backend/app/core/passage_markup.py`
- Test: `backend/tests/test_passage_markup.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_passage_markup.py
from app.core.passage_markup import FILL_BLANK_QTYPES, blanks_aligned, count_blanks


def test_count_blanks():
    assert count_blanks("") == 0
    assert count_blanks("hello") == 0
    assert count_blanks("I have ____ apples.") == 1
    assert count_blanks("____ and ____") == 2
    assert count_blanks("___") == 0  # 3 个下划线不算
    assert count_blanks("________") == 2  # 8 个下划线 = 两处挖空


def test_blanks_aligned_no_fill_blank_always_ok():
    assert blanks_aligned("____ appears in text", fill_blank_count=0) is True
    assert blanks_aligned("no blanks", fill_blank_count=0) is True


def test_blanks_aligned_requires_equal_count():
    assert blanks_aligned("A ____ B ____", fill_blank_count=2) is True
    assert blanks_aligned("A ____ B ____", fill_blank_count=1) is False
    assert blanks_aligned("plain", fill_blank_count=1) is False


def test_fill_blank_qtypes():
    assert "fill_blank" in FILL_BLANK_QTYPES
    assert "cloze" in FILL_BLANK_QTYPES
    assert "single_choice" not in FILL_BLANK_QTYPES
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_passage_markup.py -v`

Expected: FAIL，`ModuleNotFoundError: No module named 'app.core.passage_markup'`

- [ ] **Step 3: 实现**

```python
# backend/app/core/passage_markup.py
"""阅读材料轻量标记：挖空计数。渲染在前端，这里只做对齐校验。"""

BLANK = "____"
FILL_BLANK_QTYPES = frozenset({"fill_blank", "cloze"})


def count_blanks(content: str) -> int:
    return (content or "").count(BLANK)


def blanks_aligned(content: str, fill_blank_count: int) -> bool:
    """无填空子题时不强制；有填空子题时 ____ 个数必须相等。"""
    if fill_blank_count <= 0:
        return True
    return count_blanks(content) == fill_blank_count
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_passage_markup.py -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/passage_markup.py backend/tests/test_passage_markup.py
git commit -m "feat(passage): blank-count alignment helper"
```

---

## Phase 1：后端 API

### Task 4: `POST/GET /api/passages` 建材料+子题

**Files:**
- Create: `backend/app/routers/passages.py`
- Modify: `backend/app/main.py`（include_router）
- Test: `backend/tests/test_passages.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_passages.py
import json
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Question, QuestionBank, ReadingPassage
from conftest import auth_headers, make_account

client = TestClient(app)


def _parent_with_bank():
    db = SessionLocal()
    p = make_account(db, "pass_parent", "parent")
    bank = QuestionBank(user_id=p.id, title="语文卷", subject="语文", source="manual")
    db.add(bank)
    db.commit()
    headers = auth_headers(p)
    bid, pid = bank.id, p.id
    db.close()
    return headers, bid, pid


def test_create_passage_with_questions(client, setup_db):
    h, bid, _ = _parent_with_bank()
    body = {
        "title": "小蝌蚪找妈妈",
        "content": "小蝌蚪 **游啊游**。它们看见 ____。",
        "subject": "语文",
        "bank_id": bid,
        "questions": [
            {
                "qtype": "fill_blank",
                "question": "它们看见了什么？",
                "answer": "鲤鱼",
                "answer_json": {"blanks": ["鲤鱼"]},
            },
            {
                "qtype": "short_answer",
                "question": "小蝌蚪在做什么？",
                "answer": "找妈妈",
                "answer_json": {"sample": "找妈妈", "rubric": ""},
            },
        ],
    }
    r = client.post("/api/passages", json=body, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] > 0
    assert len(data["question_ids"]) == 2
    db = SessionLocal()
    psg = db.get(ReadingPassage, data["id"])
    assert psg.title == "小蝌蚪找妈妈"
    assert psg.status == "pending"
    assert psg.bank_id == bid
    qs = db.query(Question).filter_by(passage_id=psg.id).order_by(Question.id).all()
    db.close()
    assert len(qs) == 2
    assert qs[0].qtype == "fill_blank"
    assert qs[0].qtype_category == "blank"
    assert qs[0].status == "pending"
    assert qs[0].bank_id == bid
    assert qs[1].qtype == "short_answer"


def test_create_passage_rejects_blank_mismatch(client, setup_db):
    h, bid, _ = _parent_with_bank()
    body = {
        "title": "不对齐",
        "content": "只有一处 ____",
        "bank_id": bid,
        "questions": [
            {"qtype": "fill_blank", "question": "空1", "answer_json": {"blanks": ["a"]}},
            {"qtype": "fill_blank", "question": "空2", "answer_json": {"blanks": ["b"]}},
        ],
    }
    r = client.post("/api/passages", json=body, headers=h)
    assert r.status_code == 400


def test_get_passage_returns_questions(client, setup_db):
    h, bid, _ = _parent_with_bank()
    r = client.post("/api/passages", json={
        "title": "短文", "content": "正文", "bank_id": bid,
        "questions": [{"qtype": "short_answer", "question": "主旨？", "answer": "春天"}],
    }, headers=h)
    pid = r.json()["id"]
    g = client.get(f"/api/passages/{pid}", headers=h)
    assert g.status_code == 200
    data = g.json()
    assert data["title"] == "短文"
    assert data["content"] == "正文"
    assert len(data["questions"]) == 1
    assert data["questions"][0]["question"] == "主旨？"


def test_list_passages_by_bank(client, setup_db):
    h, bid, _ = _parent_with_bank()
    client.post("/api/passages", json={"title": "A", "content": "c", "bank_id": bid}, headers=h)
    r = client.get(f"/api/passages?bank_id={bid}", headers=h)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 1
    assert rows[0]["title"] == "A"
    assert rows[0]["question_count"] == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_passages.py -v`

Expected: FAIL（路由 404）

- [ ] **Step 3: 实现 router**

```python
# backend/app/routers/passages.py
"""阅读理解材料：建材料（可带子题）、列材料、拉材料+子题。"""
import json
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import require_role
from ..core.passage_markup import FILL_BLANK_QTYPES, blanks_aligned
from ..core.question_types import CATEGORY_OF_QTYPE
from ..database import get_db
from ..models import Question, QuestionBank, ReadingPassage, User

router = APIRouter(prefix="/api/passages", tags=["passages"])


class PassageQuestionIn(BaseModel):
    qtype: str = "short_answer"
    question: str
    answer: str = ""
    options: list[dict] = []
    answer_json: dict = {}
    analysis: str = ""
    difficulty: str = "medium"
    tags: dict = {}


class PassageCreateReq(BaseModel):
    title: str
    content: str
    subject: str = ""
    grade: int | None = None
    bank_id: int | None = None
    questions: list[PassageQuestionIn] = []


def _require_passage(passage_id: int, user: User, db: Session) -> ReadingPassage:
    p = db.get(ReadingPassage, passage_id)
    if not p or (user.role != "admin" and p.user_id != user.id):
        raise HTTPException(status_code=404, detail="阅读材料不存在")
    return p


def _dump_question(q: Question) -> dict:
    return {
        "id": q.id, "qtype": q.qtype, "qtype_category": q.qtype_category,
        "question": q.question, "answer": q.answer, "analysis": q.analysis or "",
        "difficulty": q.difficulty, "status": q.status,
        "options": json.loads(q.options or "[]"),
        "answer_json": json.loads(q.answer_json or "{}"),
        "bank_id": q.bank_id, "passage_id": q.passage_id,
    }


@router.post("")
def create_passage(req: PassageCreateReq, user: User = Depends(require_role("parent", "admin")),
                   db: Session = Depends(get_db)):
    title = req.title.strip()
    content = req.content.strip()
    if not title:
        raise HTTPException(status_code=400, detail="材料标题不能为空")
    if not content:
        raise HTTPException(status_code=400, detail="材料正文不能为空")
    fill_n = sum(1 for q in req.questions if q.qtype in FILL_BLANK_QTYPES)
    if not blanks_aligned(content, fill_n):
        raise HTTPException(status_code=400, detail="材料挖空个数须与填空子题个数一致")
    bank = None
    if req.bank_id:
        bank = db.get(QuestionBank, req.bank_id)
        if not bank or (user.role != "admin" and bank.user_id != user.id):
            raise HTTPException(status_code=404, detail="卷子不存在")
    subject = (req.subject or (bank.subject if bank else "") or "").strip()
    grade = req.grade if req.grade is not None else (bank.grade if bank else None)
    p = ReadingPassage(
        user_id=user.id, bank_id=req.bank_id, subject=subject,
        title=title, content=content, grade=grade, status="pending",
    )
    db.add(p)
    db.flush()
    ids: list[int] = []
    today = date_type.today()
    for item in req.questions:
        stem = item.question.strip()
        if not stem:
            raise HTTPException(status_code=400, detail="子题题干不能为空")
        category = CATEGORY_OF_QTYPE.get(item.qtype, "subjective")
        q = Question(
            lesson_id=None,
            bank_id=req.bank_id,
            passage_id=p.id,
            qtype=item.qtype,
            qtype_category=category,
            question=stem,
            answer=item.answer.strip(),
            answer_json=json.dumps(item.answer_json or {}, ensure_ascii=False),
            options=json.dumps(item.options or [], ensure_ascii=False),
            analysis=item.analysis.strip(),
            difficulty=item.difficulty or "medium",
            tags=json.dumps(item.tags or {}, ensure_ascii=False),
            subject=subject,
            date=today,
            status="pending",
        )
        db.add(q)
        db.flush()
        ids.append(q.id)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "question_ids": ids}


@router.get("")
def list_passages(bank_id: int | None = None,
                  user: User = Depends(require_role("parent", "admin")),
                  db: Session = Depends(get_db)):
    q = db.query(ReadingPassage).filter_by(user_id=user.id)
    if bank_id is not None:
        q = q.filter_by(bank_id=bank_id)
    rows = q.order_by(ReadingPassage.id.desc()).all()
    from sqlalchemy import func
    counts = dict(
        db.query(Question.passage_id, func.count(Question.id))
        .filter(Question.passage_id.isnot(None))
        .group_by(Question.passage_id)
        .all()
    )
    return [{
        "id": p.id, "title": p.title, "subject": p.subject, "grade": p.grade,
        "bank_id": p.bank_id, "status": p.status,
        "question_count": int(counts.get(p.id, 0)),
    } for p in rows]


@router.get("/{passage_id}")
def get_passage(passage_id: int, user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    p = _require_passage(passage_id, user, db)
    qs = db.query(Question).filter_by(passage_id=p.id).order_by(Question.id).all()
    return {
        "id": p.id, "title": p.title, "content": p.content, "subject": p.subject,
        "grade": p.grade, "bank_id": p.bank_id, "status": p.status,
        "questions": [_dump_question(q) for q in qs],
    }
```

`backend/app/main.py` 顶部 import 区把 `passages` 加进 `from .routers import ...`，并在 `include_router` 区追加：

```python
app.include_router(passages.router)
```

放在 `app.include_router(bank.router)` 附近。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_passages.py -v`

Expected: PASS（4 项）

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/passages.py backend/app/main.py backend/tests/test_passages.py
git commit -m "feat(passage): create/list/get reading passages with sub-questions"
```

---

### Task 5: `add_question.passage_id` + 拉题嵌入材料 + 子题判分复用

**Files:**
- Modify: `backend/app/routers/questions.py`（`AddReq` + `add_question`）
- Modify: `backend/app/routers/bank.py`（`list_bank_questions` 返回 `passage_id` + `passage`）
- Modify: `backend/tests/test_questions_review.py`
- Modify: `backend/tests/test_bank.py` 或 `backend/tests/test_passages.py`（追加判分复用）

- [ ] **Step 1: 写失败测试**

在 `test_questions_review.py` 追加：

```python
from app.models import Question, ReadingPassage, QuestionBank


def test_add_question_with_passage_id(client, setup_db):
    db = SessionLocal()
    parent = make_account(db, "add_psg_parent", "parent")
    psg = ReadingPassage(user_id=parent.id, subject="英语", title="Apple",
                         content="I have an /ˈæpl/.", status="pending")
    db.add(psg)
    db.commit()
    pid = psg.id
    h = auth_headers(parent)
    db.close()
    body = {
        "lesson_id": None, "bank_id": None, "passage_id": pid,
        "qtype": "short_answer", "question": "What fruit?", "answer": "apple",
    }
    r = client.post("/api/questions", json=body, headers=h)
    assert r.status_code == 200
    db = SessionLocal()
    q = db.get(Question, r.json()["id"])
    db.close()
    assert q.passage_id == pid
    assert q.status == "pending"
```

在 `test_passages.py` 追加（复用 `_parent_with_bank`）：

```python
from conftest import parent_child


def test_list_bank_questions_embeds_passage(client, setup_db):
    h, bid, _ = _parent_with_bank()
    cr = client.post("/api/passages", json={
        "title": "短文", "content": "**春天**来了。", "bank_id": bid,
        "questions": [{"qtype": "short_answer", "question": "什么季节？", "answer": "春天"}],
    }, headers=h)
    qid = cr.json()["question_ids"][0]
    db = SessionLocal()
    db.get(Question, qid).status = "published"
    db.commit()
    db.close()
    r = client.get(f"/api/banks/{bid}/questions", headers=h)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["passage_id"] == cr.json()["id"]
    assert items[0]["passage"]["title"] == "短文"
    assert items[0]["passage"]["content"] == "**春天**来了。"


def test_submit_passage_child_reuses_grade(client, setup_db):
    """子题走现有 grade_question，不改判分实现。"""
    db = SessionLocal()
    parent, child, _, ch = parent_child(db, "psg_grade")
    bank = QuestionBank(user_id=parent.id, title="阅读卷", subject="语文", source="manual")
    db.add(bank)
    db.flush()
    psg = ReadingPassage(user_id=parent.id, bank_id=bank.id, subject="语文",
                         title="春天", content="春天来了。", status="published")
    db.add(psg)
    db.flush()
    q = Question(
        bank_id=bank.id, passage_id=psg.id,
        qtype="single_choice", qtype_category="choice",
        question="写了什么季节？",
        options='[{"label":"春天","value":0},{"label":"冬天","value":1}]',
        answer_json='{"correct_index":0}', answer="春天", status="published",
    )
    db.add(q)
    db.commit()
    bid, qid = bank.id, q.id
    db.close()
    r = client.post("/api/banks/submit",
                    json={"bank_id": bid, "answers": [{"question_id": qid, "selected_index": 0}]},
                    headers=ch)
    assert r.status_code == 200
    assert r.json()["score"] == 1
    assert r.json()["answers"][0]["is_correct"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_questions_review.py::test_add_question_with_passage_id tests/test_passages.py::test_list_bank_questions_embeds_passage tests/test_passages.py::test_submit_passage_child_reuses_grade -v`

Expected: FAIL（`AddReq` 无 `passage_id` → 422；拉题 JSON 无 `passage`）

- [ ] **Step 3: 实现**

`AddReq` 增加字段（放在 `bank_id` 后）：

```python
    passage_id: int | None = None
```

`add_question` 里构造 `Question(...)` 时增加 `passage_id=req.passage_id`。若 `req.passage_id` 非空，校验材料存在（`db.get(ReadingPassage, req.passage_id)`，404 若无）；`subject` 优先从材料继承，其次从卷继承：

```python
    subject = ""
    if req.passage_id:
        psg = db.get(ReadingPassage, req.passage_id)
        if not psg:
            raise HTTPException(status_code=404, detail="阅读材料不存在")
        subject = (psg.subject or "").strip()
    if req.bank_id:
        bank = db.get(QuestionBank, req.bank_id)
        if bank:
            subject = subject or (bank.subject or "").strip()
```

`questions.py` 顶部 import `ReadingPassage`。

`bank.py` 的 `list_bank_questions` 返回值每项加上 `passage_id` 与 `passage`。先收集 `passage_id`，一次查出材料，避免 N+1：

```python
    qs = q.order_by(Question.id).all()
    pids = {x.passage_id for x in qs if x.passage_id}
    passages = {}
    if pids:
        for p in db.query(ReadingPassage).filter(ReadingPassage.id.in_(pids)).all():
            passages[p.id] = {"id": p.id, "title": p.title, "content": p.content, "subject": p.subject}
    return [{
        "id": item.id, "qtype": item.qtype, "qtype_category": item.qtype_category,
        "question": item.question, "options": json.loads(item.options or "[]"),
        "answer": item.answer, "analysis": item.analysis, "difficulty": item.difficulty,
        "tags": json.loads(item.tags or "{}"),
        "passage_id": item.passage_id,
        "passage": passages.get(item.passage_id),
    } for item in qs]
```

`bank.py` 顶部 import 把 `ReadingPassage` 加进 `from ..models import ...`。

**不要改** `submit_bank` / `grade_question`。`test_submit_passage_child_reuses_grade` 证明现有提交路径对子题生效。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_questions_review.py tests/test_passages.py tests/test_bank.py -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/questions.py backend/app/routers/bank.py backend/tests/test_questions_review.py backend/tests/test_passages.py
git commit -m "feat(passage): add_question passage_id and embed passage in bank questions"
```

---

### Task 6: 审核台按材料分组 + 通过本篇

**Files:**
- Modify: `backend/app/routers/questions.py`（`review_questions` 分组 + `approve_question` 发布材料 + `approve-by-passage`）
- Modify: `backend/tests/test_questions_review.py`

- [ ] **Step 1: 写失败测试**

```python
def test_review_groups_by_passage(client, setup_db):
    db = SessionLocal()
    parent = make_account(db, "rev_psg", "parent")
    from datetime import date
    today = date.today()
    psg = ReadingPassage(user_id=parent.id, subject="语文", title="找妈妈",
                         content="小蝌蚪游啊游。", status="pending")
    db.add(psg)
    db.flush()
    q = Question(passage_id=psg.id, qtype="short_answer", qtype_category="subjective",
                 question="谁在游？", answer="小蝌蚪", subject="语文",
                 date=today, status="pending")
    db.add(q)
    db.commit()
    pid, qid, hid = psg.id, q.id, parent.id
    db.close()
    h = _ph(hid)
    r = client.get(f"/api/questions/review?d={today.isoformat()}", headers=h)
    assert r.status_code == 200
    groups = r.json()["groups"]
    g = next(x for x in groups if x.get("passage_id") == pid)
    assert g["lesson_title"] == "找妈妈"
    assert g["passage"]["content"] == "小蝌蚪游啊游。"
    assert g["questions"][0]["id"] == qid


def test_approve_question_publishes_passage(client, setup_db):
    db = SessionLocal()
    parent = make_account(db, "appr_psg", "parent")
    psg = ReadingPassage(user_id=parent.id, subject="语文", title="T", content="C", status="pending")
    db.add(psg)
    db.flush()
    q = Question(passage_id=psg.id, qtype="short_answer", question="Q", answer="A",
                 status="pending")
    db.add(q)
    db.commit()
    qid, pid, hid = q.id, psg.id, parent.id
    db.close()
    r = client.post(f"/api/questions/{qid}/approve", headers=_ph(hid))
    assert r.status_code == 200
    db = SessionLocal()
    assert db.get(ReadingPassage, pid).status == "published"
    db.close()


def test_approve_by_passage(client, setup_db):
    from datetime import date
    db = SessionLocal()
    parent = make_account(db, "appr_by_psg", "parent")
    today = date.today()
    psg = ReadingPassage(user_id=parent.id, subject="语文", title="T", content="C", status="pending")
    db.add(psg)
    db.flush()
    q1 = Question(passage_id=psg.id, qtype="short_answer", question="Q1", answer="A",
                  date=today, status="pending")
    q2 = Question(passage_id=psg.id, qtype="short_answer", question="Q2", answer="B",
                  date=today, status="pending")
    db.add_all([q1, q2])
    db.commit()
    pid, hid = psg.id, parent.id
    db.close()
    r = client.post("/api/questions/approve-by-passage",
                    params={"passage_id": pid, "d": today.isoformat()},
                    headers=_ph(hid))
    assert r.status_code == 200
    db = SessionLocal()
    assert db.get(ReadingPassage, pid).status == "published"
    qs = db.query(Question).filter_by(passage_id=pid).all()
    assert all(x.status == "published" for x in qs)
    db.close()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_questions_review.py::test_review_groups_by_passage tests/test_questions_review.py::test_approve_question_publishes_passage tests/test_questions_review.py::test_approve_by_passage -v`

Expected: FAIL（分组仍按 bank/lesson/solo；无 approve-by-passage）

- [ ] **Step 3: 实现**

`review_questions` 的 `_group_key` **优先**按材料：

```python
    def _group_key(item: Question) -> tuple:
        if item.passage_id:
            return ("passage", item.passage_id)
        if item.lesson_id:
            return ("lesson", item.lesson_id)
        if item.bank_id:
            return ("bank", item.bank_id)
        return ("solo", item.id)
```

`grouped.setdefault` 里每题 dict 加上 `"passage_id": item.passage_id`。

`group_meta` 增加 passage 分支（在 lesson 分支之前判断 `gkey[0] == "passage"`）：

```python
            if gkey[0] == "passage":
                psg = db.get(ReadingPassage, gkey[1])
                title = psg.title if psg else f"阅读材料{gkey[1]}"
                if psg and (psg.subject or "").strip():
                    subj = psg.subject.strip()
                group_meta[gkey] = {
                    "subject": subj, "lesson_id": None,
                    "bank_id": psg.bank_id if psg else None,
                    "passage_id": gkey[1],
                    "lesson_title": title,
                    "passage": {
                        "id": psg.id if psg else gkey[1],
                        "title": title,
                        "content": psg.content if psg else "",
                    },
                }
```

无 `passage_id` 的旧分组保持原字段；前端用 `g.passage_id` / `g.passage` 可选读取。

`approve_question` 在 `q.status = "published"` 后：

```python
    if q.passage_id:
        psg = db.get(ReadingPassage, q.passage_id)
        if psg and psg.status != "published":
            psg.status = "published"
```

新增端点（与 `approve-by-bank` 并列）：

```python
@router.post("/approve-by-passage")
def approve_by_passage(passage_id: int, d: date_type,
                       _auth: User = Depends(require_role("parent", "admin")),
                       db: Session = Depends(get_db)):
    db.query(Question).filter_by(passage_id=passage_id, date=d, status="pending").update(
        {"status": "published"}, synchronize_session=False)
    psg = db.get(ReadingPassage, passage_id)
    if psg:
        psg.status = "published"
    db.commit()
    return {"ok": True}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_questions_review.py -v`

Expected: PASS（含原有 lesson/subject 分组用例）

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/questions.py backend/tests/test_questions_review.py
git commit -m "feat(passage): review groups by reading passage"
```

---

## Phase 2：三来源（OCR / 第三方）

### Task 7: `QuestionDraft` 带材料字段 + OCR 结构化 `passages[]`

**Files:**
- Modify: `backend/app/core/source_adapter.py`
- Modify: `backend/app/services/ocr_import.py`
- Modify: `backend/tests/test_ocr_import.py`
- Modify: `backend/tests/test_source_adapter.py`

- [ ] **Step 1: 写失败测试**

`test_source_adapter.py` 追加：

```python
def test_ocr_adapter_copies_passage_fields():
    raw = {"questions": [{
        "qtype": "short_answer",
        "question": "主旨？",
        "answer": "春天",
        "passage_title": "短文",
        "passage_content": "春天来了。",
    }]}
    drafts = OcrAdapter().normalize(raw)
    assert drafts[0].passage_title == "短文"
    assert drafts[0].passage_content == "春天来了。"
```

`test_ocr_import.py` 追加：

```python
def test_parse_questions_keeps_legacy_shape():
    from app.services.ocr_import import _parse_import
    import json
    raw = json.dumps({"questions": [{"qtype": "short_answer", "question": "Q"}]})
    passages, questions = _parse_import(raw)
    assert passages == []
    assert questions[0]["question"] == "Q"


def test_parse_import_passages_shape():
    from app.services.ocr_import import _parse_import
    import json
    raw = json.dumps({
        "passages": [{
            "title": "小蝌蚪",
            "content": "小蝌蚪 **游啊游**。看见 ____。",
            "questions": [
                {"qtype": "fill_blank", "question": "看见什么？", "answer_json": {"blanks": ["鲤鱼"]}},
            ],
        }],
        "questions": [{"qtype": "short_answer", "question": "独立题"}],
    }, ensure_ascii=False)
    passages, questions = _parse_import(raw)
    assert len(passages) == 1
    assert passages[0]["title"] == "小蝌蚪"
    assert len(questions) == 1
```

再测 flatten 后的 draft（在 `ocr_import` 加一个纯函数，不调 LLM）：

```python
def test_flatten_passages_onto_drafts():
    from app.services.ocr_import import _flatten_import
    passages = [{"title": "T", "content": "C", "questions": [
        {"qtype": "short_answer", "question": "子题", "answer": "A"},
    ]}]
    questions = [{"qtype": "short_answer", "question": "独立", "answer": "B"}]
    drafts = _flatten_import(passages, questions)
    assert len(drafts) == 2
    assert drafts[0].question == "子题"
    assert drafts[0].passage_title == "T"
    assert drafts[0].passage_content == "C"
    assert drafts[1].question == "独立"
    assert drafts[1].passage_content == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_source_adapter.py::test_ocr_adapter_copies_passage_fields tests/test_ocr_import.py -v`

Expected: FAIL（`QuestionDraft` 无材料字段 / `_parse_import` 不存在）

- [ ] **Step 3: 实现**

`QuestionDraft` 加两字段（放在 `tags` 后）：

```python
    passage_title: str = ""
    passage_content: str = ""
```

`OcrAdapter.normalize` 构造 `QuestionDraft(...)` 时加上：

```python
                passage_title=(it.get("passage_title") or "").strip(),
                passage_content=(it.get("passage_content") or it.get("passage") or "").strip(),
```

`ManualAdapter.normalize` 同样从 `raw` 读取这两字段（人工录入走 `POST /api/passages`，这里只为接口完整）。

`ocr_import.py` 把 `_parse_questions` 留作薄封装，新增：

```python
def _parse_import(raw: str) -> tuple[list[dict], list[dict]]:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return [], []
    if isinstance(data, list):
        return [], [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return [], []
    passages = [x for x in (data.get("passages") or []) if isinstance(x, dict)]
    questions = [x for x in (data.get("questions") or []) if isinstance(x, dict)]
    return passages, questions


def _parse_questions(raw: str) -> list[dict]:
    _passages, questions = _parse_import(raw)
    return questions


def _flatten_import(passages: list[dict], questions: list[dict]) -> list[QuestionDraft]:
    items: list[dict] = []
    for p in passages:
        title = (p.get("title") or "").strip()
        content = (p.get("content") or "").strip()
        for it in p.get("questions") or []:
            if not isinstance(it, dict):
                continue
            items.append({**it, "passage_title": title, "passage_content": content})
    items.extend(questions)
    return OcrAdapter().normalize({"questions": items})
```

`_STRUCTURE_SYSTEM` 整段替换为（保持旧 `questions` 形状，并补材料规则）：

```python
_STRUCTURE_SYSTEM = (
    "你是小学题库录入助手。根据 OCR 识别出的卷子文字，把题目结构化成标准 JSON。\n"
    "若识别到阅读理解（一篇短文后跟若干小题），返回：\n"
    '{"passages":[{"title":"材料标题","content":"材料正文","questions":[...]}],'
    '"questions":[独立题]}。\n'
    "没有阅读材料时只返回 "
    '{"questions":[{"qtype":"single_choice|multi_choice|true_false|fill_blank|'
    'cloze|calculation|matching|short_answer|essay|application|oral",'
    '"question":"题干","options":[{"label":"选项","value":0}],'
    '"answer_json":{},"answer":"标准答案","analysis":"解析"}]}。\n'
    "材料 content 只允许这些标记：# / ## 标题、**加粗**、*斜体*、<u>下划线</u>、"
    "/音标/（两侧斜杠）、____（四个下划线表示挖空）。其余当纯文本。\n"
    "材料中 ____ 的个数必须等于该材料下 fill_blank/cloze 子题的个数与顺序。\n"
    "options 仅选择题/连线题需要；answer_json 按题型填 correct_index / blanks / pairs / rubric。\n"
    "无法确定的题 qtype 填 short_answer。"
)
```

`structure_questions_from_text` 在解析后改走 flatten（fake provider 仍提前 `return []`）：

```python
        passages, questions = _parse_import(raw)
        return _flatten_import(passages, questions)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_ocr_import.py tests/test_source_adapter.py -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/source_adapter.py backend/app/services/ocr_import.py backend/tests/test_ocr_import.py backend/tests/test_source_adapter.py
git commit -m "feat(passage): OCR import supports passage + sub-questions"
```

---

### Task 8: `_persist_drafts` 按材料去重建 `ReadingPassage` + 第三方字段

**Files:**
- Modify: `backend/app/routers/bank.py`（`_persist_drafts`）
- Modify: `backend/app/core/tiku_cn_adapter.py`（`item_to_draft`）
- Test: `backend/tests/test_bank.py`、`backend/tests/test_tiku_cn_adapter.py`（若无现成 item_to_draft 测试则加在 `test_bank.py`）

- [ ] **Step 1: 写失败测试**

在 `test_bank.py` 追加：

```python
from app.models import ReadingPassage
from app.core.source_adapter import QuestionDraft
from app.routers.bank import _persist_drafts


def test_persist_drafts_groups_passage(client, setup_db):
    db = SessionLocal()
    from conftest import make_account
    p = make_account(db, "persist_psg", "parent")
    bank = QuestionBank(user_id=p.id, title="卷", subject="英语", source="manual")
    db.add(bank)
    db.flush()
    drafts = [
        QuestionDraft(qtype="short_answer", question="Q1", answer="A",
                      passage_title="Apple", passage_content="I like apples."),
        QuestionDraft(qtype="fill_blank", question="Q2", answer="red",
                      passage_title="Apple", passage_content="I like apples."),
        QuestionDraft(qtype="short_answer", question="独立题", answer="B"),
    ]
    ids = _persist_drafts(db, bank, drafts, "photo")
    db.commit()
    assert len(ids) == 3
    qs = db.query(Question).filter(Question.id.in_(ids)).order_by(Question.id).all()
    assert qs[0].passage_id is not None
    assert qs[0].passage_id == qs[1].passage_id
    assert qs[2].passage_id is None
    psg = db.get(ReadingPassage, qs[0].passage_id)
    assert psg.title == "Apple"
    assert psg.content == "I like apples."
    assert psg.bank_id == bank.id
    assert psg.status == "pending"
    db.close()
```

第三方：在 `test_bank.py` 或新建用例，直接调 `item_to_draft`：

```python
from app.core.tiku_cn_adapter import item_to_draft


def test_tiku_item_reads_passage_fields():
    d = item_to_draft({
        "question": "What is the main idea?",
        "type": "short_answer",
        "answer": "spring",
        "passage": "Spring is coming.",
        "passage_title": "Spring",
    })
    assert d is not None
    assert d.passage_content == "Spring is coming."
    assert d.passage_title == "Spring"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_bank.py::test_persist_drafts_groups_passage tests/test_bank.py::test_tiku_item_reads_passage_fields -v`

Expected: FAIL（persist 不建 ReadingPassage；item_to_draft 无材料字段）

- [ ] **Step 3: 实现**

`_persist_drafts` 在循环里按 `(passage_title, passage_content)` 缓存材料 id：

```python
def _persist_drafts(db: Session, bank: QuestionBank, drafts: list[QuestionDraft], tag_source: str) -> list[int]:
    today = date_type.today()
    subj = (bank.subject or "").strip()
    ids: list[int] = []
    passage_ids: dict[tuple[str, str], int] = {}
    for d in drafts:
        if not d.question:
            continue
        category = CATEGORY_OF_QTYPE.get(d.qtype, "subjective")
        tags = {**(d.tags or {}), "source": tag_source}
        pid = None
        content = (d.passage_content or "").strip()
        if content:
            key = ((d.passage_title or "").strip(), content)
            if key not in passage_ids:
                rp = ReadingPassage(
                    user_id=bank.user_id,
                    bank_id=bank.id,
                    subject=subj,
                    title=key[0] or (bank.title or "阅读材料"),
                    content=content,
                    grade=bank.grade,
                    status="pending",
                )
                db.add(rp)
                db.flush()
                passage_ids[key] = rp.id
            pid = passage_ids[key]
        q = Question(
            bank_id=bank.id,
            passage_id=pid,
            qtype=d.qtype or "short_answer",
            qtype_category=category,
            question=d.question,
            answer=d.answer,
            answer_json=json.dumps(d.answer_json or {}, ensure_ascii=False),
            options=json.dumps(d.options or [], ensure_ascii=False),
            analysis=d.analysis or "",
            difficulty=d.difficulty or "medium",
            tags=json.dumps(tags, ensure_ascii=False),
            subject=subj,
            date=today,
            status="pending",
        )
        db.add(q)
        db.flush()
        ids.append(q.id)
    if ids and bank.source == "manual":
        bank.source = "third_party"
    return ids
```

`bank.py` 的 models import 加入 `ReadingPassage`。OCR 导入不在此处校验挖空对齐（识别可能不全，交给审核台人工改）；家长 `POST /api/passages` 才 400。

`item_to_draft` 在 `return QuestionDraft(...)` 前取材料：

```python
    passage_content = (
        item.get("passage") or item.get("article") or item.get("material")
        or item.get("passage_content") or ""
    )
    if not isinstance(passage_content, str):
        passage_content = str(passage_content or "")
    passage_title = (
        item.get("passage_title") or item.get("article_title") or item.get("material_title") or ""
    )
    if not isinstance(passage_title, str):
        passage_title = str(passage_title or "")
```

`QuestionDraft(...)` 加上 `passage_title=passage_title.strip(), passage_content=passage_content.strip()`。

学库宝 `from .tiku_cn_adapter import item_to_draft`，无需再改 `xuekubao_adapter.py`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_bank.py tests/test_ocr_import.py tests/test_source_adapter.py -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/bank.py backend/app/core/tiku_cn_adapter.py backend/tests/test_bank.py
git commit -m "feat(passage): persist OCR/third-party drafts as ReadingPassage groups"
```

---

## Phase 3：前端

> `parent-web` 无自动化测试，验收靠手动走通。Flutter 用 `flutter test`。此阶段每个任务仍独立可提交。

### Task 9: parent-web 白名单渲染 + 阅读理解录入

**Files:**
- Modify: `parent-web/app.js`
- Modify: `parent-web/index.html`（样式）

- [ ] **Step 1: 材料预览样式**

在 `parent-web/index.html` 的 `.bank-qform .bank-import-hint` 规则后追加：

```css
  .passage-preview{margin-top:10px;padding:14px 16px;border-radius:12px;background:#f7f9fc;border:1px solid #e8ecf4;font-size:14px;line-height:1.8;color:#202723}
  .passage-preview h1,.passage-preview h2{font-size:16px;margin:0 0 8px}
  .passage-blank{display:inline-block;min-width:48px;border-bottom:1px solid #334038;height:1em;vertical-align:-2px;margin:0 2px}
  .passage-ipa{font-family:Georgia,"Times New Roman",serif;color:#3158e8;font-size:13px}
  .bank-mode-toggle{display:flex;gap:8px;margin-bottom:14px}
  .bank-mode-toggle button{padding:6px 12px;border-radius:999px;font-size:13px;font-weight:600;color:#69716c;background:#f4f5f3}
  .bank-mode-toggle button.on{background:#edf1ff;color:#3158e8}
  .reading-sub{border:1px solid #e8ecf4;border-radius:12px;padding:14px;margin-top:12px;background:#fff}
  .reading-sub-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}
  .blank-hint{font-size:12px;margin-top:8px}
  .blank-hint.ok{color:#2e8b5a}
  .blank-hint.bad{color:#c05b4a}
```

- [ ] **Step 2: 白名单渲染函数 + 录入模式**

在 `parent-web/app.js` 的 `// ---- 题库管理 ----` 块、`BANK_QTYPES` 之后加入状态与渲染器：

```javascript
let bankEntryMode = 'single'; // single | reading
let readingSubs = [{qtype:'single_choice'}];

function setBankEntryMode(m){
  bankEntryMode = m;
  if(m==='reading' && (!readingSubs || !readingSubs.length)) readingSubs = [{qtype:'single_choice'}];
  render();
}
function setReadingSubQtype(i, v){ readingSubs[i].qtype = v; render(); }
function addReadingSub(){ readingSubs.push({qtype:'single_choice'}); render(); }
function removeReadingSub(i){ if(readingSubs.length>1){ readingSubs.splice(i,1); render(); } }

function escapeHtml(s){
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function renderPassageInline(escaped){
  return escaped
    .replace(/____/g, '<span class="passage-blank"></span>')
    .replace(/&lt;u&gt;([\s\S]*?)&lt;\/u&gt;/g, '<u>$1</u>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\/([^\/:\n]{1,40})\//g, '<span class="passage-ipa">/$1/</span>');
}
function renderPassageMarkup(src){
  return (src||'').split('\n').map(line=>{
    const raw = line.replace(/\s+$/,'');
    if(/^##\s+/.test(raw)){
      return '<h2>'+renderPassageInline(escapeHtml(raw.replace(/^##\s+/,'')))+'</h2>';
    }
    if(/^#\s+/.test(raw)){
      return '<h1>'+renderPassageInline(escapeHtml(raw.replace(/^#\s+/,'')))+'</h1>';
    }
    return renderPassageInline(escapeHtml(raw)) || '<br>';
  }).join('<br>');
}
```

把现有 `buildBankQuestionPayload` / `renderBankChoiceFields` **整函数替换**为带可选下标版本（`idx` 缺省时 id 无后缀，单题表单行为不变）：

```javascript
function _fieldSuf(idx){ return (idx==null || idx===undefined) ? '' : '-'+idx; }
function buildBankQuestionPayload(idx){
  const suf = _fieldSuf(idx);
  const qtype = idx==null ? bankAddQtype : readingSubs[idx].qtype;
  const question = (document.getElementById('bankQText'+suf)?.value||'').trim();
  const analysis = (document.getElementById('bankAnalysis'+suf)?.value||'').trim();
  const difficulty = document.getElementById('bankDifficulty'+suf)?.value
    || document.getElementById('bankDifficulty')?.value || 'medium';
  const cat = BANK_QTYPE_CATEGORY[qtype]||'subjective';
  let options = [], answer_json = {}, answer = '';
  if(cat==='choice'){
    options = bankChoiceOptionsFromForm(idx);
    if(qtype==='multi_choice'){
      const checks = document.querySelectorAll('input[name="bankMultiCorrect'+suf+'"]:checked');
      const ix = [...checks].map(el=>Number(el.value)).filter(n=>!Number.isNaN(n));
      answer_json = {correct_index: ix.length?ix:[0]};
      answer = ix.map(i=>options[i]?.label).filter(Boolean).join('、');
    }else{
      const picked = document.querySelector('input[name="bankSingleCorrect'+suf+'"]:checked');
      const ci = picked ? Number(picked.value) : 0;
      const correct = Number.isNaN(ci)?0:ci;
      answer_json = {correct_index: correct};
      answer = options[correct]?.label || '';
    }
  }else if(cat==='blank'){
    const raw = (document.getElementById('bankBlanks'+suf)?.value||'').trim();
    const blanks = raw.split(/[,，;；\n]+/).map(s=>s.trim()).filter(Boolean);
    answer_json = {blanks};
    answer = blanks.join('；');
  }else if(cat==='match'){
    const raw = (document.getElementById('bankPairs'+suf)?.value||'').trim();
    const pairs = [];
    raw.split('\n').forEach(line=>{
      const p = line.split(/[→\-=]/).map(s=>s.trim()).filter(Boolean);
      if(p.length>=2) pairs.push([p[0], p[1]]);
    });
    answer_json = {pairs};
    answer = pairs.map(p=>p.join('→')).join('；');
  }else{
    answer = (document.getElementById('bankSubjAnswer'+suf)?.value||'').trim();
    const rubric = (document.getElementById('bankRubric'+suf)?.value||'').trim();
    answer_json = {sample: answer, rubric};
  }
  return {lesson_id:null, bank_id:bankSelectedId, qtype, question, answer, options, answer_json, analysis, difficulty, tags:{}};
}
function bankChoiceOptionsFromForm(idx){
  const suf = _fieldSuf(idx);
  const n = Math.max(2, Math.min(8, parseInt(document.getElementById('bankOptCount'+suf)?.value||'4', 10)||4));
  const opts = [];
  for(let i=0;i<n;i++){
    const label = (document.getElementById(`bankOptLabel${i}${suf}`)?.value||'').trim() || `选项${String.fromCharCode(65+i)}`;
    opts.push({label, value:i});
  }
  return opts;
}
function renderBankChoiceFields(idx){
  const suf = _fieldSuf(idx);
  const qtype = idx==null ? bankAddQtype : readingSubs[idx].qtype;
  const multi = qtype==='multi_choice';
  const n = 4;
  const optRows = [...Array(n)].map((_,i)=>{
    const letter = String.fromCharCode(65+i);
    const mark = multi
      ? `<label class="bank-opt-mark"><input type="checkbox" name="bankMultiCorrect${suf}" value="${i}"/>正确答案</label>`
      : `<label class="bank-opt-mark"><input type="radio" name="bankSingleCorrect${suf}" value="${i}" ${i===0?'checked':''}/>正确答案</label>`;
    return `<div class="bank-opt-row">
      <span class="bank-opt-letter">${letter}</span>
      <input id="bankOptLabel${i}${suf}" class="inp" placeholder="选项 ${letter} 内容" />
      ${mark}
    </div>`;
  }).join('');
  const hint = multi ? '可多选「正确答案」' : '勾选唯一正确答案';
  return `<div class="bank-q-block">
    <span class="bank-field-label">选项 <span style="font-weight:500;color:#9aa39d">${hint}</span></span>
    <div class="bank-opt-list">${optRows}</div>
  </div>`;
}
function renderBankAnswerFields(qtype, idx){
  const suf = _fieldSuf(idx);
  const cat = BANK_QTYPE_CATEGORY[qtype]||'subjective';
  if(cat==='choice') return renderBankChoiceFields(idx);
  if(cat==='blank'){
    return `<div class="bank-q-block"><label class="bank-field-label">参考答案（多空用逗号或换行分隔）</label>
      <textarea id="bankBlanks${suf}" class="inp" rows="2" placeholder="如：春天,播种"></textarea></div>`;
  }
  if(cat==='match'){
    return `<div class="bank-q-block"><label class="bank-field-label">连线答案（每行一对，用 → 分隔）</label>
      <textarea id="bankPairs${suf}" class="inp" rows="3" placeholder="苹果→红色"></textarea></div>`;
  }
  return `<div class="bank-q-block">
    <label class="bank-field-label">参考答案 / 范文</label>
    <textarea id="bankSubjAnswer${suf}" class="inp" rows="2"></textarea>
    <label class="bank-field-label" style="margin-top:12px">评分要点（可选）</label>
    <textarea id="bankRubric${suf}" class="inp" rows="2"></textarea>
  </div>`;
}
```

`renderBankQuestionForm` 里原来的 `extra = renderBankChoiceFields()` / blank / match / subjective 分支改成 `extra = renderBankAnswerFields(bankAddQtype)`。

- [ ] **Step 3: 阅读理解表单 + 提交**

```javascript
function renderReadingForm(){
  const qBlocks = readingSubs.map((sub,i)=>{
    const qtypeOpts = BANK_QTYPES.map(q=>`<option value="${q}" ${q===sub.qtype?'selected':''}>${BANK_QTYPE_LABEL[q]}</option>`).join('');
    return `<div class="reading-sub">
      <div class="reading-sub-head">
        <strong>子题 ${i+1}</strong>
        ${readingSubs.length>1?`<button type="button" class="btn-ghost" onclick="removeReadingSub(${i})">删除</button>`:''}
      </div>
      <div class="bank-q-meta">
        <label class="bank-field"><span class="bank-field-label">题型</span>
          <select onchange="setReadingSubQtype(${i}, this.value)">${qtypeOpts}</select></label>
        <label class="bank-field"><span class="bank-field-label">难度</span>
          <select id="bankDifficulty-${i}"><option value="easy">简单</option><option value="medium" selected>中等</option><option value="hard">困难</option></select></label>
      </div>
      <div class="bank-q-block">
        <label class="bank-field-label">题干</label>
        <textarea id="bankQText-${i}" class="inp" rows="3" placeholder="围绕材料出题"></textarea>
      </div>
      ${renderBankAnswerFields(sub.qtype, i)}
      <div class="bank-q-block">
        <label class="bank-field-label">解析（可选）</label>
        <textarea id="bankAnalysis-${i}" class="inp" rows="2"></textarea>
      </div>
    </div>`;
  }).join('');
  return `<div class="bank-q-block">
      <label class="bank-field-label">材料标题</label>
      <input id="readingTitle" class="inp" placeholder="如：小蝌蚪找妈妈" />
    </div>
    <div class="bank-q-block">
      <label class="bank-field-label">材料正文（可用 # 标题、**加粗**、*斜体*、&lt;u&gt;下划线&lt;/u&gt;、/音标/、____ 挖空）</label>
      <textarea id="readingContent" class="inp" rows="6" placeholder="在这里粘贴或编写短文" oninput="updateReadingPreview()"></textarea>
      <div id="readingBlankHint" class="blank-hint"></div>
      <div class="bank-field-label" style="margin-top:10px">预览</div>
      <div id="readingPreview" class="passage-preview"></div>
    </div>
    ${qBlocks}
    <div class="bank-actions-primary" style="margin-top:12px">
      <button type="button" class="btn-ghost" onclick="addReadingSub()">加一道子题</button>
      <button type="button" class="btn-primary" onclick="submitReadingPassage()">提交整篇审核</button>
    </div>`;
}
function updateReadingPreview(){
  const content = document.getElementById('readingContent')?.value || '';
  const box = document.getElementById('readingPreview');
  if(box) box.innerHTML = renderPassageMarkup(content);
  const n = (content.match(/____/g)||[]).length;
  const fillN = (readingSubs||[]).filter(s=>s.qtype==='fill_blank'||s.qtype==='cloze').length;
  const hint = document.getElementById('readingBlankHint');
  if(!hint) return;
  if(fillN===0){ hint.className='blank-hint'; hint.textContent = n?`材料挖空 ${n} 处（无填空子题，挖空仅展示）`:''; return; }
  const ok = n===fillN;
  hint.className = 'blank-hint '+(ok?'ok':'bad');
  hint.textContent = `材料挖空 ${n} 处 / 填空子题 ${fillN} 道`+(ok?'，已对齐':'，须一致才能提交');
}
async function submitReadingPassage(){
  if(!bankSelectedId){ toast('请先选择一张卷子'); return; }
  const title = (document.getElementById('readingTitle')?.value||'').trim();
  const content = (document.getElementById('readingContent')?.value||'').trim();
  if(!title){ toast('请填写材料标题'); return; }
  if(!content){ toast('请填写材料正文'); return; }
  const questions = readingSubs.map((_,i)=>{
    const body = buildBankQuestionPayload(i);
    return {qtype:body.qtype, question:body.question, answer:body.answer,
            options:body.options, answer_json:body.answer_json,
            analysis:body.analysis, difficulty:body.difficulty, tags:body.tags};
  });
  if(questions.some(q=>!q.question)){ toast('请填写每道子题的题干'); return; }
  const blankN = (content.match(/____/g)||[]).length;
  const fillN = questions.filter(q=>q.qtype==='fill_blank'||q.qtype==='cloze').length;
  if(fillN>0 && blankN!==fillN){ toast(`材料挖空 ${blankN} 处，填空子题 ${fillN} 道，须一致`); return; }
  const bank = bankList.find(b=>b.id===bankSelectedId);
  const r = await api('/api/passages', {method:'POST', body:{
    title, content, subject: bank?.subject||'语文', grade: bank?.grade??null,
    bank_id: bankSelectedId, questions
  }});
  if(r && r.id){ toast('阅读理解已提交审核'); readingSubs=[{qtype:'single_choice'}]; render(); }
  else toast(apiErrorMsg(r, '提交失败'));
}
```

`renderBankQuestionForm` 开头加模式切换，`bankEntryMode==='reading'` 时用 `renderReadingForm()` 替换题干/答案区（导入条保留）：

```javascript
  const modeBar = `<div class="bank-mode-toggle">
    <button type="button" class="${bankEntryMode==='single'?'on':''}" onclick="setBankEntryMode('single')">单题</button>
    <button type="button" class="${bankEntryMode==='reading'?'on':''}" onclick="setBankEntryMode('reading')">阅读理解</button>
  </div>`;
```

`renderBankQuestionForm` 在 `return \`<div class="parent-panel bank-qform"...` 的 `.bd` 里，题型区之前插入 `${modeBar}`；若 `bankEntryMode==='reading'`，`.bd` 内部改为 `${modeBar}${renderReadingForm()}` 再加上原来的 `bank-import-bar`（拍照/第三方仍挂在卷上），不要渲染单题的「提交审核」按钮。

`function render()` 现为 `document.getElementById('main').innerHTML = renderParent();`。在赋值后追加：

```javascript
function render(){
  document.getElementById('main').innerHTML = renderParent();
  if(parentTab==='题库管理') updateReadingPreview();
}
```

- [ ] **Step 4: 手动验证**

后端从 `backend/` 启动后：建一卷（语文）→ 选「阅读理解」→ 填标题/正文（含一处 `____`）+ 一道填空子题 + 一道简答 → 提交成功 → 审核台能看到（Task 10 会展示材料）。挖空数对不上时应 toast 拦截。

- [ ] **Step 5: 提交**

```bash
git add parent-web/app.js parent-web/index.html
git commit -m "feat(parent-web): reading passage entry form with whitelist preview"
```

---

### Task 10: parent-web 审核台展示材料 + 通过本篇

**Files:**
- Modify: `parent-web/app.js`（`reviewGroupKey` / `renderQuestionTab`）

- [ ] **Step 1: 分组 key 纳入 passage**

```javascript
function reviewGroupKey(g){
  if(g.passage_id) return `passage-${g.passage_id}`;
  if(g.bank_id) return `bank-${g.bank_id}`;
  if(g.lesson_id != null && g.lesson_id !== '') return String(g.lesson_id);
  return `solo-${(g.questions && g.questions[0] && g.questions[0].id) || 0}`;
}
```

新增：

```javascript
async function approveByPassage(passageId){
  await api(`/api/questions/approve-by-passage?passage_id=${passageId}&d=${todayStr()}`, {method:'POST'});
  await loadReviewQuestions(); render();
}
```

- [ ] **Step 2: 组头下展示材料，组操作加「通过本篇」**

在 `renderQuestionTab` 的 `lessonGroups` 里，`qItems` 之前若 `g.passage && g.passage.content`，插入：

```javascript
      const passageHtml = (g.passage && g.passage.content)
        ? `<div class="passage-preview" style="margin:8px 0 12px">${renderPassageMarkup(g.passage.content)}</div>`
        : '';
```

把 `${qItems}` 换成 `${passageHtml}${qItems}`。

组头操作区（已有 `g.lesson_id` / `g.bank_id` 按钮处）追加：

```javascript
            ${g.passage_id?`<button class="btn-ghost" style="padding:4px 10px" onclick="approveByPassage('${g.passage_id}')">通过本篇</button>`:''}
```

组标题继续用 `g.lesson_title`（后端已填材料标题）。

- [ ] **Step 3: 手动验证**

录入一篇阅读 → 审核台该组展开能看到渲染后的材料（加粗/挖空）和子题 → 「通过本篇」后学生端拉题能看到（Task 11/12）。

- [ ] **Step 4: 提交**

```bash
git add parent-web/app.js
git commit -m "feat(parent-web): show reading passage in review groups"
```

---

### Task 11: Flutter 白名单 tokenizer

**Files:**
- Create: `student-app/lib/features/bank_exercise/passage_markup.dart`
- Test: `student-app/test/features/bank_exercise/passage_markup_test.dart`

- [ ] **Step 1: 写失败测试**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/bank_exercise/passage_markup.dart';

void main() {
  test('tokenize 加粗、音标、挖空', () {
    final tokens = tokenizePassage('**生词** /ˈæpl/ ____');
    final kinds = tokens.map((t) => t.kind).toList();
    expect(kinds, containsAllInOrder(['bold', 'ipa', 'blank']));
    expect(tokens.firstWhere((t) => t.kind == 'bold').text, '生词');
    expect(tokens.firstWhere((t) => t.kind == 'ipa').text, 'ˈæpl');
  });

  test('tokenize 标题行', () {
    final tokens = tokenizePassage('# 标题\n正文');
    expect(tokens.first.kind, 'h1');
    expect(tokens.first.text, '标题');
  });

  test('白名单外当纯文本', () {
    final tokens = tokenizePassage('[link](http://x) and `code`');
    expect(tokens.every((t) => t.kind == 'text' || t.kind == 'br'), isTrue);
    expect(tokens.map((t) => t.text).join(), contains('[link](http://x)'));
  });

  test('下划线标签', () {
    final tokens = tokenizePassage('<u>line</u>');
    expect(tokens.any((t) => t.kind == 'underline' && t.text == 'line'), isTrue);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd student-app && flutter test test/features/bank_exercise/passage_markup_test.dart`

Expected: FAIL（库不存在）

- [ ] **Step 3: 实现 tokenizer + widget**

```dart
import 'package:flutter/material.dart';

class PassageToken {
  const PassageToken(this.kind, this.text);
  final String kind; // text, bold, italic, underline, ipa, blank, h1, h2, br
  final String text;
}

final _inline = RegExp(
  r'(\*\*[^*]+\*\*|\*[^*]+\*|<u>[\s\S]*?</u>|/[^/:\n]{1,40}/|____)',
);

List<PassageToken> tokenizePassage(String src) {
  final out = <PassageToken>[];
  final lines = src.replaceAll('\r\n', '\n').split('\n');
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    if (i > 0) out.add(const PassageToken('br', '\n'));
    if (line.startsWith('## ')) {
      out.add(PassageToken('h2', line.substring(3)));
      continue;
    }
    if (line.startsWith('# ')) {
      out.add(PassageToken('h1', line.substring(2)));
      continue;
    }
    _tokenizeInline(line, out);
  }
  return out;
}

void _tokenizeInline(String line, List<PassageToken> out) {
  var start = 0;
  for (final m in _inline.allMatches(line)) {
    if (m.start > start) {
      out.add(PassageToken('text', line.substring(start, m.start)));
    }
    final raw = m.group(0)!;
    if (raw == '____') {
      out.add(const PassageToken('blank', ''));
    } else if (raw.startsWith('**') && raw.endsWith('**')) {
      out.add(PassageToken('bold', raw.substring(2, raw.length - 2)));
    } else if (raw.startsWith('*') && raw.endsWith('*')) {
      out.add(PassageToken('italic', raw.substring(1, raw.length - 1)));
    } else if (raw.startsWith('<u>') && raw.endsWith('</u>')) {
      out.add(PassageToken('underline', raw.substring(3, raw.length - 4)));
    } else if (raw.startsWith('/') && raw.endsWith('/')) {
      out.add(PassageToken('ipa', raw.substring(1, raw.length - 1)));
    } else {
      out.add(PassageToken('text', raw));
    }
    start = m.end;
  }
  if (start < line.length) out.add(PassageToken('text', line.substring(start)));
}

class PassageContentView extends StatelessWidget {
  const PassageContentView({super.key, required this.content, this.title});

  final String content;
  final String? title;

  @override
  Widget build(BuildContext context) {
    final tokens = tokenizePassage(content);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (title != null && title!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(title!, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          ),
        Text.rich(_spans(tokens)),
      ],
    );
  }

  static TextSpan _spans(List<PassageToken> tokens) {
    return TextSpan(
      style: const TextStyle(fontSize: 15, height: 1.7, color: Color(0xFF202723)),
      children: [
        for (final t in tokens) _span(t),
      ],
    );
  }

  static InlineSpan _span(PassageToken t) {
    switch (t.kind) {
      case 'br':
        return const TextSpan(text: '\n');
      case 'h1':
      case 'h2':
        return TextSpan(text: '${t.text}\n', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16));
      case 'bold':
        return TextSpan(text: t.text, style: const TextStyle(fontWeight: FontWeight.w700));
      case 'italic':
        return TextSpan(text: t.text, style: const TextStyle(fontStyle: FontStyle.italic));
      case 'underline':
        return TextSpan(text: t.text, style: const TextStyle(decoration: TextDecoration.underline));
      case 'ipa':
        return TextSpan(
          text: '/${t.text}/',
          style: const TextStyle(fontFamily: 'serif', color: Color(0xFF3158E8), fontSize: 13),
        );
      case 'blank':
        return const WidgetSpan(
          alignment: PlaceholderAlignment.baseline,
          baseline: TextBaseline.alphabetic,
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: 2),
            child: SizedBox(
              width: 48,
              child: DecoratedBox(
                decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Color(0xFF334038)))),
                child: SizedBox(height: 14),
              ),
            ),
          ),
        );
      default:
        return TextSpan(text: t.text);
    }
  }
}
```

> 不引入 `flutter_markdown`：完整 Markdown 会解析链接/列表，违反白名单硬规则。与家长端同一套标记。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd student-app && flutter test test/features/bank_exercise/passage_markup_test.dart`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/bank_exercise/passage_markup.dart student-app/test/features/bank_exercise/passage_markup_test.dart
git commit -m "feat(student-app): whitelist passage markup tokenizer"
```

---

### Task 12: Flutter 题库练习按材料分组展示

**Files:**
- Modify: `student-app/lib/features/bank_exercise/data/bank_models.dart`
- Modify: `student-app/lib/features/bank_exercise/ui/bank_exercise_page.dart`
- Modify: `student-app/test/bank_exercise_test.dart`

- [ ] **Step 1: 写失败测试**

在 `bank_exercise_test.dart` 的 `FakeBankRepository.fetchQuestions` 增加一道带材料的题（可另写一个 Fake，或让默认 fake 返回两道：一道独立、一道带 passage）。新增 widget 测试：

```dart
  testWidgets('阅读理解先展示材料再展示子题', (tester) async {
    final router = GoRouter(
      routes: [GoRoute(path: '/', builder: (_, __) => const BankExercisePage(bankId: 9))],
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [bankRepositoryProvider.overrideWithValue(FakePassageBankRepository())],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pump();
    await tester.pumpAndSettle();
    expect(find.text('小蝌蚪找妈妈'), findsOneWidget);
    expect(find.textContaining('游啊游'), findsWidgets);
    expect(find.textContaining('谁在游'), findsOneWidget);
  });
```

`FakePassageBankRepository`：

```dart
class FakePassageBankRepository implements BankRepository {
  @override
  Future<List<PracticeBank>> listPracticeBanks() async => const [];

  @override
  Future<List<BankQuestion>> fetchQuestions(int bankId, {List<int>? questionIds}) async {
    const p = ReadingPassageInfo(id: 3, title: '小蝌蚪找妈妈', content: '小蝌蚪 **游啊游**。');
    return const [
      BankQuestion(
        id: 2,
        qtype: 'short_answer',
        qtypeCategory: 'subjective',
        question: '谁在游？',
        options: [],
        passageId: 3,
        passage: p,
      ),
    ];
  }

  @override
  Future<BankSubmitResult> submit({required int bankId, required List<Map<String, dynamic>> answers}) async {
    return const BankSubmitResult(score: 1, total: 1, answers: []);
  }
}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd student-app && flutter test test/bank_exercise_test.dart`

Expected: FAIL（`ReadingPassageInfo` / `passageId` 不存在，或页面不渲染材料标题）

- [ ] **Step 3: 实现模型和页面分组**

`bank_models.dart` 增加：

```dart
class ReadingPassageInfo {
  const ReadingPassageInfo({required this.id, required this.title, required this.content, this.subject = ''});
  final int id;
  final String title;
  final String content;
  final String subject;

  factory ReadingPassageInfo.fromJson(Map<String, dynamic> json) => ReadingPassageInfo(
        id: (json['id'] as num?)?.toInt() ?? 0,
        title: '${json['title'] ?? ''}',
        content: '${json['content'] ?? ''}',
        subject: '${json['subject'] ?? ''}',
      );
}
```

`BankQuestion` 构造加可选字段（默认 null，不破坏现有调用）：

```dart
    this.passageId,
    this.passage,
```

```dart
  final int? passageId;
  final ReadingPassageInfo? passage;
```

`fromJson`：

```dart
    ReadingPassageInfo? passage;
    final pRaw = json['passage'];
    if (pRaw is Map) passage = ReadingPassageInfo.fromJson(Map<String, dynamic>.from(pRaw));
    return BankQuestion(
      ...
      passageId: (json['passage_id'] as num?)?.toInt(),
      passage: passage,
    );
```

`bank_exercise_page.dart` 的 `ListView` children 不要直接 `for (var i = 0; i < s.questions.length; i++)` 平铺。先按「首次出现的 passageId」聚成块：

```dart
List<Widget> _buildQuestionBlocks(...) {
  final shown = <int>{};
  final widgets = <Widget>[];
  for (var i = 0; i < questions.length; i++) {
    final q = questions[i];
    final pid = q.passageId;
    if (pid != null && !shown.contains(pid)) {
      shown.add(pid);
      final p = q.passage;
      if (p != null && p.content.isNotEmpty) {
        widgets.add(SectionCard(
          padding: const EdgeInsets.all(16),
          child: PassageContentView(title: p.title, content: p.content),
        ));
        widgets.add(const SizedBox(height: 12));
      }
    }
    widgets.add(_QuestionCard(...现有参数，index: i, question: q...));
    widgets.add(const SizedBox(height: 12));
  }
  return widgets;
}
```

同一 `passageId` 的后续子题不再重复材料卡片。独立题（`passageId == null`）不加材料卡。

import `passage_markup.dart`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd student-app && flutter analyze && flutter test test/bank_exercise_test.dart test/features/bank_exercise/passage_markup_test.dart`

Expected: PASS，analyze 无 error

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/bank_exercise student-app/test/bank_exercise_test.dart student-app/test/features/bank_exercise/passage_markup_test.dart
git commit -m "feat(student-app): show reading passage above bank sub-questions"
```

---

## 自检（写完后自查，无需重跑）

- [x] **Spec 覆盖：**
  - §1.1 `ReadingPassage` → Task 1
  - §1.2 `Question.passage_id` 可空、与 `bank_id` 正交 → Task 1 / 4 / 5
  - §1.3 不新增 qtype → 全计划未改 `question_types.py`
  - §1.4 白名单标记 + 挖空对齐 → Task 3 / 4（400）/ 9 / 11
  - §2 人工录入 → Task 4 / 9；OCR → Task 7 / 8；第三方 → Task 8（`item_to_draft`，学库宝复用）
  - §3 孩子端先材料后子题 + 判分复用 → Task 5 / 12
  - §4 路由/迁移 → Task 2 / 4 / 5
  - §6 单测 + 集成路径（录入→审核→拉题作答）→ Task 4–6、5 的 submit 复用、9–12
- [x] **类型一致：** `QuestionDraft.passage_title/passage_content`、API `passage_id`/`passage` 对象、`FILL_BLANK_QTYPES`、`ReadingPassage.status` 的 pending/published 在各任务间一致。
- [x] **无占位：** 每个代码步骤都有完整代码；前端手动验证步骤写了具体操作。
- [x] **与 spec 的一处刻意偏离：** 学生端不用 `flutter_markdown`，改用与家长端同一套白名单 tokenizer，以满足「白名单外一律当纯文本」。

## 遗留（明确不做）

1. **不收编** 现有 `Quiz`（边读边问 / evidence 校验）与 `services/question_gen.py` / `routers/learning.py` 课文阅读题。
2. **不改判分** `grade_question()` / `grade_subjective_with_ai()`。
3. **无 bank_id 的独立材料**：API 允许 `bank_id=null`；孩子端练习入口仍是卷子（`/api/banks/practice`）。家长录入表单始终挂当前选中卷。
4. **第三方真实阅读题拆篇**：只认常见字段 `passage`/`article`/`material`；不接 tiku.cn/学库宝新 API。字段对不上时仍当独立题。
5. **OCR 挖空不对齐**：导入不 400（识别常不全），留给审核台改；仅家长 `POST /api/passages` 与家长表单硬拦截。
6. **材料正文不 sanitize 入库**：写错标记当纯文本渲染，不报错、不改写存储。
