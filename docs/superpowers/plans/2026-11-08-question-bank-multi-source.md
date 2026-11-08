# 题型统一化 + 多来源题库 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 `Question` 表上做加法，落地题型 taxonomy、统一富答案结构、独立题库、可插拔 `SourceAdapter`（人工/拍照 OCR/第三方占位），并打通家长录入→审核→孩子做题判分闭环。

**Architecture:** 后端为核心：新增 `core/question_types.py`（题型常量）、`core/source_adapter.py`（adapter 接口 + 三个实现）、`services/grade_question.py`（多题型判分）、`routers/bank.py`（题库/卷）；`models.py` 加列加表。前端 `parent-web` 加题库管理页 + 审核扩展，Flutter 学生端加题库练习。三个来源经 adapter 标准化汇聚到同一张 `Question` 表与同一套 `pending→published` 审核流。

**Tech Stack:** Python 3 + FastAPI + SQLAlchemy（SQLite 测试 / MySQL 生产）+ pytest；`parent-web` 原生 JS；`student-app` Flutter（Riverpod + go_router + dio）。

**关键约束（来自 AGENTS.md，勿违反）：**
- 后端启动/测试必须从 `backend/` 目录跑（`DATABASE_URL` 是相对路径 `sqlite:///./zhixueban.db`）。测试已在 `backend/tests/conftest.py` 里强制 `sqlite:///./test.db`。
- 跑后端用 Bash 的 `python`（装了全部依赖），不要用 PowerShell 的 conda python。
- 所有测试命令在 `backend/` 目录下执行：`python -m pytest tests/<file>::<test> -v`。
- AI provider 走 `services/ai.py` 的 `get_provider(db)`（三级降级，绝不抛异常）；未配置时回落 `FakeProvider`（`generate` 返回 `[fake] ...`）。
- 主观题 AI 判分未配置 → 返回 `pending`（待家长批改），不报错。

---

## File Structure（新增/改动清单）

**后端（新增）：**
- `backend/app/core/question_types.py` — 题型 taxonomy 常量（`CATEGORY_OF_QTYPE`、`QTYPE_LABELS`、`QTYPES`）
- `backend/app/core/source_adapter.py` — `QuestionDraft` dataclass + `SourceAdapter` 接口 + `ManualAdapter`/`OcrAdapter`/`ThirdPartyAdapter` 基类
- `backend/app/core/source_registry.py` — 来源注册表 + `tiku.cn` 占位 stub
- `backend/app/services/grade_question.py` — `grade_question()` 多题型判分 + `grade_subjective()` + `normalize_answer()`
- `backend/app/services/ocr_import.py` — 拍照 → OCR → LLM 结构化 → `list[QuestionDraft]`
- `backend/app/routers/bank.py` — 建卷/列卷/拉题/做题提交
- `backend/tests/test_question_types.py`、`backend/tests/test_grade_question.py`、`backend/tests/test_source_adapter.py`、`backend/tests/test_ocr_import.py`、`backend/tests/test_bank.py`

**后端（改动）：**
- `backend/app/models.py` — `Question` 加列 + `lesson_id` 改 nullable；新增 `QuestionBank`
- `backend/app/routers/questions.py` — `add_question` 扩展富结构

**前端（改动）：**
- `parent-web/app.js` + `parent-web/index.html` — 题库管理页 + 审核扩展
- `student-app/lib/features/bank_exercise/`（新增）— 题库练习

---

## Phase 0：模型与题型常量（后端基础）

### Task 1: 题型 taxonomy 常量 + 测试

**Files:**
- Create: `backend/app/core/question_types.py`
- Test: `backend/tests/test_question_types.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_question_types.py
from app.core.question_types import CATEGORY_OF_QTYPE, QTYPE_LABELS, QTYPES, CATEGORIES

def test_every_qtype_has_category_and_label():
    for qtype in QTYPES:
        assert qtype in CATEGORY_OF_QTYPE, f"{qtype} 缺 category"
        assert qtype in QTYPE_LABELS, f"{qtype} 缺 label"

def test_category_in_categories():
    for cat in CATEGORY_OF_QTYPE.values():
        assert cat in CATEGORIES

def test_known_mappings():
    assert CATEGORY_OF_QTYPE["single_choice"] == "choice"
    assert CATEGORY_OF_QTYPE["true_false"] == "choice"
    assert CATEGORY_OF_QTYPE["fill_blank"] == "blank"
    assert CATEGORY_OF_QTYPE["calculation"] == "blank"
    assert CATEGORY_OF_QTYPE["matching"] == "match"
    assert CATEGORY_OF_QTYPE["essay"] == "subjective"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_question_types.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.core.question_types'`

- [ ] **Step 3: 实现常量**

