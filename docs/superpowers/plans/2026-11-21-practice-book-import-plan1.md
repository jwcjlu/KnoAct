# 计划一：练习册 PDF 导入流水线 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 家长上传一本扫描版练习册 PDF 后，后端后台 OCR 拆出「课时 → 题目 → 答案」，把**答案已对齐**的题发布进题库，未对齐的进入「待补答案」清单；家长端可看进度、补答案、重试失败页。

**Architecture:** 新增两张表（导入任务 / 逐题作答留待计划二用）+ 给 `Question` 加 4 个可索引列；后台任务用可注入的 `run_import_job(job_id)`，每页新开 `SessionLocal()`；OCR 走 `_render_page_png(dpi=150)` + `services.ai.ocr_image()`，**不复用**带缓存的 `_ocr_page`、**不复用** `/api/pdf/upload`（会触发整本拆课）。

**Tech Stack:** FastAPI + SQLAlchemy（SQLite 本地 / MySQL 生产）、PyMuPDF、pytest；家长端 `parent-web`（原生 JS 单文件）。

**规格：** `docs/superpowers/specs/2026-11-20-practice-book-import-design.md`

---

## 写代码前必须知道的 8 件事

1. **`_persist_drafts` 不写 `user_id`，题目会被启动迁移删光。**
   `migrate_grade_buckets.migrate()` 末尾有
   `db.query(Question).filter(Question.user_id.is_(None)).delete(...)`，
   `main.py` **每次启动**都跑它。必须先修这个（Task 2），否则导入的题下次重启就没了。

2. **`_persist_drafts` 末尾会改 `bank.source`**：
   `if ids and bank.source == "manual": bank.source = "third_party"`（`bank.py:153`）。
   所以 `practice_pdf` 必须在 persist **之后**设置。

3. **`schema_sync` 不补索引**（文件头明写）。存量库要新增索引只能写迁移脚本。

4. **`CATEGORY_OF_QTYPE` 没有 `objective`**，只有
   `choice/blank/match/subjective`。`qtype_category` 一律由它派生，不要手填。

5. **`calculate` 的 category 是 `blank`**，题库练习页会把竖式渲染成填空框。
   所以练习册卷必须从 `GET /api/banks/practice` 排除。

6. **`pdf_split._ocr_page` 会把失败结果（空串）缓存住**，`/retry` 永远拿到同一个失败。
   必须直接用 `_render_page_png(pdf_path, i, dpi=150)` + `ai.ocr_image`。

7. **`resolve(db,'llm')` 返回的是 `Resolved` dataclass**，字段是 `provider`（字符串）、
   `api_key`、`base_url`，**没有 `.name`**。写成 `.provider.name` 会 AttributeError。

8. **测试库每个用例前后 `drop_all`/`create_all`**（`conftest.py` 的 autouse `setup_db`），
   所以新表/新列在测试里自动就有；但**存量库不会**，这就是 Task 1 要写迁移的原因。

---

## 文件结构

| 文件 | 职责 |
| --- | --- |
| `backend/app/models.py` | `Question` 加 4 列 + 索引；新增 `PracticeImportJob`、`PracticeAttempt` |
| `backend/app/core/source_adapter.py` | `QuestionDraft` 加 `lesson_no`/`lesson_title`/`question_no`/`source_document_id` |
| `backend/app/routers/bank.py` | `_persist_drafts` 透传新字段 + **`user_id`**；`list_practice_banks` 排除练习册 |
| `backend/app/migrate_practice_import.py` | 存量库 `ALTER TABLE` × 3 + `CREATE INDEX`（各自 try/except） |
| `backend/app/services/practice_import.py` | 页码解析、课时/题号解析、答案对齐、任务编排、`run_import_job` |
| `backend/app/routers/practice_import.py` | 上传 / 进度 / 重试 / 待补 / 补答案 / 课时列表 / 新建练习册卷 |
| `backend/app/routers/pdf.py` | `content_kind="practice"` 默认从教材列表排除 |
| `backend/app/main.py` | include router；启动跑迁移；清理卡住的 job |
| `parent-web/app.js` / `index.html` | 「练习册导入」子视图 |
| `backend/tests/test_practice_import.py` | 新增 |

---

## Task 1: 数据模型与迁移

**Files:**
- Modify: `backend/app/models.py`（`Question` 内 + 文件末尾）
- Create: `backend/app/migrate_practice_import.py`
- Test: `backend/tests/test_practice_import.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_practice_import.py`：

```python
from app import models  # noqa: F401  确保表已注册


def test_question_has_practice_columns(db):
    from app.models import Question

    cols = {c.name for c in Question.__table__.columns}
    for name in ("lesson_no", "lesson_title", "question_no", "source_document_id"):
        assert name in cols, f"缺少列 {name}"


def test_practice_tables_exist(db):
    from app.models import PracticeAttempt, PracticeImportJob

    assert PracticeImportJob.__tablename__ == "practice_import_jobs"
    assert PracticeAttempt.__tablename__ == "practice_attempts"


def test_question_index_on_bank_lesson(db):
    from app.models import Question

    names = {i.name for i in Question.__table__.indexes}
    assert "ix_questions_bank_lesson" in names
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v
```

Expected: FAIL（`缺少列 lesson_no`）

- [ ] **Step 3: 给 `Question` 加列与索引**

在 `backend/app/models.py` 的 `class Question` 内，`task_type` 那行之后追加：

```python
    # 练习册导入用：课时号/课时标题/题号（可索引，便于按课时取题）
    lesson_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lesson_title: Mapped[str | None] = mapped_column(String(64), nullable=True)
    question_no: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pdf_documents.id", ondelete="SET NULL"), nullable=True)
```

并在 `__tablename__` 下方加 `__table_args__`（`Question` 原本没有）：

```python
    __table_args__ = (
        Index("ix_questions_bank_lesson", "bank_id", "lesson_no"),
    )
```

- [ ] **Step 4: 加两张新表**

在 `backend/app/models.py` **文件末尾**追加：

```python
class PracticeImportJob(Base):
    """练习册 PDF 导入任务：进度、页码范围、识别/对齐/发布计数。"""
    __tablename__ = "practice_import_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("pdf_documents.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending | rendering | ocr | aligning | done | failed
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    done_pages: Mapped[int] = mapped_column(Integer, default=0)
    question_start_page: Mapped[int] = mapped_column(Integer, default=1)
    question_end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer_start_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer_end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    aligned_count: Mapped[int] = mapped_column(Integer, default=0)
    published_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_pages: Mapped[str] = mapped_column(LongText, default="[]")
    error: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PracticeAttempt(Base):
    """逐题作答（计划二用，计划一先建表，避免二次迁移）。"""
    __tablename__ = "practice_attempts"
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", "date", name="uq_practice_attempt"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"))
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"))
    date: Mapped[date] = mapped_column(Date)
    lesson_no: Mapped[int] = mapped_column(Integer, default=0)
    student_answer: Mapped[str] = mapped_column(LongText, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    photo_path: Mapped[str] = mapped_column(String(512), default="")
    ai_status: Mapped[str] = mapped_column(String(16), default="")
    ai_final_answer: Mapped[str] = mapped_column(String(64), default="")
    ai_steps_plausible: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_reason: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

> `Index` / `UniqueConstraint` / `Boolean` / `Date` / `LongText` 在 `models.py` 顶部已 import，无需新增。

- [ ] **Step 5: 写迁移脚本**

新建 `backend/app/migrate_practice_import.py`：

```python
"""存量库补列与索引（练习册导入用）。

`schema_sync` 只补列不补索引，`create_all` 又不改老表，所以这里显式做。
每步独立 try/except，保证幂等（列/索引已存在时跳过）。
"""
import logging

from sqlalchemy import text

from .database import engine

_log = logging.getLogger("uvicorn.error")

_STATEMENTS = [
    ("lesson_no", "ALTER TABLE questions ADD COLUMN lesson_no INTEGER"),
    ("lesson_title", "ALTER TABLE questions ADD COLUMN lesson_title VARCHAR(64)"),
    ("question_no", "ALTER TABLE questions ADD COLUMN question_no VARCHAR(16)"),
    ("ix_questions_bank_lesson",
     "CREATE INDEX ix_questions_bank_lesson ON questions (bank_id, lesson_no)"),
]


def migrate() -> None:
    for name, sql in _STATEMENTS:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception as exc:
            # 已存在（SQLite/MySQL 报错文案不同）或权限不足：记一条日志继续
            _log.info("迁移跳过 %s: %s", name, str(exc)[:120])