```python
# backend/app/core/question_types.py
"""题型 taxonomy：category（判分方式）→ qtype（展示/录入）。"""
CATEGORIES = ("choice", "blank", "match", "subjective")

CATEGORY_OF_QTYPE: dict[str, str] = {
    "single_choice": "choice",
    "multi_choice": "choice",
    "true_false": "choice",
    "fill_blank": "blank",
    "cloze": "blank",
    "calculation": "blank",
    "matching": "match",
    "short_answer": "subjective",
    "essay": "subjective",
    "application": "subjective",
    "oral": "subjective",
}

QTYPE_LABELS: dict[str, str] = {
    "single_choice": "单选题",
    "multi_choice": "多选题",
    "true_false": "判断题",
    "fill_blank": "填空题",
    "cloze": "完形填空",
    "calculation": "计算题",
    "matching": "连线题",
    "short_answer": "简答题",
    "essay": "作文",
    "application": "应用题",
    "oral": "口语题",
}

QTYPES = tuple(CATEGORY_OF_QTYPE.keys())

# 旧 qtype 粗粒度值 → taxonomy 最近项
LEGACY_QTYPE_MAP: dict[str, str] = {
    "reading": "short_answer",
    "listening": "single_choice",
    "knowledge": "short_answer",
    "math": "application",
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_question_types.py -v`
Expected: PASS（4 项全过）

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/question_types.py backend/tests/test_question_types.py
git commit -m "feat(bank): question type taxonomy constants"
```

### Task 2: `Question` 加列 + `QuestionBank` 模型

**Files:**
- Modify: `backend/app/models.py`（`Question` 类 97-111 行；文件末尾追加 `QuestionBank`）
- Test: `backend/tests/test_models.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_models.py 追加
from app.models import Question, QuestionBank
from sqlalchemy import inspect

def test_question_new_columns():
    cols = {c.name for c in inspect(Question).columns}
    for name in ("answer_json", "options", "analysis", "difficulty", "tags",
                 "qtype_category", "bank_id"):
        assert name in cols, f"Question 缺列 {name}"

def test_question_lesson_id_nullable():
    assert Question.__table__.c.lesson_id.nullable is True

def test_question_bank_table():
    cols = {c.name for c in inspect(QuestionBank).columns}
    for name in ("user_id", "title", "subject", "grade", "tags", "source", "status"):
        assert name in cols
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_models.py::test_question_new_columns -v`
Expected: FAIL（AssertionError：缺列）

- [ ] **Step 3: 改 `Question` + 新增 `QuestionBank`**

`Question` 类（`models.py` 97-111 行）替换为：

```python
class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=True)  # 改 nullable：可独立成题
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"), nullable=True)  # 归属的卷
    qtype: Mapped[str] = mapped_column(String(16), default="reading")   # taxonomy 值（single_choice/fill_blank/...）
    qtype_category: Mapped[str] = mapped_column(String(16), default="subjective")  # choice|blank|match|subjective
    question: Mapped[str] = mapped_column(LongText)
    answer: Mapped[str] = mapped_column(LongText, default="")
    answer_json: Mapped[str] = mapped_column(LongText, default="")       # 机器判分依据 JSON
    options: Mapped[str] = mapped_column(LongText, default="")           # 选择/连线题选项 JSON
    analysis: Mapped[str] = mapped_column(LongText, default="")          # 解析
    difficulty: Mapped[str] = mapped_column(String(16), default="medium")  # easy|medium|hard
    tags: Mapped[str] = mapped_column(LongText, default="")              # {grade, knowledge_points, source} JSON
    subject: Mapped[str] = mapped_column(String(16), default="")         # 学科：语文/英语/数学
    date: Mapped[date] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="published")
    extra: Mapped[str] = mapped_column(LongText, default="")
    task_type: Mapped[str] = mapped_column(String(16), default="reading")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

在 `models.py` 末尾（`FamilyBindRequest` 之后）追加：

```python
class QuestionBank(Base):
    """家长自建的一册卷子/题库；一道题可挂卷、挂课、或都不挂只靠 tags 检索。"""
    __tablename__ = "question_banks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(16), default="")
    grade: Mapped[int] = mapped_column(Integer, nullable=True)
    tags: Mapped[str] = mapped_column(LongText, default="")   # JSON 文本
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual|photo|third_party
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|archived
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: PASS（含既有 test_models.py 全部 + 新增 3 项）

- [ ] **Step 5: 提交**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat(bank): Question rich-answer columns + QuestionBank model"
```

---

## Phase 1：判分 + 来源 adapter（后端核心）

### Task 3: `grade_question()` 多题型判分

**Files:**
- Create: `backend/app/services/grade_question.py`
- Test: `backend/tests/test_grade_question.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_grade_question.py
from app.services.grade_question import grade_question, normalize_answer

def test_grade_single_choice():
    r = grade_question("choice", {"correct_index": 2}, {"selected_index": 2})
    assert r["is_correct"] is True

def test_grade_single_choice_wrong():
    r = grade_question("choice", {"correct_index": 2}, {"selected_index": 0})
    assert r["is_correct"] is False

def test_grade_multi_choice():
    r = grade_question("choice", {"correct_index": [0, 2]}, {"selected_index": [2, 0]})
    assert r["is_correct"] is True

def test_grade_fill_blank_normalized():
    r = grade_question("blank", {"blanks": ["春天", "播种"]}, {"blanks": [" 春天 ", "播种"]})
    assert r["is_correct"] is True

def test_grade_calculation():
    r = grade_question("blank", {"blanks": ["8"]}, {"blanks": ["8"]})
    assert r["is_correct"] is True

def test_grade_match():
    r = grade_question("match", {"pairs": [["A", "1"], ["B", "3"]]},
                       {"pairs": [["A", "1"], ["B", "3"]]})
    assert r["is_correct"] is True

def test_normalize_answer():
    assert normalize_answer("  Hello World ") == "helloworld"
    assert normalize_answer("苹果") == "苹果"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_grade_question.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现判分**

```python
# backend/app/services/grade_question.py
"""多题型判分：客观题精确判，主观题走 AI（未配置回落 pending）。"""
import json
import re

_SPACING = re.compile(r"[\s\-·、，。,.!！?？:：;；'\"“”‘’()（）\[\]【】]+")


def normalize_answer(value: str) -> str:
    """去空白/标点/大小写，供填空/计算容错比较。"""
    return _SPACING.sub("", (value or "").casefold())


def grade_question(qtype_category: str, answer_json: dict, student_answer: dict) -> dict:
    """返回 {is_correct, correct_answer_text, detail}。

    student_answer 形状按题型：
      choice:  {"selected_index": int | list[int]}
      blank:   {"blanks": [str]}
      match:   {"pairs": [[str,str],...]}
      subjective: {"text": str}
    """
    if qtype_category == "choice":
        ci = answer_json.get("correct_index")
        sel = student_answer.get("selected_index")
        if isinstance(ci, list):
            ok = isinstance(sel, list) and sorted(map(int, sel)) == sorted(map(int, ci))
        else:
            ok = isinstance(sel, int) and sel == ci
        return {"is_correct": ok, "correct_answer_text": json.dumps(ci, ensure_ascii=False), "detail": "choice"}

    if qtype_category == "blank":
        expected = answer_json.get("blanks") or []
        got = student_answer.get("blanks") or []
        ok = len(expected) == len(got) and all(
            normalize_answer(e) == normalize_answer(g) for e, g in zip(expected, got)
        )
        return {"is_correct": ok, "correct_answer_text": "；".join(expected), "detail": "blank"}

    if qtype_category == "match":
        expected = sorted(tuple(p) for p in (answer_json.get("pairs") or []))
        got = sorted(tuple(p) for p in (student_answer.get("pairs") or []))
        ok = expected == got
        return {"is_correct": ok, "correct_answer_text": json.dumps(answer_json.get("pairs"), ensure_ascii=False), "detail": "match"}

    # subjective：交给 grade_subjective
    return grade_subjective(answer_json, student_answer)


def grade_subjective(answer_json: dict, student_answer: dict) -> dict:
    """主观题 AI 判分；未配置/fake 回落 pending（待家长批改）。"""
    from sqlalchemy.orm import Session
    from .ai import get_provider

    rubric = (answer_json.get("rubric") or "").strip()
    sample = (answer_json.get("sample") or "").strip()
    text = (student_answer.get("text") or "").strip()
    if not text:
        return {"is_correct": False, "correct_answer_text": sample, "detail": "empty"}
    # grade_subjective 需要 db；由调用方传入，这里简化：无 db 时直接 pending
    return {"is_correct": None, "correct_answer_text": sample, "detail": "pending"}
```

> 注：`grade_subjective` 的 AI 调用需要 `db`。为保持 `grade_question()` 纯函数，把 AI 判分拆成独立函数 `grade_subjective_with_ai(db, answer_json, student_answer)`（Task 4 补），此处 `grade_subjective` 先返回 `pending`，保证客观题判分可先行验证。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_grade_question.py -v`
Expected: PASS（7 项全过；主观题未在本任务断言 `is_correct`）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/grade_question.py backend/tests/test_grade_question.py
git commit -m "feat(bank): multi-type grade_question objective grading"
```

### Task 4: 主观题 AI 判分 `grade_subjective_with_ai`

**Files:**
- Modify: `backend/app/services/grade_question.py`
- Test: `backend/tests/test_grade_question.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_grade_question.py 追加
from app.services.grade_question import grade_subjective_with_ai