if __name__ == "__main__":
    migrate()
    print("练习册导入迁移完成")
```

- [ ] **Step 6: 在启动时跑迁移**

在 `backend/app/main.py` 的 `_ensure_db_tables()` 里，紧跟 `sync_schema(...)` 那段之后追加：

```python
        try:
            from .migrate_practice_import import migrate as _migrate_practice_import
            _migrate_practice_import()
        except Exception as exc:
            _log.warning("练习册导入迁移失败: %s", exc)
```

- [ ] **Step 7: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v
```

Expected: PASS（3 passed）

- [ ] **Step 8: 手工验证迁移幂等**

```bash
cd backend && python -c "
from app.migrate_practice_import import migrate
migrate(); migrate()   # 连跑两次，第二次全部跳过
print('idempotent ok')
"
```

Expected: `idempotent ok`（第二次没有任何异常抛出）

- [ ] **Step 9: 提交**

```bash
git add backend/app/models.py backend/app/migrate_practice_import.py backend/app/main.py backend/tests/test_practice_import.py
git commit -m "feat(practice-import): Question 加课时列与索引 + 导入任务/逐题作答表 + 存量库迁移"
```

---

## Task 2: 修 `_persist_drafts` 不写 `user_id`（防清库）+ 透传新字段

**Files:**
- Modify: `backend/app/core/source_adapter.py`
- Modify: `backend/app/routers/bank.py:104-158`
- Test: `backend/tests/test_practice_import.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_practice_import.py` 追加：

```python
def test_persist_drafts_sets_user_id(db):
    """不写 user_id 的题会被 migrate_grade_buckets 在下次启动时删光。"""
    from app.models import Question, QuestionBank
    from conftest import make_account
    from app.core.source_adapter import QuestionDraft
    from app.routers.bank import _persist_drafts

    parent = make_account(db, "pi_parent", "parent")
    bank = QuestionBank(user_id=parent.id, title="测试卷", subject="数学", source="manual")
    db.add(bank)
    db.commit()

    ids = _persist_drafts(db, bank, [
        QuestionDraft(qtype="oral", question="8.9+4.5=", answer="13.4"),
    ], "test")
    db.commit()

    row = db.get(Question, ids[0])
    assert row.user_id == parent.id, "user_id 必须是卷主，否则启动迁移会删题"


def test_persist_drafts_survives_startup_migration(db):
    """回归：创建题 → 跑启动迁移 → 题还在。"""
    from app.models import Question, QuestionBank
    from conftest import make_account
    from app.core.source_adapter import QuestionDraft
    from app.routers.bank import _persist_drafts
    from app.migrate_grade_buckets import migrate

    parent = make_account(db, "pi_parent2", "parent")
    bank = QuestionBank(user_id=parent.id, title="卷2", subject="数学", source="manual")
    db.add(bank)
    db.commit()
    _persist_drafts(db, bank, [
        QuestionDraft(qtype="oral", question="1+1=", answer="2"),
    ], "test")
    db.commit()
    before = db.query(Question).count()

    migrate(db)  # 这是服务启动时跑的迁移

    assert db.query(Question).count() == before, "启动迁移把练习册题目删掉了"


def test_persist_drafts_passes_lesson_fields(db):
    from app.models import Question, QuestionBank
    from conftest import make_account
    from app.core.source_adapter import QuestionDraft
    from app.routers.bank import _persist_drafts

    parent = make_account(db, "pi_parent3", "parent")
    bank = QuestionBank(user_id=parent.id, title="卷3", subject="数学", source="manual")
    db.add(bank)
    db.commit()

    d = QuestionDraft(qtype="oral", question="1+1=", answer="2")
    d.lesson_no = 3
    d.lesson_title = "小数乘小数"
    d.question_no = "1"
    d.source_document_id = 99
    ids = _persist_drafts(db, bank, [d], "practice_pdf")
    db.commit()

    row = db.get(Question, ids[0])
    assert row.lesson_no == 3
    assert row.lesson_title == "小数乘小数"
    assert row.question_no == "1"
    assert row.source_document_id == 99
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v -k "user_id or survive or lesson_fields"
```

Expected: FAIL（`row.user_id` 为 None / lesson_no 为 None）

- [ ] **Step 3: 给 `QuestionDraft` 加字段**

`backend/app/core/source_adapter.py` 的 `QuestionDraft` 内追加：

```python
    lesson_no: int | None = None
    lesson_title: str = ""
    question_no: str = ""
    source_document_id: int | None = None
```

- [ ] **Step 4: 改 `_persist_drafts`**

在 `backend/app/routers/bank.py` 的 `Question(...)` 构造里，`passage_id=passage_id,` 之后追加：

```python
            user_id=bank.user_id,   # 必须：否则启动迁移会删掉无主题目
            lesson_no=d.lesson_no,
            lesson_title=(d.lesson_title or None),
            question_no=(d.question_no or None),
            source_document_id=d.source_document_id,
```

- [ ] **Step 5: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v
```

Expected: PASS（6 passed）

- [ ] **Step 6: 跑既有题库测试确认没破坏**

```bash
cd backend && python -m pytest tests/test_bank.py tests/test_ocr_import.py -q
```

Expected: 全绿（若原有用例断言 `user_id is None`，需同步改为 `bank.user_id`）

- [ ] **Step 7: 提交**

```bash
git add backend/app/core/source_adapter.py backend/app/routers/bank.py backend/tests/test_practice_import.py
git commit -m "fix(bank): _persist_drafts 写入 user_id（否则启动迁移删题）+ 透传课时字段"
```

---

## Task 3: 课时/题号解析与答案对齐（纯函数）

**Files:**
- Create: `backend/app/services/practice_import.py`（先放纯函数）
- Test: `backend/tests/test_practice_import.py`（追加）

- [ ] **Step 1: 写失败测试**

追加：

```python
def test_parse_lesson_page_extracts_header_and_items():
    from app.services.practice_import import parse_lesson_page

    text = """第3课时 小数乘小数
1. 8.9 + 4.5 =        2. 1000 - 550 =
3. 0.76 - 0.39 =      4. 3.4 - 1.24 =
"""
    out = parse_lesson_page(text)
    assert out["lesson_no"] == 3
    assert out["lesson_title"] == "小数乘小数"
    assert [i["question_no"] for i in out["items"]] == ["1", "2", "3", "4"]
    assert "8.9" in out["items"][0]["question"]
    # 小数不能被误判成题号
    assert "8.9" in out["items"][0]["question"]
    assert "0.76" in out["items"][2]["question"]


def test_parse_lesson_page_does_not_split_on_decimals():
    from app.services.practice_import import parse_lesson_page

    out = parse_lesson_page("第1课时 口算\n1. 计算 3.25 + 1.8 =")
    assert len(out["items"]) == 1
    assert "3.25" in out["items"][0]["question"]


def test_parse_lesson_page_handles_fullwidth_and_no_title():
    from app.services.practice_import import parse_lesson_page

    out = parse_lesson_page("第 12 课时 练习课\n（1）0.6×0.4＝")
    assert out["lesson_no"] == 12
    assert out["lesson_title"] == "练习课"
    assert out["items"][0]["question_no"] == "1"


def test_parse_lesson_page_returns_empty_when_no_header():
    from app.services.practice_import import parse_lesson_page

    out = parse_lesson_page("随便一段没有课时标题的文字")
    assert out["lesson_no"] is None
    assert out["items"] == []


def test_align_answers_matches_by_lesson_and_number():
    from app.services.practice_import import align_answers

    questions = [
        {"lesson_no": 3, "question_no": "1", "question": "8.9+4.5="},
        {"lesson_no": 3, "question_no": "2", "question": "1000-550="},
    ]
    answers = [
        {"lesson_no": 3, "question_no": "1", "answer": "13.4"},
        # 缺 question_no 2
    ]
    aligned, missing = align_answers(questions, answers)
    assert aligned[0]["answer"] == "13.4"
    assert [m["question_no"] for m in missing] == ["2"]


def test_split_blanks_by_count():
    from app.services.practice_import import split_blanks

    assert split_blanks("0.24, 1.16", 2) == ["0.24", "1.16"]
    assert split_blanks("13.4", 1) == ["13.4"]
    # 数量不符返回 None（调用方视为未对齐）
    assert split_blanks("1, 2, 3", 2) is None
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v -k "parse or align or split"
```

Expected: FAIL（`ModuleNotFoundError: app.services.practice_import`）

- [ ] **Step 3: 实现解析与对齐**

新建 `backend/app/services/practice_import.py`：

```python
"""练习册 PDF 导入：课时/题号解析、答案对齐、后台任务编排。

设计要点见 docs/superpowers/specs/2026-11-20-practice-book-import-design.md
"""
import json
import os
import re

# 「第3课时 小数乘小数」/「第 12 课时 练习课」
_LESSON_RE = re.compile(r"第\s*(\d+)\s*课时\s*([^\n]*)")

# 题号只在「行首」或「行内空白 + 数字紧跟 . / 、/ (n)」时才算，
# 且数字后面不能跟数字（否则 8.9 / 3.32 这类小数会被当成题号）。
_ITEM_RE = re.compile(
    r"(?:(?<=^)|(?<=[\s\u3000]))"          # 行首或空白之后
    r"(?:\((\d{1,2})\)|（(\d{1,2})）|(\d{1,2})[.、．](?!\d))"
)


def parse_lesson_page(text: str) -> dict:
    """从一页 OCR 文本解析出课时号、标题、题目列表。

    返回 {"lesson_no": int|None, "lesson_title": str, "items": [{"question_no","question"}]}
    没识别到课时标题时返回空 items（由调用方记失败页）。
    """
    text = (text or "").replace("\r", "")
    m = _LESSON_RE.search(text)
    if not m:
        return {"lesson_no": None, "lesson_title": "", "items": []}

    lesson_no = int(m.group(1))
    lesson_title = (m.group(2) or "").strip().split("\n")[0].strip()
    body = text[m.end():]

    items: list[dict] = []
    marks = list(_ITEM_RE.finditer(body))
    for i, mk in enumerate(marks):
        num = mk.group(1) or mk.group(2) or mk.group(3)
        start = mk.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        stem = body[start:end].strip()
        if not stem:
            continue
        items.append({"question_no": str(num), "question": stem})
    return {"lesson_no": lesson_no, "lesson_title": lesson_title, "items": items}


def split_blanks(answer_text: str, count: int) -> list[str] | None:
    """把答案文本按空位数量切开；数量不匹配返回 None（视为未对齐）。"""
    raw = (answer_text or "").strip()
    if not raw:
        return None
    parts = [p.strip() for p in re.split(r"[,，;；、\s]+", raw) if p.strip()]
    if len(parts) != count:
        return None
    return parts


def align_answers(questions: list[dict], answers: list[dict]) -> tuple[list[dict], list[dict]]:
    """按 (lesson_no, question_no) 对齐。返回 (已对齐, 未对齐)。

    已对齐的题会带上 answer / analysis；未对齐的原样返回（answer 留空）。
    """
    index: dict[tuple, dict] = {}
    for a in answers:
        key = (a.get("lesson_no"), str(a.get("question_no")))
        if key not in index:
            index[key] = a

    aligned: list[dict] = []
    missing: list[dict] = []
    for q in questions:
        key = (q.get("lesson_no"), str(q.get("question_no")))
        hit = index.get(key)
        if hit and (hit.get("answer") or "").strip():
            aligned.append({**q, "answer": hit["answer"], "analysis": hit.get("analysis", "")})
        else:
            missing.append(q)
    return aligned, missing
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v -k "parse or align or split"
```

Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/practice_import.py backend/tests/test_practice_import.py
git commit -m "feat(practice-import): 课时/题号解析、答案对齐、多空拆分"
```

---

## Task 4: 题型映射与 Draft 构造

**Files:**
- Modify: `backend/app/services/practice_import.py`（追加）
- Test: `backend/tests/test_practice_import.py`（追加）

- [ ] **Step 1: 写失败测试**

追加：

```python
def test_kind_maps_to_qtype():
    from app.services.practice_import import QTYPE_OF_KIND

    assert QTYPE_OF_KIND["oral"] == "oral"
    assert QTYPE_OF_KIND["fill"] == "fill_blank"
    assert QTYPE_OF_KIND["vertical"] == "calculation"
    assert QTYPE_OF_KIND["step"] == "calculation"
    assert QTYPE_OF_KIND["app"] == "application"


def test_qtype_category_is_derived_not_hardcoded():
    """category 必须由 CATEGORY_OF_QTYPE 派生，不能出现 objective。"""
    from app.core.question_types import CATEGORY_OF_QTYPE
    from app.services.practice_import import QTYPE_OF_KIND

    for qtype in QTYPE_OF_KIND.values():
        assert qtype in CATEGORY_OF_QTYPE
    assert "objective" not in set(CATEGORY_OF_QTYPE.values())


def test_build_drafts_sets_lesson_and_blank_json():
    from app.services.practice_import import build_drafts

    aligned = [
        {"lesson_no": 3, "lesson_title": "小数乘小数", "question_no": "1",
         "question": "8.9+4.5=", "answer": "13.4", "kind": "oral", "page": 11},
        {"lesson_no": 3, "lesson_title": "小数乘小数", "question_no": "2",
         "question": "（  ）+（  ）=", "answer": "1, 2", "kind": "fill", "page": 11},
    ]
    drafts = build_drafts(aligned, document_id=7, blanks_of=lambda q: 2)
    assert drafts[0].qtype == "oral"
    assert drafts[0].lesson_no == 3
    assert drafts[0].source_document_id == 7
    assert drafts[1].qtype == "fill_blank"
    assert drafts[1].answer_json["blanks"] == ["1", "2"]
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v -k "kind or category or build_drafts"
```

Expected: FAIL（`ImportError: cannot import name 'QTYPE_OF_KIND'`）

- [ ] **Step 3: 实现映射与构造**

在 `backend/app/services/practice_import.py` **追加**：

```python
from ..core.source_adapter import QuestionDraft

# OCR 解析出的 kind → 题库 qtype。
# category 由 CATEGORY_OF_QTYPE 派生（core/question_types.py），绝不手填。
QTYPE_OF_KIND: dict[str, str] = {
    "oral": "oral",          # 口算：单值
    "fill": "fill_blank",    # 多空填空：answer_json.blanks
    "vertical": "calculation",  # 竖式：拍照
    "step": "calculation",      # 脱式/简算：拍照
    "app": "application",       # 应用题：拍照
}


def build_drafts(
    aligned: list[dict],
    *,
    document_id: int,
    blanks_of=lambda q: 0,
) -> list[QuestionDraft]:
    """已对齐的题 → QuestionDraft（供 bank._persist_drafts 落库）。

    `blanks_of(q)` 返回该题的空位数（fill 类用）；数量与答案切分不符时降级为 oral。
    """
    out: list[QuestionDraft] = []
    for q in aligned:
        kind = (q.get("kind") or "oral").strip()
        qtype = QTYPE_OF_KIND.get(kind, "oral")
        d = QuestionDraft(qtype=qtype, question=q.get("question") or "",
                          answer=(q.get("answer") or "").strip(),
                          analysis=q.get("analysis") or "")
        d.lesson_no = q.get("lesson_no")
        d.lesson_title = q.get("lesson_title") or ""
        d.question_no = str(q.get("question_no") or "")
        d.source_document_id = document_id
        d.tags = {"source": "practice_pdf", "page": q.get("page") or 0}

        if qtype == "fill_blank":
            n = int(blanks_of(q) or 0)
            blanks = split_blanks(d.answer, n) if n else None
            if blanks:
                d.answer_json = {"blanks": blanks}
            else:
                # 空位数与答案不符：降级为 oral，避免永远判错
                d.qtype = "oral"
        out.append(d)
    return out
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v -k "kind or category or build_drafts"
```

Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/practice_import.py backend/tests/test_practice_import.py
git commit -m "feat(practice-import): kind→qtype 映射与 Draft 构造（category 由 CATEGORY_OF_QTYPE 派生）"
```

---

## Task 5: 发布（只发布已对齐题）

**Files:**
- Modify: `backend/app/services/practice_import.py`（追加）
- Test: `backend/tests/test_practice_import.py`（追加）

- [ ] **Step 1: 写失败测试**

追加：

```python
def test_publish_only_aligned(db):
    """未对齐的题保持 pending，不能进孩子端。"""
    from app.models import Question, QuestionBank
    from conftest import make_account
    from app.services.practice_import import publish_aligned

    parent = make_account(db, "pi_pub", "parent")
    bank = QuestionBank(user_id=parent.id, title="卷", subject="数学")
    db.add(bank)
    db.commit()
    q1 = Question(user_id=parent.id, bank_id=bank.id, qtype="oral",
                  question="a", answer="1", status="pending")
    q2 = Question(user_id=parent.id, bank_id=bank.id, qtype="oral",
                  question="b", answer="", status="pending")
    db.add_all([q1, q2])
    db.commit()

    n = publish_aligned(db, bank.id)
    db.commit()

    assert n == 1
    assert db.get(Question, q1.id).status == "published"
    assert db.get(Question, q2.id).status == "pending"