def test_grade_subjective_fake_returns_pending(client):
    # fake provider：generate 返回 "[fake] ..."，无法解析 → pending
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        r = grade_subjective_with_ai(db, {"rubric": "要点", "sample": "参考"}, {"text": "我的回答"})
    finally:
        db.close()
    assert r["is_correct"] is None
    assert r["detail"] == "pending"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_grade_question.py::test_grade_subjective_fake_returns_pending -v`
Expected: FAIL（ImportError：`grade_subjective_with_ai` 未定义）

- [ ] **Step 3: 实现**

在 `backend/app/services/grade_question.py` 末尾追加：

```python
def grade_subjective_with_ai(db, answer_json: dict, student_answer: dict) -> dict:
    """主观题 AI 判分。返回 {is_correct: bool|None, correct_answer_text, detail}。

    AI 未配置 / fake / 返回无法解析 → is_correct=None, detail="pending"（待家长批改）。
    """
    from .ai import get_provider

    rubric = (answer_json.get("rubric") or "").strip()
    sample = (answer_json.get("sample") or "").strip()
    text = (student_answer.get("text") or "").strip()
    if not text:
        return {"is_correct": False, "correct_answer_text": sample, "detail": "empty"}

    provider = get_provider(db)
    if provider.name == "fake":
        return {"is_correct": None, "correct_answer_text": sample, "detail": "pending"}

    prompt = (
        f"你是一位小学老师，正在批改一道主观题。\n"
        f"评分要点（rubric）：{rubric or '未提供'}\n"
        f"参考答案：{sample or '未提供'}\n"
        f"学生作答：{text}\n"
        '只返回 JSON：{"is_correct": true 或 false, "reason": "简短评语"}'
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是小学老师，公正批改。", json_mode=True)
        data = json.loads(raw)
        return {
            "is_correct": bool(data.get("is_correct", False)),
            "correct_answer_text": sample,
            "detail": data.get("reason", ""),
        }
    except Exception:
        return {"is_correct": None, "correct_answer_text": sample, "detail": "pending"}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_grade_question.py -v`
Expected: PASS（含上一步 7 项 + 新增 1 项）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/grade_question.py backend/tests/test_grade_question.py
git commit -m "feat(bank): subjective AI grading with pending fallback"
```

### Task 5: `SourceAdapter` 接口 + 三个实现 + registry

**Files:**
- Create: `backend/app/core/source_adapter.py`
- Create: `backend/app/core/source_registry.py`
- Test: `backend/tests/test_source_adapter.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_source_adapter.py
from app.core.source_adapter import QuestionDraft, ManualAdapter, ThirdPartyAdapter
from app.core.source_registry import SOURCE_REGISTRY

def test_manual_adapter_normalize():
    raw = {"qtype": "single_choice", "question": "1+1=?", "options": [{"label": "1", "value": 0}, {"label": "2", "value": 1}], "answer_json": {"correct_index": 1}}
    drafts = ManualAdapter().normalize(raw)
    assert len(drafts) == 1
    d = drafts[0]
    assert d.qtype == "single_choice"
    assert d.options == [{"label": "1", "value": 0}, {"label": "2", "value": 1}]
    assert d.answer_json == {"correct_index": 1}

def test_third_party_registry_has_tiku():
    assert "tiku.cn" in SOURCE_REGISTRY
    adapter = SOURCE_REGISTRY["tiku.cn"]
    assert isinstance(adapter, ThirdPartyAdapter)
    assert adapter.name == "tiku.cn"

def test_tiku_stub_returns_empty():
    assert SOURCE_REGISTRY["tiku.cn"].normalize({"raw": "x"}) == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_source_adapter.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现接口与三个实现**

```python
# backend/app/core/source_adapter.py
"""题目来源标准化：各来源产出统一的 QuestionDraft 中间结构。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class QuestionDraft:
    qtype: str = ""
    question: str = ""
    options: list[dict] = field(default_factory=list)   # [{label, value}]
    answer_json: dict = field(default_factory=dict)     # 机器判分依据
    answer: str = ""                                     # 标准答案展示文本
    analysis: str = ""
    difficulty: str = "medium"
    tags: dict = field(default_factory=dict)


class SourceAdapter(ABC):
    """一个来源 = 一个 normalize 实现。输出 QuestionDraft，落库/审核/判分统一处理。"""

    @abstractmethod
    def normalize(self, raw) -> list[QuestionDraft]:
        ...


class ManualAdapter(SourceAdapter):
    """家长录入表单：raw 已经是富结构，直接产出单个 draft。"""

    def normalize(self, raw) -> list[QuestionDraft]:
        d = QuestionDraft(
            qtype=(raw.get("qtype") or "").strip(),
            question=(raw.get("question") or "").strip(),
            options=raw.get("options") or [],
            answer_json=raw.get("answer_json") or {},
            answer=(raw.get("answer") or "").strip(),
            analysis=(raw.get("analysis") or "").strip(),
            difficulty=(raw.get("difficulty") or "medium"),
            tags=raw.get("tags") or {},
        )
        return [d] if d.question else []


class ThirdPartyAdapter(SourceAdapter):
    """第三方题库基类。子类实现 fetch() 拉取原始数据 + normalize() 转 QuestionDraft。

    第一版只有 tiku.cn 占位 stub：normalize 返回空，等待后续接入（需爬虫/商业授权）。
    """
    name = "third_party"

    def fetch(self, *args, **kwargs):
        raise NotImplementedError

    def normalize(self, raw) -> list[QuestionDraft]:
        return []


class OcrAdapter(SourceAdapter):
    """卷子拍照：OCR + LLM 结构化。raw 是 OCR 文字，结构化在 services/ocr_import 完成。

    normalize 接收已结构化的 dict（list of 题），转成 QuestionDraft。
    """
    def normalize(self, raw) -> list[QuestionDraft]:
        items = raw.get("questions") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            return []
        drafts = []
        for it in items:
            if not isinstance(it, dict):
                continue
            q = (it.get("question") or it.get("prompt") or "").strip()
            if not q:
                continue
            drafts.append(QuestionDraft(
                qtype=(it.get("qtype") or "short_answer").strip(),
                question=q,
                options=it.get("options") or it.get("choices") or [],
                answer_json=it.get("answer_json") or {},
                answer=(it.get("answer") or "").strip(),
                analysis=(it.get("analysis") or "").strip(),
                difficulty=(it.get("difficulty") or "medium"),
                tags=it.get("tags") or {},
            ))
        return drafts
```

```python
# backend/app/core/source_registry.py
"""题目来源注册表：新增来源 = 新增一个 adapter 并注册到这里。"""
from .source_adapter import SourceAdapter, ThirdPartyAdapter


class TikuCnAdapter(ThirdPartyAdapter):
    name = "tiku.cn"

    def normalize(self, raw) -> list:
        # 占位 stub：tiku.cn 无公开 API，具体同步（爬虫/授权）后续实现。
        return []


SOURCE_REGISTRY: dict[str, SourceAdapter] = {
    "tiku.cn": TikuCnAdapter(),
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_source_adapter.py -v`
Expected: PASS（3 项）

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/source_adapter.py backend/app/core/source_registry.py backend/tests/test_source_adapter.py
git commit -m "feat(bank): pluggable SourceAdapter + tiku.cn stub registry"
```

### Task 6: 拍照 OCR → 结构化 `services/ocr_import.py`

**Files:**
- Create: `backend/app/services/ocr_import.py`
- Test: `backend/tests/test_ocr_import.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ocr_import.py
from app.services.ocr_import import structure_questions_from_text

def test_structure_fake_returns_empty():
    # fake provider 返回 "[fake] ..."，解析失败 → 空列表（不抛异常）
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        drafts = structure_questions_from_text(db, "这是一张卷子")
    finally:
        db.close()
    assert drafts == []

def test_structure_parses_json_list():
    from app.services.ocr_import import _parse_questions
    import json
    raw = json.dumps({"questions": [{"qtype": "single_choice", "question": "1+1=?", "options": [{"label": "2", "value": 0}], "answer_json": {"correct_index": 0}}]}, ensure_ascii=False)
    items = _parse_questions(raw)
    assert len(items) == 1
    assert items[0]["question"] == "1+1=?"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_ocr_import.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

```python
# backend/app/services/ocr_import.py
"""卷子拍照 → OCR 文字 → LLM 结构化 → list[QuestionDraft]。"""
import json

from ..core.source_adapter import OcrAdapter, QuestionDraft


def _parse_questions(raw: str) -> list[dict]:
    """解析 LLM 返回的 JSON，容错：直接数组 / {"questions": [...]} / 前缀包裹。"""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        qs = data.get("questions") or []
        return [x for x in qs if isinstance(x, dict)]
    return []


_STRUCTURE_SYSTEM = (
    "你是小学题库录入助手。根据 OCR 识别出的卷子文字，把每道题结构化成标准 JSON。\n"
    '只返回 JSON：{"questions":[{"qtype":"single_choice|multi_choice|true_false|fill_blank|'
    'cloze|calculation|matching|short_answer|essay|application|oral",'
    '"question":"题干","options":[{"label":"选项","value":0}],"answer_json":{...},"answer":"标准答案","analysis":"解析"}]}。\n'
    "options 仅选择题/连线题需要；answer_json 按题型填 correct_index / blanks / pairs / rubric。\n"
    "无法确定的题 qtype 填 short_answer。"
)


def structure_questions_from_text(db, ocr_text: str) -> list[QuestionDraft]:
    """OCR 文字 → LLM 结构化 → QuestionDraft 列表。任何异常回落空列表。"""
    from .ai import get_provider

    if not ocr_text or not ocr_text.strip():
        return []
    provider = get_provider(db)
    if provider.name == "fake":
        return []
    try:
        raw = provider.generate(
            prompt=f"卷子 OCR 文字：\n{ocr_text[:6000]}",
            system=_STRUCTURE_SYSTEM,
            json_mode=True,
        )
        items = _parse_questions(raw)
        return OcrAdapter().normalize({"questions": items})
    except Exception:
        return []
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_ocr_import.py -v`
Expected: PASS（2 项）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/ocr_import.py backend/tests/test_ocr_import.py
git commit -m "feat(bank): photo OCR to structured QuestionDraft"
```

---

## Phase 2：后端路由（题库 CRUD + 做题判分）

### Task 7: `routers/bank.py` 建卷/列卷/拉题/做题

**Files:**
- Create: `backend/app/routers/bank.py`
- Modify: `backend/app/main.py`（include_router）
- Test: `backend/tests/test_bank.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_bank.py
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from conftest import auth_headers, make_account

client = TestClient(app)


def _parent_headers():
    db = SessionLocal()
    p = make_account(db, "bank_parent", "parent")
    db.close()
    return auth_headers(p)


def test_create_bank(client, setup_db):
    h = _parent_headers()
    r = client.post("/api/banks", json={"title": "三年级数学期末卷", "subject": "数学", "grade": 3}, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] > 0

def test_list_banks(client, setup_db):
    h = _parent_headers()
    client.post("/api/banks", json={"title": "卷A", "subject": "数学"}, headers=h)
    r = client.get("/api/banks", headers=h)
    assert r.status_code == 200
    assert len(r.json()) >= 1
```

> 鉴权用 `conftest.auth_headers(user)`（签发 Bearer JWT，sub=用户 id），与 `test_questions_review.py` 一致。`client`、`setup_db` 均来自 `conftest.py` 既有 fixture。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_bank.py -v`
Expected: FAIL（路由不存在 / 404）

- [ ] **Step 3: 实现 router**

```python
# backend/app/routers/bank.py
"""独立题库/卷：建卷、列卷、拉题、做题判分。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import require_learning_user
from ..core.deps import get_current_user, require_role
from ..database import get_db
from ..models import Question, QuestionBank, User
from ..services.grade_question import grade_question, grade_subjective_with_ai

router = APIRouter(prefix="/api/banks", tags=["bank"])


class BankCreateReq(BaseModel):
    title: str
    subject: str = ""
    grade: int | None = None
    tags: dict = {}
    source: str = "manual"


class BankSubmitReq(BaseModel):
    bank_id: int | None = None
    answers: list[dict]   # [{question_id, selected_index|blanks|pairs|text}]


@router.post("")
def create_bank(req: BankCreateReq, user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    bank = QuestionBank(user_id=user.id, title=req.title.strip(), subject=req.subject,
                        grade=req.grade, tags=json.dumps(req.tags, ensure_ascii=False),
                        source=req.source)
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return {"id": bank.id, "title": bank.title}


@router.get("")
def list_banks(user: User = Depends(require_role("parent", "admin")),
               db: Session = Depends(get_db)):
    banks = db.query(QuestionBank).filter_by(user_id=user.id).order_by(QuestionBank.id.desc()).all()
    return [{"id": b.id, "title": b.title, "subject": b.subject, "grade": b.grade,
             "source": b.source, "status": b.status} for b in banks]


@router.get("/{bank_id}/questions")
def list_bank_questions(bank_id: int, _auth: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    qs = db.query(Question).filter_by(bank_id=bank_id, status="published").order_by(Question.id).all()
    return [{
        "id": q.id, "qtype": q.qtype, "qtype_category": q.qtype_category,
        "question": q.question, "options": json.loads(q.options or "[]"),
        "answer": q.answer, "analysis": q.analysis, "difficulty": q.difficulty,
        "tags": json.loads(q.tags or "{}"),
    } for q in qs]


@router.post("/submit")
def submit_bank(req: BankSubmitReq, user: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    qs = db.query(Question).filter(Question.id.in_([a.get("question_id") for a in req.answers])).all()
    by_id = {q.id: q for q in qs}
    results = []
    for a in req.answers:
        q = by_id.get(a.get("question_id"))
        if q is None:
            results.append({"question_id": a.get("question_id"), "is_correct": False})
            continue
        answer_json = json.loads(q.answer_json or "{}")
        student = {k: a.get(k) for k in ("selected_index", "blanks", "pairs", "text") if a.get(k) is not None}
        if q.qtype_category == "subjective":
            r = grade_subjective_with_ai(db, answer_json, student)
        else:
            r = grade_question(q.qtype_category, answer_json, student)
        results.append({"question_id": q.id, "is_correct": r["is_correct"],
                        "correct_answer_text": r["correct_answer_text"], "detail": r["detail"]})
    score = sum(1 for r in results if r["is_correct"] is True)
    return {"answers": results, "score": score, "total": len(results)}
```

在 `backend/app/main.py` 的 router include 区（找 `include_router` 处）追加：

```python
from app.routers import bank  # 顶部 import 区
app.include_router(bank.router)  # 与其他 include_router 并列
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_bank.py -v`
Expected: PASS（2 项）

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/bank.py backend/app/main.py backend/tests/test_bank.py
git commit -m "feat(bank): bank CRUD + submit grading router"
```

### Task 8: `add_question` 扩展富结构 + 审核流复用

> **实现注意（来自 Task 5 评审）**：`QuestionDraft`/`AddReq` 的 `qtype` 是 taxonomy 细值（`single_choice` 等），而 `Question.qtype_category`（`choice|blank|match|subjective`）须由 `CATEGORY_OF_QTYPE.get(qtype, "subjective")` 派生——下方 Step 3 已含此逻辑。另 `subject` 不在 `QuestionDraft`/`AddReq` 里、但 `Question.subject` 有列（默认 `""`），第一版可让 `add_question` 不设 `subject`（用默认 `""`），或从 `bank_id` 归属卷继承 `subject`——选后者更完整，但属增强；第一版默认 `""` 即可，本题库检索暂不依赖 subject。

**Files:**
- Modify: `backend/app/routers/questions.py`（`AddReq` 与 `add_question`）
- Test: `backend/tests/test_questions_review.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_questions_review.py` 追加（复用该文件顶部 `from conftest import auth_headers, make_account` 与 `client`）：

```python
def test_add_question_rich_structure(client, setup_db):
    db = SessionLocal()
    parent = make_account(db, "rich_parent", "parent")
    db.close()
    h = auth_headers(parent)
    body = {
        "lesson_id": None,
        "bank_id": None,
        "qtype": "single_choice",
        "question": "1+1=?",
        "options": [{"label": "2", "value": 0}, {"label": "1", "value": 1}],
        "answer_json": {"correct_index": 0},
        "answer": "2",
    }
    r = client.post("/api/questions", json=body, headers=h)
    assert r.status_code == 200
    qid = r.json()["id"]
    db = SessionLocal()
    q = db.get(Question, qid)
    db.close()
    assert q.qtype == "single_choice"
    assert q.qtype_category == "choice"
    assert q.status == "pending"  # 人工录入默认进审核队列
    assert "2" in q.options
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_questions_review.py::test_add_question_rich_structure -v`
Expected: FAIL（`AddReq` 不接受 `qtype`/`options`/`answer_json` 等新字段 → 422 Validation Error）

- [ ] **Step 3: 扩展 `AddReq` + `add_question`**

`AddReq` 替换为：

```python
class AddReq(BaseModel):
    lesson_id: int | None = None
    bank_id: int | None = None
    qtype: str = "short_answer"
    question: str
    answer: str = ""
    options: list[dict] = []
    answer_json: dict = {}
    analysis: str = ""
    difficulty: str = "medium"
    tags: dict = {}
```

`add_question` 函数体替换为：

```python
@router.post("")
def add_question(req: AddReq, _auth: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="题目内容不能为空")
    from ..core.question_types import CATEGORY_OF_QTYPE
    category = CATEGORY_OF_QTYPE.get(req.qtype, "subjective")
    q = Question(
        lesson_id=req.lesson_id,
        bank_id=req.bank_id,
        qtype=req.qtype,
        qtype_category=category,
        question=question,
        answer=req.answer.strip(),
        answer_json=json.dumps(req.answer_json, ensure_ascii=False),
        options=json.dumps(req.options, ensure_ascii=False),
        analysis=req.analysis.strip(),
        difficulty=req.difficulty,
        tags=json.dumps(req.tags, ensure_ascii=False),
        status="pending",  # 人工录入默认进审核队列
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return {"id": q.id}
```

> 注意：`questions.py` 顶部需 `import json`（若尚未引入）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_questions_review.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/questions.py backend/tests/test_questions_review.py
git commit -m "feat(bank): extend add_question with rich structure"
```

---

## Phase 3：前端（parent-web + Flutter）

> 前端阶段没有自动化测试框架（`parent-web` 是原生 JS，Flutter 用 `flutter test`）。验收方式改为：后端起来后手动走通「建卷 → 录入 → 审核 → 拉题做题」，Flutter 用 `flutter analyze && flutter test`。此阶段任务粒度适当放大，每个任务仍独立可提交。

### Task 9: parent-web 题库管理页（建卷 + 录入）

**Files:**
- Modify: `parent-web/index.html`（新增导航项）
- Modify: `parent-web/app.js`（新增 `renderBankManage` 等）

- [ ] **Step 1:** 在 `index.html` 侧边导航加一项「题库管理」，触发 `renderBankManage()`。

- [ ] **Step 2:** 在 `app.js` 加 `renderBankManage()`：顶部「新建卷」表单（标题/学科/年级）+ 卷列表（调 `GET /api/banks`）；点某卷进入「录入题目」表单，支持题型下拉（复用 `QTYPE_LABEL` 中文名，加一个 taxonomy 到 label 的映射）与按题型动态字段（单选/多选/判断/填空/连线/简答/作文）。提交调 `POST /api/questions`。

- [ ] **Step 3:** 手动验证（后端起来后）：建卷成功 → 录入一道单选题成功 → `GET /api/banks/{id}/questions` 能在审核通过后看到它。

- [ ] **Step 4: 提交**

```bash
git add parent-web/index.html parent-web/app.js
git commit -m "feat(parent-web): question bank manage page (create bank + add question)"
```

### Task 10: parent-web 审核页多题型预览

**Files:**
- Modify: `parent-web/app.js`（扩展 `QTYPE_LABEL` + 审核渲染）

- [ ] **Step 1:** 扩展 `QTYPE_LABEL`：新增 taxonomy 值到中文名映射（或复用后端同一份，前端写死一份中文表）。

- [ ] **Step 2:** 审核卡片（`reviewGroups` 渲染处）按 `qtype` 展示：选择题显示选项列表、填空题显示答案、主观题显示解析；`approve`/`reject` 按钮保持原逻辑。

- [ ] **Step 3:** 手动验证：录入一道选择题 → 审核页能看到选项与答案 → approve 后 `GET /api/banks/{id}/questions` 能拉到。

- [ ] **Step 4: 提交**

```bash
git add parent-web/app.js
git commit -m "feat(parent-web): multi-type preview in review page"
```

### Task 11: Flutter 学生端「题库练习」

**Files:**
- Create: `student-app/lib/features/bank_exercise/bank_exercise_page.dart`（+ 按需拆 widget）
- Modify: `student-app/lib/core/router.dart`（注册路由/入口）
- Test: `student-app/test/bank_exercise_test.dart`

- [ ] **Step 1:** 写失败测试：`flutter test` 断言「题库练习」页能渲染题干与选项。

- [ ] **Step 2:** 实现 `BankExercisePage`：调 `GET /api/banks/{id}/questions` 拉题 → 按 `qtype` 渲染控件（单选 RadioListTile / 多选 CheckboxListTile / 填空 TextField / 连线省略为下拉配对 / 简答作文多行 TextField）→ 提交 `POST /api/banks/submit` → 展示判分结果。

- [ ] **Step 3:** `flutter analyze && flutter test` 通过。

- [ ] **Step 4: 提交**

```bash
git add student-app/lib/features/bank_exercise student-app/lib/core/router.dart student-app/test/bank_exercise_test.dart
git commit -m "feat(student-app): bank exercise page"
```

---

## 自检（写完后自查，无需重跑）

- [ ] **Spec 覆盖**：§1 taxonomy→Task1、富答案→Task2/8、判分路由→Task3/4、§2 独立题库→Task2/7、三来源→Task5/6/8、§3 做题闭环→Task7/11、纳入每日任务（P2）→ 未实现（spec 明确 P2，可留）、§6 迁移→Task2/8 的 LEGACY_QTYPE_MAP 已定义但未跑迁移脚本（见下方「遗留」）。
- [ ] **类型一致**：`grade_question`/`grade_subjective_with_ai`/`grade_question` 的签名、`QuestionDraft` 字段、`SOURCE_REGISTRY` 键名在各任务间一致。
- [ ] **无占位**：每个 code step 都有完整代码块；唯一「需对照既有 fixture」的是测试鉴权（已显式标注读哪些文件），非占位。

## 遗留（明确不做，避免计划外蔓延）

1. **旧数据迁移脚本**：`LEGACY_QTYPE_MAP` 常量已定义，但「把库里旧 4 值 `qtype` 批量更新为 taxonomy 值」的迁移脚本不在本计划。现有旧数据 `answer_json` 为空、判分回落「仅展示/人工批改」，功能不破。如需，另行一个 data-migration 任务。
2. **拍照上传端点**：`OcrAdapter`/`ocr_import` 已就绪，但「家长端上传照片 → 调 `ocr_image` → 结构化落库」的 HTTP 端点（如 `POST /api/banks/photo-import`）不在本计划——它依赖 vision 模型配置与上传落盘，留作后续任务（或实现时若你有 vision 配置再加）。
3. **第三方 tiku.cn 真实接入**：占位 stub，需爬虫/授权信息后续确认。
4. **「纳入每日任务」抽取规则**：spec 标 P2，本计划未展开 `task_gen` 的抽取逻辑。