def test_publish_skips_fill_blank_without_blanks(db):
    from app.models import Question, QuestionBank
    from conftest import make_account
    from app.services.practice_import import publish_aligned

    parent = make_account(db, "pi_pub2", "parent")
    bank = QuestionBank(user_id=parent.id, title="卷2", subject="数学")
    db.add(bank)
    db.commit()
    q = Question(user_id=parent.id, bank_id=bank.id, qtype="fill_blank",
                 question="__ + __ =", answer="1, 2", answer_json="{}",
                 status="pending")
    db.add(q)
    db.commit()

    assert publish_aligned(db, bank.id) == 0
    assert db.get(Question, q.id).status == "pending"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v -k publish
```

Expected: FAIL（`ImportError: publish_aligned`）

- [ ] **Step 3: 实现**

在 `backend/app/services/practice_import.py` 追加：

```python
def _is_aligned(q) -> bool:
    """已对齐 = 有答案；fill_blank/cloze 还要求 blanks 非空。"""
    if not (q.answer or "").strip():
        return False
    if q.qtype in ("fill_blank", "cloze"):
        try:
            data = json.loads(q.answer_json or "{}")
        except (ValueError, TypeError):
            return False
        return bool(data.get("blanks"))
    return True


def publish_aligned(db, bank_id: int) -> int:
    """把该卷里「已对齐答案」且仍 pending 的题置 published，返回条数。"""
    from ..models import Question

    rows = (db.query(Question)
            .filter(Question.bank_id == bank_id, Question.status == "pending")
            .all())
    ids = [q.id for q in rows if _is_aligned(q)]
    if not ids:
        return 0
    db.query(Question).filter(Question.id.in_(ids)).update(
        {"status": "published"}, synchronize_session=False)
    return len(ids)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v -k publish
```

Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/practice_import.py backend/tests/test_practice_import.py
git commit -m "feat(practice-import): 只发布答案已对齐的题"
```

---

## Task 6: 后台任务 `run_import_job`

**Files:**
- Modify: `backend/app/services/practice_import.py`（追加）
- Test: `backend/tests/test_practice_import.py`（追加）

- [ ] **Step 1: 写失败测试**

追加（全部 mock 掉 OCR，不真跑）：

```python
def _seed_job(db, parent, bank, doc, **kw):
    from app.models import PracticeImportJob
    job = PracticeImportJob(
        user_id=parent.id, bank_id=bank.id, document_id=doc.id,
        total_pages=kw.get("total_pages", 4),
        question_start_page=1, question_end_page=kw.get("q_end", 2),
        answer_start_page=kw.get("a_start", 3), answer_end_page=kw.get("a_end", 4),
    )
    db.add(job)
    db.commit()
    return job


def test_run_import_job_publishes_aligned_and_records_failures(db, monkeypatch):
    from app.models import Question, QuestionBank, PdfDocument, PracticeImportJob
    from conftest import make_account
    from app.services import practice_import as pi

    parent = make_account(db, "pi_job", "parent")
    bank = QuestionBank(user_id=parent.id, title="卷", subject="数学")
    doc = PdfDocument(filename="b.pdf", subject="数学", storage_path="uploads/x.pdf",
                      content_kind="practice")
    db.add_all([bank, doc])
    db.commit()
    job = _seed_job(db, parent, bank, doc)

    # 第 1 页有课时 + 两道题；第 2 页 OCR 返回空（失败页）
    pages = {
        1: "第3课时 小数乘小数\n1. 8.9+4.5=\n2. 1000-550=",
        2: "",
        3: "第3课时 小数乘小数\n1. 13.4\n2. 450",
        4: "",
    }

    monkeypatch.setattr(pi, "_render_page_png", lambda p, i, dpi=150: b"png")
    monkeypatch.setattr(pi, "_ocr_text", lambda path, idx, db_: pages.get(idx + 1, ""))

    pi.run_import_job(job.id)

    fresh = db.get(PracticeImportJob, job.id)
    db.refresh(fresh)
    assert fresh.status == "failed"  # 有失败页 → 整体标记 failed 但已发布的题保留
    assert json.loads(fresh.failed_pages) == [2, 4]
    published = db.query(Question).filter_by(bank_id=bank.id, status="published").count()
    assert published == 2
    fresh_bank = db.get(QuestionBank, bank.id)
    assert fresh_bank.source == "practice_pdf"


def test_run_import_job_all_ok_marks_done(db, monkeypatch):
    from app.models import QuestionBank, PdfDocument, PracticeImportJob
    from conftest import make_account
    from app.services import practice_import as pi

    parent = make_account(db, "pi_job2", "parent")
    bank = QuestionBank(user_id=parent.id, title="卷2", subject="数学")
    doc = PdfDocument(filename="c.pdf", subject="数学", storage_path="uploads/y.pdf",
                      content_kind="practice")
    db.add_all([bank, doc])
    db.commit()
    job = _seed_job(db, parent, bank, doc, total_pages=2, q_end=1, a_start=2, a_end=2)

    pages = {
        1: "第1课时 口算\n1. 1+1=",
        2: "第1课时 口算\n1. 2",
    }
    monkeypatch.setattr(pi, "_render_page_png", lambda p, i, dpi=150: b"png")
    monkeypatch.setattr(pi, "_ocr_text", lambda path, idx, db_: pages.get(idx + 1, ""))

    pi.run_import_job(job.id)

    row = db.get(PracticeImportJob, job.id)
    db.refresh(row)
    assert row.status == "done"
    assert row.published_count == 1
    assert row.question_count == 1
```

> 第二个用例里 `answered_count` 不存在时用 `hasattr` 兜底，避免误写。

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v -k run_import_job
```

Expected: FAIL（`AttributeError: module ... has no attribute 'run_import_job'`）

- [ ] **Step 3: 实现任务编排**

在 `backend/app/services/practice_import.py` 追加：

```python
def _ocr_text(pdf_path: str, page_index: int, db) -> str:
    """OCR 单页。**不用** pdf_split._ocr_page（它会缓存失败结果，导致 retry 无效）。"""
    from .ai import ocr_image
    from .pdf_split import _render_page_png

    png = _render_page_png(pdf_path, page_index, dpi=150)
    try:
        return (ocr_image(db, png, instruction=_OCR_INSTRUCTION) or "").strip()
    except Exception:
        return ""


_OCR_INSTRUCTION = (
    "识别这一页练习册的全部文字，保留「第N课时 标题」与题号（1. 2. (1)），"
    "题目与答案都要原样输出，不要解释、不要省略。"
)


def _parse_pages(db, pdf_path: str, pages: list[int]) -> tuple[list[dict], list[int]]:
    """OCR 并解析指定页码（1-based）。返回 (items, 失败页列表)。"""
    items: list[dict] = []
    failed: list[int] = []
    for pno in pages:
        text = _ocr_text(pdf_path, pno - 1, db)
        parsed = parse_lesson_page(text)
        if not parsed["items"]:
            failed.append(pno)
            continue
        for it in parsed["items"]:
            items.append({
                **it,
                "lesson_no": parsed["lesson_no"],
                "lesson_title": parsed["lesson_title"],
                "page": pno,
            })
    return items, failed


def run_import_job(job_id: int, retry_pages: list[int] | None = None) -> None:
    """后台执行导入。`retry_pages` 非空时只重跑这些页。

    每阶段新开 Session，避免请求级 session 失效（BackgroundTasks 里请求已结束）。
    """
    from ..database import SessionLocal
    from ..models import PdfDocument, PracticeImportJob, QuestionBank
    from ..routers.bank import _persist_drafts

    db = SessionLocal()
    try:
        job = db.get(PracticeImportJob, job_id)
        if job is None:
            return
        doc = db.get(PdfDocument, job.document_id)
        bank = db.get(QuestionBank, job.bank_id)
        if doc is None or bank is None:
            job.status = "failed"
            job.error = "文档或题库卷不存在"
            db.commit()
            return

        job.status = "ocr"
        db.commit()

        q_start = job.question_start_page or 1
        q_end = job.question_end_page or (job.answer_start_page or 1) - 1
        a_start = job.answer_start_page or 1
        a_end = job.answer_end_page or a_start

        if retry_pages:
            # 只重跑指定页（已知每页属于题面还是答案）
            q_pages = [p for p in retry_pages if q_start <= p <= q_end]
            a_pages = [p for p in retry_pages if a_start <= p <= a_end]
            q_items, q_failed = _parse_pages(db, doc.storage_path, q_pages)
            a_items, a_failed = _parse_pages(db, doc.storage_path, a_pages)
        else:
            q_items, q_failed = _parse_pages(
                db, doc.storage_path, list(range(q_start, q_end + 1)))
            a_items, a_failed = _parse_pages(
                db, doc.storage_path, list(range(a_start, a_end + 1)))

        job.status = "aligning"
        job.question_count = len(q_items)
        db.commit()

        aligned, missing = align_answers(q_items, a_items)
        job.aligned_count = len(aligned)

        drafts = build_drafts(aligned, document_id=job.document_id)
        ids = _persist_drafts(db, bank, drafts, "practice_pdf")
        # 必须在 persist 之后设置：_persist_drafts 会把 manual 改成 third_party
        bank.source = "practice_pdf"
        db.commit()

        published = publish_aligned(db, bank.id)
        job.published_count = published

        failed = sorted(q_failed + a_failed)
        job.failed_pages = json.dumps(failed)
        job.done_pages = max(0, (a_end - q_start + 1) - len(failed))
        job.status = "failed" if failed else "done"
        job.error = f"{len(failed)} 页识别失败，可重试" if failed else ""
        db.commit()
    except Exception as exc:  # noqa: BLE001
        try:
            job = db.get(PracticeImportJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)[:480]
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v -k run_import_job
```

Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/practice_import.py backend/tests/test_practice_import.py
git commit -m "feat(practice-import): run_import_job 后台任务（逐页 OCR → 对齐 → 落库 → 发布）"
```

---

## Task 7: 导入接口（上传 / 进度 / 重试 / 待补 / 补答案 / 课时列表）

**Files:**
- Create: `backend/app/routers/practice_import.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_practice_import.py`（追加）

- [ ] **Step 1: 写失败测试**

追加：

```python
def _client_router():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.practice_import import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_create_practice_book_bank(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child

    s = SessionLocal()
    _p, _c, parent_h, _ch = parent_child(s, "pib")
    s.close()
    client = _client_router()
    r = client.post("/api/banks/practice-book", headers=parent_h,
                    json={"title": "RJ五上", "subject": "数学", "grade": 5})
    assert r.status_code == 200
    assert r.json()["id"] > 0


def test_import_rejects_without_answer_pages(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import QuestionBank

    s = SessionLocal()
    p, _c, parent_h, _ch = parent_child(s, "pib2")
    bank = QuestionBank(user_id=p.id, title="卷", subject="数学", source="practice_pdf")
    s.add(bank)
    s.commit()
    bank_id = bank.id
    s.close()

    client = _client_router()
    r = client.post(f"/api/banks/{bank_id}/import-practice-pdf", headers=parent_h,
                    files={"file": ("a.pdf", b"%PDF-1.4 fake", "application/pdf")},
                    data={"answer_start_page": "", "answer_end_page": ""})
    assert r.status_code == 400
    assert "答案页" in r.json()["detail"]


def test_import_rejects_without_vision_model(setup_db, monkeypatch):
    """fake provider → 400，任务不启动。"""
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import QuestionBank
    from app.routers import practice_import as pi

    class FakeResolved:
        provider = "fake"
        api_key = ""
        base_url = ""

    # 直接替换 router 模块里解析出来的 _vision_ready，避开 resolve 的导入路径问题
    monkeypatch.setattr(pi, "_vision_ready", lambda db: False)

    s = SessionLocal()
    p, _c, parent_h, _ch = parent_child(s, "pib3")
    bank = QuestionBank(user_id=p.id, title="卷", subject="数学", source="practice_pdf")
    s.add(bank)
    s.commit()
    bank_id = bank.id
    s.close()

    client = _client_router()
    r = client.post(f"/api/banks/{bank_id}/import-practice-pdf", headers=parent_h,
                    files={"file": ("a.pdf", b"%PDF-1.4 fake", "application/pdf")},
                    data={"answer_start_page": 100, "answer_end_page": 107})
    assert r.status_code == 400
    assert "视觉模型" in r.json()["detail"]


def test_missing_answers_lists_pending_without_answer(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import Question, QuestionBank

    s = SessionLocal()
    p, _c, parent_h, _ch = parent_child(s, "pib4")
    bank = QuestionBank(user_id=p.id, title="卷", subject="数学", source="practice_pdf")
    s.add(bank)
    s.flush()
    s.add(Question(user_id=p.id, bank_id=bank.id, qtype="oral", question="a",
                   answer="", status="pending", lesson_no=3, question_no="1"))
    s.commit()
    bank_id = bank.id
    s.close()

    client = _client_router()
    r = client.get(f"/api/practice-import/missing-answers?bank_id={bank_id}",
                   headers=parent_h)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["question_no"] == "1"


def test_patch_question_publishes_after_answer(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import Question, QuestionBank

    s = SessionLocal()
    p, _c, parent_h, _ch = parent_child(s, "pib5")
    bank = QuestionBank(user_id=p.id, title="卷", subject="数学", source="practice_pdf")
    s.add(bank)
    s.flush()
    q = Question(user_id=p.id, bank_id=bank.id, qtype="oral", question="a",
                 answer="", status="pending")
    s.add(q)
    s.commit()
    qid = q.id
    s.close()

    client = _client_router()
    r = client.patch(f"/api/practice-import/questions/{qid}", headers=parent_h,
                     json={"answer": "13.4"})
    assert r.status_code == 200
    assert r.json()["status"] == "published"


def test_lessons_endpoint_counts_published(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import Question, QuestionBank

    s = SessionLocal()
    p, _c, parent_h, _ch = parent_child(s, "pib6")
    bank = QuestionBank(user_id=p.id, title="卷", subject="数学", source="practice_pdf")
    s.add(bank)
    s.flush()
    s.add(Question(user_id=p.id, bank_id=bank.id, qtype="oral", question="a",
                   answer="1", status="published", lesson_no=3, lesson_title="小数乘小数"))
    s.commit()
    bank_id = bank.id
    s.close()

    client = _client_router()
    r = client.get(f"/api/practice-import/lessons?bank_id={bank_id}", headers=parent_h)
    assert r.status_code == 200
    lessons = r.json()["lessons"]
    assert lessons[0]["lesson_no"] == 3
    assert lessons[0]["title"] == "小数乘小数"
    assert lessons[0]["count"] == 1
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v -k "create_practice_book or import_rejects or missing_answers or patch_question or lessons_endpoint"
```

Expected: FAIL（`ModuleNotFoundError: app.routers.practice_import`）

- [ ] **Step 3: 实现 router**

新建 `backend/app/routers/practice_import.py`：

```python
"""练习册导入：上传 PDF、查进度、重试失败页、补答案、课时列表。"""
import json
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access, require_learning_user
from ..core.deps import require_role
from ..database import get_db
from ..models import PdfDocument, PdfPage, PracticeImportJob, Question, QuestionBank, User
from ..services.bucket_guard import resolve_bucket_id  # noqa: F401  (预留)
from ..services.model_config import resolve as resolve_model
from ..services.pdf_split import render_pages
from ..services.practice_import import run_import_job

router = APIRouter(tags=["practice-import"])

_MAX_BYTES = 120 * 1024 * 1024
PRACTICE_SOURCE = "practice_pdf"


class PracticeBookReq(BaseModel):
    title: str
    subject: str = "数学"
    grade: int | None = None


class PatchQuestionReq(BaseModel):
    answer: str | None = None
    question: str | None = None
    analysis: str | None = None


def _require_own_bank(bank_id: int, user: User, db: Session) -> QuestionBank:
    bank = db.get(QuestionBank, bank_id)
    if bank is None:
        raise HTTPException(status_code=404, detail={"error": "bank_not_found"})
    if user.role != "admin" and bank.user_id != user.id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    return bank


def _vision_ready(db: Session) -> bool:
    """OCR 需要 OpenAI 兼容（有 base_url）且非 fake 的 llm 档。"""
    try:
        r = resolve_model(db, "llm")
    except Exception:
        return False
    return r.provider != "fake" and bool(r.api_key) and bool(r.base_url)


@router.post("/api/banks/practice-book")
def create_practice_book(req: PracticeBookReq,
                         user: User = Depends(require_role("parent", "admin")),
                         db: Session = Depends(get_db)):
    """新建一个练习册卷（source=practice_pdf）。"""
    bank = QuestionBank(user_id=user.id, title=req.title.strip(), subject=req.subject,
                        grade=req.grade, source=PRACTICE_SOURCE)
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return {"id": bank.id, "title": bank.title}


@router.post("/api/banks/{bank_id}/import-practice-pdf")
def import_practice_pdf(
    bank_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    answer_start_page: str = Form(""),
    answer_end_page: str = Form(""),
    question_start_page: str = Form(""),
    question_end_page: str = Form(""),
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    bank = _require_own_bank(bank_id, user, db)

    if not _vision_ready(db):
        raise HTTPException(
            status_code=400,
            detail="需要配置 OpenAI 兼容 / 中转站的 llm 档才能 OCR（deepseek、glm 这类内置 base_url 的 provider 无法用于 OCR）")

    def _int(s: str) -> int | None:
        s = (s or "").strip()
        return int(s) if s.isdigit() else None

    a_start, a_end = _int(answer_start_page), _int(answer_end_page)
    if not a_start or not a_end:
        raise HTTPException(status_code=400, detail="必须填写答案页起止页（扫描版无法自动识别）")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="只支持 PDF")
    data = file.file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="PDF 超过 120MB")

    os.makedirs("uploads/practice", exist_ok=True)
    safe = f"practice_{uuid.uuid4().hex}{ext}"
    path = f"uploads/practice/{safe}"
    with open(path, "wb") as f:
        f.write(data)

    doc = PdfDocument(filename=os.path.basename(file.filename or safe),
                      subject=bank.subject or "数学", storage_path=path,
                      grade=bank.grade, content_kind="practice")
    db.add(doc)
    db.commit()
    db.refresh(doc)

    pages = render_pages(doc.id, path, f"uploads/{doc.id}_pages")
    for p in pages:
        db.add(PdfPage(document_id=doc.id, page_number=p["page_number"],
                       image_path=p["image_path"]))
    db.commit()

    total = len(pages)
    if a_start < 1 or a_end > total or a_start > a_end:
        raise HTTPException(
            status_code=400,
            detail=f"答案页范围非法：文档共 {total} 页")

    q_start = _int(question_start_page) or 1
    q_end = _int(question_end_page) or (a_start - 1)

    job = PracticeImportJob(
        user_id=user.id, bank_id=bank.id, document_id=doc.id,
        total_pages=total, question_start_page=q_start, question_end_page=q_end,
        answer_start_page=a_start, answer_end_page=a_end,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background.add_task(run_import_job, job.id)
    return {"job_id": job.id, "document_id": doc.id, "total_pages": total}


@router.get("/api/practice-import/jobs/{job_id}")
def get_job(job_id: int,
            user: User = Depends(require_learning_user),
            db: Session = Depends(get_db)):
    job = db.get(PracticeImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found"})
    ensure_user_access(user, job.user_id, db)
    return {
        "id": job.id, "status": job.status, "total_pages": job.total_pages,
        "done_pages": job.done_pages, "question_count": job.question_count,
        "aligned_count": job.aligned_count, "published_count": job.published_count,
        "failed_pages": json.loads(job.failed_pages or "[]"), "error": job.error,
    }


@router.post("/api/practice-import/jobs/{job_id}/retry")
def retry_job(job_id: int, background: BackgroundTasks,
              user: User = Depends(require_learning_user),
              db: Session = Depends(get_db)):
    """只重跑上次失败的页（成功页不重跑，省 OCR 费用）。"""
    job = db.get(PracticeImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found"})
    ensure_user_access(user, job.user_id, db)

    try:
        pages = json.loads(job.failed_pages or "[]")
    except (ValueError, TypeError):
        pages = []
    if not pages:
        return {"ok": False, "message": "没有失败页需要重试"}

    job.status = "pending"
    job.error = ""
    db.commit()
    background.add_task(run_import_job, job.id, list(pages))
    return {"ok": True, "retry_pages": pages}


@router.get("/api/practice-import/missing-answers")
def missing_answers(bank_id: int = Query(...),
                    user: User = Depends(require_learning_user),
                    db: Session = Depends(get_db)):
    bank = _require_own_bank(bank_id, user, db)
    rows = (db.query(Question)
            .filter(Question.bank_id == bank.id, Question.status == "pending",
                    Question.answer == "")
            .order_by(Question.lesson_no, Question.question_no)
            .all())
    return {"items": [
        {"id": q.id, "lesson_no": q.lesson_no, "lesson_title": q.lesson_title,
         "question_no": q.question_no, "question": q.question}
        for q in rows
    ]}


@router.patch("/api/practice-import/questions/{question_id}")
def patch_question(question_id: int, req: PatchQuestionReq,
                   user: User = Depends(require_role("parent", "admin")),
                   db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail={"error": "question_not_found"})
    bank = db.get(QuestionBank, q.bank_id) if q.bank_id else None
    if bank is None or (user.role != "admin" and bank.user_id != user.id):
        raise HTTPException(status_code=403, detail={"error": "forbidden"})

    if req.question is not None:
        q.question = req.question
    if req.analysis is not None:
        q.analysis = req.analysis
    if req.answer is not None:
        q.answer = req.answer.strip()
        if q.qtype in ("fill_blank", "cloze") and q.answer:
            parts = [p for p in q.answer.replace("，", ",").split(",") if p.strip()]
            q.answer_json = json.dumps({"blanks": [p.strip() for p in parts]},
                                       ensure_ascii=False)
        if q.answer:
            q.status = "published"
    db.commit()
    return {"id": q.id, "status": q.status}


@router.get("/api/practice-import/lessons")
def lessons(bank_id: int = Query(...),
            user: User = Depends(require_learning_user),
            db: Session = Depends(get_db)):
    bank = _require_own_bank(bank_id, user, db)
    rows = (db.query(Question.lesson_no,
                     func.max(Question.lesson_title),
                     func.count(Question.id))
            .filter(Question.bank_id == bank.id, Question.status == "published",
                    Question.lesson_no.isnot(None))
            .group_by(Question.lesson_no)
            .order_by(Question.lesson_no)
            .all())
    return {"lessons": [
        {"lesson_no": no, "title": title or "", "count": cnt}
        for no, title, cnt in rows
    ]}
```

- [ ] **Step 4: 注册 router**

在 `backend/app/main.py` 的 import 行加 `practice_import`，并在
`app.include_router(brain_games.router)` 之后加：

```python
app.include_router(practice_import.router)
```

- [ ] **Step 5: 启动时清理卡住的任务**

在 `main.py` 的 `_ensure_db_tables()` 末尾（迁移之后）追加：

```python
    db2 = SessionLocal()
    try:
        from .models import PracticeImportJob
        stuck = (db2.query(PracticeImportJob)
                 .filter(PracticeImportJob.status.in_(("rendering", "ocr", "aligning")))
                 .all())
        for j in stuck:
            j.status = "failed"
            j.error = "服务重启，请重试"
        if stuck:
            db2.commit()
    except Exception as exc:
        _log.warning("清理卡住的导入任务失败: %s", exc)
    finally:
        db2.close()
```

- [ ] **Step 6: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v
```

Expected: 全部 PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/routers/practice_import.py backend/app/main.py backend/tests/test_practice_import.py
git commit -m "feat(practice-import): 上传/进度/重试/待补/补答案/课时列表接口"
```

---

## Task 8: 练习册不进教材列表、不进题库练习

**Files:**
- Modify: `backend/app/routers/pdf.py`
- Modify: `backend/app/routers/bank.py`（`list_practice_banks`）
- Test: `backend/tests/test_practice_import.py`（追加）

- [ ] **Step 1: 写失败测试**

追加：

```python
def test_practice_doc_hidden_from_textbook_list(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import PdfDocument

    s = SessionLocal()
    p, _c, parent_h, _ch = parent_child(s, "pi_hide")
    s.add(PdfDocument(filename="练习册.pdf", subject="数学", storage_path="uploads/a.pdf",
                      content_kind="practice"))
    s.add(PdfDocument(filename="教材.pdf", subject="数学", storage_path="uploads/b.pdf",
                      content_kind="textbook"))
    s.commit()
    s.close()

    # 走真实路由（家长身份）
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.pdf import router as pdf_router

    app = FastAPI()
    app.include_router(pdf_router)
    r = TestClient(app).get("/api/pdf/documents", headers=parent_h)
    names = [d["filename"] for d in r.json()]
    assert "教材.pdf" in names
    assert "练习册.pdf" not in names

    # include_practice=true 时能看到
    r2 = TestClient(app).get("/api/pdf/documents?include_practice=true", headers=parent_h)
    assert "练习册.pdf" in [d["filename"] for d in r2.json()]


def test_practice_bank_excluded_from_practice_list(setup_db):
    from app.database import SessionLocal
    from conftest import parent_child
    from app.models import Question, QuestionBank

    s = SessionLocal()
    p, c, _ph, child_h = parent_child(s, "pi_hide2")
    bank = QuestionBank(user_id=p.id, title="练习册卷", subject="数学",
                        source="practice_pdf", status="active")
    s.add(bank)
    s.flush()
    s.add(Question(user_id=p.id, bank_id=bank.id, qtype="oral", question="a",
                   answer="1", status="published"))
    s.commit()
    s.close()

    client = _client_router()
    r = client.get("/api/banks/practice", headers=child_h)
    assert r.status_code == 200
    assert all(b["title"] != "练习册卷" for b in r.json())
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v -k "hidden or excluded"
```

Expected: FAIL

- [ ] **Step 3: 改 pdf 列表过滤（`list_documents` 已存在，直接改）**

`backend/app/routers/pdf.py:69` 的 `list_documents` 已存在，**不要新建函数**。
给它加一个 `include_practice` 参数并在查询上过滤：

```python
@router.get("/documents")
def list_documents(user_id: int | None = None,
                   include_practice: bool = False,
                   user: User = Depends(require_learning_user),
                   db: Session = Depends(get_db)):
    # ...原有 effective_user_id 解析不变...

    q = db.query(PdfDocument)
    if effective_user_id is not None:
        bound = db.query(UserDocument.document_id).filter_by(user_id=effective_user_id)
        q = q.filter(PdfDocument.id.in_(bound))
    if not include_practice:
        # 练习册不进教材列表（只在「练习册导入」子视图里出现）
        q = q.filter(PdfDocument.content_kind != "practice")
    docs = q.all()
```

> 注意 `PdfDocument` **没有 `user_id` 列**（已核实），归属靠 `UserDocument` 绑定表。
> 因此不要写 `PdfDocument.user_id == ...`。`content_kind` 老数据可能为 NULL，
> 用 `!= "practice"` 在 SQLite 下会排除 NULL 行 —— 若担心，写成
> `or_(PdfDocument.content_kind.is_(None), PdfDocument.content_kind != "practice")`。

- [ ] **Step 4: 改 `list_practice_banks`**

`backend/app/routers/bank.py:290` 那句 `.filter_by(user_id=pid, status="active")`
改为：

```python
        .filter(QuestionBank.user_id == pid,
                QuestionBank.status == "active",
                QuestionBank.source != PRACTICE_SOURCE)
```

并在文件顶部加常量（若无）：

```python
PRACTICE_SOURCE = "practice_pdf"
```

- [ ] **Step 5: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/test_practice_import.py -v -k "hidden or excluded"
```

Expected: PASS（2 passed）

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/pdf.py backend/app/routers/bank.py backend/tests/test_practice_import.py
git commit -m "fix(practice-import): 练习册不进教材列表、不进题库练习列表"
```

---

## Task 9: 家长端「练习册导入」子视图

**Files:**
- Modify: `parent-web/app.js`
- Modify: `parent-web/index.html`（bump `app.js?v=`）

- [ ] **Step 1: 加子视图状态与渲染**

在 `parent-web/app.js` 顶部状态区（`let parentTab = '教材';` 附近）加：

```javascript
// 练习册导入
let practiceBookBanks = [];      // [{id,title,subject,grade}]
let practiceImportJob = null;    // 当前 job 进度
let practiceLessons = [];        // [{lesson_no,title,count}]
let practiceMissing = [];        // 待补答案
let practicePollTimer = null;
```

在「题库管理」渲染函数里加一个入口按钮（`renderBankManage` 的 head 区）：

```javascript
<button class="btn-ghost" style="margin-left:auto" onclick="openPracticeImport()">练习册导入</button>
```

追加渲染函数：

```javascript
async function openPracticeImport(){
  await loadPracticeBanks();
  bankView = 'practice_import';
  render();
}

async function loadPracticeBanks(){
  const list = await api('/api/banks');
  practiceBookBanks = (Array.isArray(list) ? list : []).filter(b => b.source === 'practice_pdf');
}

function renderPracticeImport(){
  const bankOpts = practiceBookBanks.map(b =>
    `<option value="${b.id}">${escapeAttr(b.title)}（${escapeAttr(b.subject || '')}）</option>`
  ).join('');
  const job = practiceImportJob;
  const progress = job ? `
    <div style="margin-top:16px;padding:14px 16px;border-radius:12px;background:var(--blue-soft2)">
      <div style="font-size:13px;font-weight:700">导入进度：${job.status}</div>
      <div style="font-size:12px;color:var(--gray2);margin-top:6px">
        第 ${job.done_pages}/${job.total_pages} 页 ·
        识别 ${job.question_count} 题 · 已对齐 ${job.aligned_count} ·
        已发布 ${job.published_count}
      </div>
      ${job.failed_pages && job.failed_pages.length
        ? `<div style="margin-top:8px;font-size:12px;color:#c05b4a">
             失败页：${job.failed_pages.join(', ')}
             <span class="rule-edit" style="margin-left:8px" onclick="retryPracticeJob(${job.id})">重试</span>
           </div>` : ''}
      ${job.error ? `<div style="margin-top:6px;font-size:12px;color:#c05b4a">${escapeAttr(job.error)}</div>` : ''}
    </div>` : '';

  const missingRows = practiceMissing.length ? practiceMissing.map(m => `
    <div class="pdf-row">
      <div class="pdf-info">
        <div class="nm">第 ${m.lesson_no} 课时 · ${escapeAttr(m.lesson_title || '')}</div>
        <div class="meta">题 ${escapeAttr(m.question_no || '')}：${escapeAttr(m.question).slice(0, 60)}</div>
      </div>
      <div class="pdf-actions">
        <input placeholder="填标准答案" id="ans_${m.id}"
               style="border:1px solid var(--line3);border-radius:8px;padding:6px 10px;font-size:12px;width:140px">
        <button class="btn-ghost" onclick="savePracticeAnswer(${m.id})">保存</button>
      </div>
    </div>`).join('') : '<div style="color:#8e9691;padding:8px 0">没有待补答案</div>';

  const lessonOpts = practiceLessons.map(l =>
    `<option value="${l.lesson_no}">第${l.lesson_no}课时 ${escapeAttr(l.title)}（${l.count}题）</option>`
  ).join('');

  return `<div class="parent-grid" style="display:block">
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic blue">${icon('book',20)}</div>
        <div><h3>练习册导入</h3>
          <div class="sub">上传扫描版练习册 PDF，自动 OCR 拆出课时与题目</div></div>
        <button class="btn-ghost" style="margin-left:auto" onclick="bankView=null;render()">返回题库管理</button>
      </div>
      <div class="bd">
        <div class="bank-field">
          <div class="bank-field-label">选择练习册卷</div>
          <select id="practiceBankSel" style="width:100%;border:1px solid var(--line3);border-radius:10px;padding:9px 12px;font-size:13px" onchange="loadPracticeLessons(this.value)">
            <option value="">— 请选择 —</option>${bankOpts}
          </select>
          <button class="btn-ghost" style="margin-top:8px" onclick="createPracticeBook()">+ 新建练习册卷</button>
        </div>

        <div class="bank-field" style="margin-top:16px">
          <div class="bank-field-label">上传 PDF</div>
          <input type="file" id="practicePdf" accept="application/pdf" style="font-size:13px">
          <div style="display:flex;gap:10px;margin-top:10px;flex-wrap:wrap;align-items:center">
            <label style="font-size:12px;color:var(--gray2)">答案页起
              <input id="ansStart" type="number" min="1" style="width:80px;border:1px solid var(--line3);border-radius:8px;padding:6px 8px">
            </label>
            <label style="font-size:12px;color:var(--gray2)">止
              <input id="ansEnd" type="number" min="1" style="width:80px;border:1px solid var(--line3);border-radius:8px;padding:6px 8px">
            </label>
            <button class="btn-primary" onclick="startPracticeImport()">开始导入</button>
          </div>
          <div class="ms-hint">扫描版 PDF 无法自动识别答案页，请先翻到答案页填写范围（如 100–107）。</div>
        </div>

        ${progress}

        <div style="margin-top:20px">
          <div class="bank-list-head">待补答案</div>
          <div class="pdf-list">${missingRows}</div>
        </div>

        <div style="margin-top:20px">
          <div class="bank-list-head">当前课时（决定孩子每天练哪页）</div>
          <select style="border:1px solid var(--line3);border-radius:10px;padding:9px 12px;font-size:13px;min-width:280px"
                  onchange="savePracticeLesson(this.value)">
            <option value="">— 请选择 —</option>${lessonOpts}
          </select>
        </div>
      </div>
    </div>
  </div>`;
}
```

- [ ] **Step 2: 加交互函数**

追加：

```javascript
async function createPracticeBook(){
  const title = prompt('练习册名称（如 RJ五上 计算小达人）');
  if(!title) return;
  const r = await api('/api/banks/practice-book', {method:'POST',
    body:{title, subject:'数学', grade:5}});
  if(r && r.id){ await loadPracticeBanks(); render(); toast('已创建练习册卷'); }
  else toast('创建失败');
}

async function startPracticeImport(){
  const sel = document.getElementById('practiceBankSel');
  const file = document.getElementById('practicePdf');
  const a1 = (document.getElementById('ansStart')?.value || '').trim();
  const a2 = (document.getElementById('ansEnd')?.value || '').trim();
  if(!sel || !sel.value) return toast('请先选择练习册卷');
  if(!file || !file.files.length) return toast('请选择 PDF');
  if(!a1 || !a2) return toast('请填写答案页起止页');

  const fd = new FormData();
  fd.append('file', file.files[0]);
  fd.append('answer_start_page', a1);
  fd.append('answer_end_page', a2);
  toast('正在上传并开始 OCR，请稍候…');
  const r = await apiForm(`/api/banks/${sel.value}/import-practice-pdf`, fd);
  if(r && r.job_id){ pollPracticeJob(r.job_id); }
  else toast('导入失败：' + (r && (r.detail || r.error) ? (r.detail || r.error) : '未知错误'));
}

function pollPracticeJob(jobId){
  if(practicePollTimer) clearInterval(practicePollTimer);
  const tick = async () => {
    const j = await api(`/api/practice-import/jobs/${jobId}`);
    if(j && j.id){
      practiceImportJob = j;
      render();
      if(j.status === 'done' || j.status === 'failed'){
        clearInterval(practicePollTimer);
        practicePollTimer = null;
        await loadPracticeMissing();
        render();
      }
    }
  };
  tick();
  practicePollTimer = setInterval(tick, 2000);
}

async function retryPracticeJob(jobId){
  const r = await api(`/api/practice-import/jobs/${jobId}/retry`, {method:'POST'});
  if(r && r.ok){ practiceImportJob = null; pollPracticeJob(jobId); }
  else toast('重试失败');
}

async function loadPracticeMissing(){
  const sel = document.getElementById('practiceBankSel');
  const bankId = sel && sel.value;
  if(!bankId){ practiceMissing = []; return; }
  const r = await api(`/api/practice-import/missing-answers?bank_id=${bankId}`);
  practiceMissing = (r && r.items) || [];
}

async function savePracticeAnswer(qid){
  const el = document.getElementById(`ans_${qid}`);
  const answer = (el && el.value || '').trim();
  if(!answer) return toast('请填写答案');
  const r = await api(`/api/practice-import/questions/${qid}`, {method:'PATCH',
    body:{answer}});
  if(r && r.id){ toast('已保存并发布'); await loadPracticeMissing(); render(); }
  else toast('保存失败');
}

async function loadPracticeLessons(bankId){
  if(!bankId){ practiceLessons = []; practiceMissing = []; render(); return; }
  const r = await api(`/api/practice-import/lessons?bank_id=${bankId}`);
  practiceLessons = (r && r.lessons) || [];
  await loadPracticeMissing();
  render();
}

async function savePracticeLesson(lessonNo){
  const sel = document.getElementById('practiceBankSel');
  const bankId = sel && sel.value;
  if(!bankId || !lessonNo) return;
  const r = await api('/api/practice/preferences', {method:'PUT',
    body:{user_id: uid, current_document: Number(bankId), current_lesson: Number(lessonNo)}});
  toast(r && r.ok ? '已设为当前课时' : '设置失败');
}
```

- [ ] **Step 3: 挂到 render 分发**

在 `render()`（或 `renderParent()`）里，让 `renderBankManage` 能切到子视图：

```javascript
function renderBankManage(){
  if(bankView === 'practice_import') return renderPracticeImport();
  // ...原有实现
}
```

并在状态区加 `let bankView = null;`

- [ ] **Step 4: bump 版本号**

`parent-web/index.html` 里 `app.js?v=N` 改成 `N+1`。

- [ ] **Step 5: 手工冒烟**

1. 启动后端：`cd backend && python -m uvicorn app.main:app --port 8010`
2. 启动家长端：`python -m http.server 8767 --directory parent-web`
3. 打开 `http://127.0.0.1:8767/?cb=1`，登录家长账号
4. 题库管理 → 练习册导入 → 新建练习册卷 → 选 PDF（`D:\smartedu_download\RJ5上.pdf`）
   → 填答案页 100–107 → 开始导入
5. 观察进度条递增；完成后看待补答案清单

Expected: 进度从 0/108 递增；完成后显示已识别/已对齐/已发布数字

- [ ] **Step 6: 提交**

```bash
git add parent-web/app.js parent-web/index.html
git commit -m "feat(parent-web): 练习册导入子视图（上传/进度/待补答案/当前课时）"
```

---

## Task 10: 全量回归

**Files:** 无新增

- [ ] **Step 1: 后端全量测试**

```bash
cd backend && python -m pytest -q
```

Expected: 全绿。若 `test_bank.py` 等因 `user_id` 变更失败，按新语义调整断言（不是放宽检查）。

- [ ] **Step 2: 迁移幂等复验**

```bash
cd backend && python -c "
from app.migrate_practice_import import migrate
migrate(); migrate(); print('ok')
"
```

Expected: `ok`

- [ ] **Step 3: 端到端验证（重启不丢题）**

```bash
# 1) 导入一本书（或直接造几条 published 题）
# 2) 重启后端
cd backend && python -m uvicorn app.main:app --port 8010
# 3) 查题数
cd backend && python -c "
from app.database import SessionLocal
from app.models import Question
db = SessionLocal()
print('practice questions:', db.query(Question).filter_by(source_document_id=None).count())
print('published total:', db.query(Question).filter_by(status='published').count())
db.close()
"
```

Expected: 重启前后数量一致（这是 Task 2 的核心验收）

- [ ] **Step 4: 提交收尾（如有小修）**

```bash
git add -A
git commit -m "test(practice-import): 端到端验证与收尾"
```

---

## 验收标准（计划一）

- [ ] `Question` 有 `lesson_no`/`lesson_title`/`question_no`/`source_document_id`，且存量库迁移后索引存在
- [ ] **导入的题 `user_id` 非空；重启服务后题数不变**（不许被 `migrate_grade_buckets` 删掉）
- [ ] 上传 PDF 必须填答案页起止页；未配置视觉模型时返回 400 且不启动任务
- [ ] 后台任务逐页推进 `done_pages`；失败页记录并可 `/retry`
- [ ] **只有答案已对齐的题被发布**；未对齐进「待补答案」清单
- [ ] 家长补答案后该题自动 `published`
- [ ] 练习册不出现在「教材」列表，也不出现在孩子端「题库练习」列表
- [ ] 课时列表接口返回 `lesson_no`/`title`/`count`
- [ ] `pytest` 全绿；服务重启后题目数量不变

## 下一步

计划二（学生端「每日一练」+ Flutter 第 5 Tab）单独成文：
`docs/superpowers/plans/<date>-practice-daily-plan2.md`。
