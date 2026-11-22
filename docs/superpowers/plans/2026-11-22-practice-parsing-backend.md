# 练习册解析重构 · 计划一（后端）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把练习册 PDF 解析从「行级正则 + 答案页对齐」重建为「整页视觉分析 → 题组/小题两级 → 跨页合并 → AI 求答案 → 按 `answer_kind` 判分」。

**Architecture:** 每页一次 `ai.vision_json()` 返回 `{page_type, groups[], image_questions[]}`；全书扫完统一跨页合并；题组先入库、小题后挂（`Question.group_id`）；判分由 `math_grade.grade_by_answer_kind()` 唯一实现按 `answer_kind` 分派，`practice_grade.grade_practice_item()` 只是取字段的薄包装。

**Tech Stack:** FastAPI + SQLAlchemy 2.x（Mapped 风格）、SQLite（本地）/ MySQL 8.4（部署）、pytest、`openai` SDK 直连视觉模型。

**Spec:** `docs/superpowers/specs/2026-11-22-practice-parsing-redesign.md`

---

## Task 0: 测试脚手架约定（先读，不改代码）

**这一节不是任务，是所有后续任务的硬约束。写测试前必须遵守，否则测试跑不起来。**

**1) 用 `db` 拿 Session，不要用 `setup_db`**

`backend/tests/conftest.py:27-34` 的 `setup_db` 是 `autouse` fixture，它 **`yield` 出 `None`**
——只负责每例前后 drop/create 表。真正可用的 Session 是 `db` fixture（`conftest.py:41-44`）。

```python
# ❌ 错：AttributeError: 'NoneType' object has no attribute 'add'
def test_x(setup_db):
    setup_db.add(...)

# ✅ 对：两个都声明
def test_x(setup_db, db):
    db.add(...)
```

**2) 从 `conftest` 直接 import，不要写 `tests.conftest`**

`backend/tests/` 没有 `__init__.py`，且 site-packages 里有同名 `tests` 包会遮蔽。
仓库惯例是 `from conftest import ...`（见 `test_bank.py:7`）。

```python
from conftest import auth_headers, make_account, parent_child   # ✅
from tests.conftest import make_account                          # ❌ ImportError
```

**3) 需要「孩子可作答」的接口，用 `parent_child`**

`require_learning_user` 会校验孩子已绑定家长。`make_account(session, "x", role="child")`
不设 `parent_id` → 403。用 `parent_child(db)` 拿三元组：

```python
parent, child, parent_h, child_h = parent_child(db)
```

**4) 测试命令**

```bash
cd backend && python -m pytest tests/test_xxx.py -v
```

---

## 环境前提（每一步都适用）

1. **必须从 `backend/` 目录运行**，否则 `DATABASE_URL=sqlite:///./zhixueban.db` 会指向错误路径生成空库。
2. 本轮**只改后端**，不动 `student-app/` 与 `parent-web/`（那两个属于计划二）。
3. **不写数据清理进迁移**。旧练习册数据由家长端点「重新导入」显式触发删除。
4. `run_import_job` 内是**函数内 import**（`from .parsers.math_page import analyze_page`）。
   patch 时**必须用完整模块路径字符串**，不能 patch `practice_import.analyze_page`（那不是模块属性）：
   ```python
   monkeypatch.setattr("app.services.parsers.math_page.analyze_page", fake)   # ✅
   monkeypatch.setattr(pi, "analyze_page", fake, raising=False)               # ❌ 无效
   ```

---

## File Structure

**新建**

| 文件 | 职责 |
| --- | --- |
| `backend/app/core/work_modes.py` | `WorkModeSpec` + 14 个数学题型注册表 + 查表函数 |
| `backend/app/core/subjects.py` | `SubjectSpec` 学科注册表（数学实现，语文/英语占位） |
| `backend/app/services/parsers/__init__.py` | 包标记 |
| `backend/app/services/parsers/math_page.py` | 数学整页分析：提示词 + JSON 规范化（纯函数）+ 调 `ai.vision_json` |
| `backend/app/services/math_grade.py` | `grade_by_answer_kind()`，唯一一份按 `answer_kind` 分派的判分 |
| `backend/app/services/practice_grade.py` | `grade_practice_item()`，从 ORM 对象取字段的薄包装 |
| `backend/app/migrate_practice_groups.py` | 幂等 schema 迁移（建表靠 `schema_sync`，这里补列与索引） |
| `backend/tests/test_work_modes.py` | 注册表完整性 |
| `backend/tests/test_math_page_parser.py` | 页面分析 JSON 规范化 |
| `backend/tests/test_merge_groups.py` | 跨页合并 |
| `backend/tests/test_math_grade.py` | 判分分派 |
| `backend/tests/test_practice_groups.py` | 题组入库 / 发布闸门 / 格式标记 / 路由 |

**修改**

| 文件 | 改动 |
| --- | --- |
| `backend/app/models.py` | 新增 `PracticeQuestionGroup`、`PracticeImportPage`；`Question` 加 4 列 |
| `backend/app/core/source_adapter.py` | `QuestionDraft` 加 4 字段 |
| `backend/app/services/ai.py` | 新增 `vision_json()` |
| `backend/app/services/practice_image.py` | 新增公开 `render_page_png()`；删除 `detect_image_questions()` |
| `backend/app/services/practice_import.py` | 重写编排；`_strip_answer` 感知 `$`；`build_drafts` 写 `answer_json`；新增 `merge_cross_page_groups` |
| `backend/app/services/practice_solve.py` | `solve_math_items` 返回 `dict[int, dict]` |
| `backend/app/routers/bank.py` | `_persist_drafts` 透传 4 字段；`POST /submit` 分派；题目列表返回题组信息 |
| `backend/app/routers/practice_import.py` | 题组浏览、页类型查询/修改、答案页可选、学科校验、`_derive_page_range` |
| `backend/app/routers/pdf.py` | 删文档时显式清理题组/页记录/小题（无外键级联） |
| `backend/app/services/task_gen.py` | 抽题排除示例、带出题组题干 |
| `backend/app/services/ocr_import.py` | `content` 白名单补 `$...$`；draft 带 `work_mode` |
| `backend/app/main.py` | 启动跑新迁移；`q_end` 派生修正 |

---

## Task 1: 题型注册表 `work_modes.py`

**Files:**
- Create: `backend/app/core/work_modes.py`
- Test: `backend/tests/test_work_modes.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_work_modes.py
"""题型注册表完整性：每个数学 mode 的字段都必须合法。"""
import pytest

from app.core.question_types import CATEGORY_OF_QTYPE
from app.core.work_modes import (
    ANSWER_KINDS,
    INPUT_UIS,
    MATH_WORK_MODES,
    REGISTRY,
    answer_kind_of,
    input_ui_of,
    legacy_qtype_of,
    spec_of,
)


def test_registry_ids_unique_and_ordered():
    ids = [m.id for m in MATH_WORK_MODES]
    assert len(ids) == len(set(ids))
    assert ids[0] == "oral" and ids[-1] == "other"


def test_every_spec_has_valid_fields():
    for m in MATH_WORK_MODES:
        assert m.answer_kind in ANSWER_KINDS, m
        assert m.input_ui in INPUT_UIS, m
        # legacy_qtype 必须能被既有 taxonomy 认识，否则 qtype_category 会退成 subjective
        assert m.legacy_qtype in CATEGORY_OF_QTYPE, m
        assert m.label


def test_lookup_never_raises_and_falls_back_to_other():
    assert answer_kind_of("oral") == "number"
    assert input_ui_of("vertical") == "camera"
    assert legacy_qtype_of("equation") == "fill_blank"


@pytest.mark.parametrize("bad", ["", None, "  ", "no_such_mode"])
def test_unknown_mode_falls_back(bad):
    assert spec_of(bad).id == "other"


def test_photo_kinds_map_to_camera():
    """photo answer_kind 必须配 camera，否则前端没有拍照入口。"""
    for m in MATH_WORK_MODES:
        if m.answer_kind == "photo":
            assert m.input_ui == "camera", m


def test_all_fourteen_modes_present():
    assert len(REGISTRY) == 14
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_work_modes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.work_modes'`

- [ ] **Step 3: 写实现**

```python
# backend/app/core/work_modes.py
"""题型注册表：answer_kind（判分方式）+ input_ui（前端交互）。

仿 `provider_registry` 的声明式写法。新增题型只加一行 `WorkModeSpec`，
判分按 `answer_kind` 分派、前端按 `input_ui` 渲染，两侧都不用改代码。
"""
from dataclasses import dataclass

# 判分方式（math_grade.grade_by_answer_kind 的分派键）
ANSWER_KINDS = ("number", "numeric_list", "symbol", "choice", "text", "photo")
# 前端交互形态
INPUT_UIS = ("keypad", "chooser", "camera")


@dataclass(frozen=True)
class WorkModeSpec:
    id: str            # oral | step | compare | ...
    label: str         # 口算 | 脱式/简算 | 比较大小
    answer_kind: str   # 见 ANSWER_KINDS
    input_ui: str      # 见 INPUT_UIS
    legacy_qtype: str  # 映射到 Question.qtype，复用既有 taxonomy


MATH_WORK_MODES: tuple[WorkModeSpec, ...] = (
    WorkModeSpec("oral", "口算", "number", "keypad", "oral"),
    WorkModeSpec("vertical", "竖式", "photo", "camera", "calculation"),
    WorkModeSpec("step", "脱式/简算", "photo", "camera", "calculation"),
    WorkModeSpec("equation", "解方程", "number", "keypad", "fill_blank"),
    WorkModeSpec("pattern", "找规律", "numeric_list", "keypad", "fill_blank"),
    WorkModeSpec("compare", "比较大小", "symbol", "chooser", "fill_blank"),
    WorkModeSpec("unit_compare", "单位换算比较", "symbol", "chooser", "fill_blank"),
    WorkModeSpec("fill_vertical", "填空竖式", "photo", "camera", "calculation"),
    WorkModeSpec("letter_pattern", "字母规律", "numeric_list", "keypad", "fill_blank"),
    WorkModeSpec("geometry", "图形题", "photo", "camera", "application"),
    WorkModeSpec("app", "应用题", "photo", "camera", "application"),
    WorkModeSpec("choice", "选择题", "choice", "chooser", "single_choice"),
    WorkModeSpec("judge", "判断题", "choice", "chooser", "true_false"),
    WorkModeSpec("other", "其他/未识别", "text", "keypad", "short_answer"),
)

REGISTRY: dict[str, WorkModeSpec] = {m.id: m for m in MATH_WORK_MODES}

# 兜底 id：未知题型一律归这里，绝不抛异常
FALLBACK_ID = "other"


def spec_of(work_mode: str | None) -> WorkModeSpec:
    """查不到（空串/None/未知）一律回落 other。"""
    return REGISTRY.get((work_mode or "").strip(), REGISTRY[FALLBACK_ID])


def answer_kind_of(work_mode: str | None) -> str:
    return spec_of(work_mode).answer_kind


def input_ui_of(work_mode: str | None) -> str:
    return spec_of(work_mode).input_ui


def legacy_qtype_of(work_mode: str | None) -> str:
    return spec_of(work_mode).legacy_qtype
```

> **为什么 `other` 必须是 `text`**：未知题型的判分方式是「参考答案文本」，走既有
> 主观题判分；若硬塞成 `number` 会因格式不符永远判错。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_work_modes.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/work_modes.py backend/tests/test_work_modes.py
git commit -m "feat(practice): 新增题型注册表 work_modes（14 种数学题型）"
```

---

## Task 2: 学科注册表 `subjects.py`

**Files:**
- Create: `backend/app/core/subjects.py`
- Test: `backend/tests/test_work_modes.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
# backend/tests/test_work_modes.py 末尾追加
from app.core.subjects import SUBJECTS, is_implemented
from app.core.subjects import spec_of as subject_spec


def test_math_subject_covers_registry_exactly():
    """数学学科声明的题型必须与 work_modes 注册表完全一致（不多不少）。"""
    math = SUBJECTS["数学"]
    assert set(math.work_mode_ids) == set(REGISTRY)


def test_placeholder_subjects_are_marked_unimplemented():
    for name in ("语文", "英语"):
        assert SUBJECTS[name].implemented is False
        assert is_implemented(name) is False


def test_math_is_implemented():
    assert is_implemented("数学") is True


def test_unknown_subject_falls_back_to_math():
    assert subject_spec("").id == "数学"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_work_modes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.subjects'`

- [ ] **Step 3: 写实现**

```python
# backend/app/core/subjects.py
"""学科注册表：每个学科用哪个页面解析器、支持哪些题型。

本期只有数学实现；语文/英语仅占位，上传时由路由返回 400。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SubjectSpec:
    id: str
    label: str
    parser_id: str                  # 该学科用哪个页面解析器
    work_mode_ids: tuple[str, ...]  # 该学科可用的题型（来自 work_modes 注册表）
    implemented: bool = True


SUBJECTS: dict[str, SubjectSpec] = {
    "数学": SubjectSpec(
        "数学", "数学", "math_page",
        ("oral", "vertical", "step", "equation", "pattern", "compare",
         "unit_compare", "fill_vertical", "letter_pattern", "geometry",
         "app", "choice", "judge", "other"),
    ),
    # 以下本期不实现，仅占位表明扩展点。work_mode_ids 里的 id 尚未注册到
    # work_modes（等实现语文/英语时一起加），因此「注册表完整性」测试只校验数学。
    "语文": SubjectSpec(
        "语文", "语文", "text_page",
        ("pinyin", "dictation", "fill_blank", "reading", "comprehension", "other"),
        implemented=False,
    ),
    "英语": SubjectSpec(
        "英语", "英语", "text_page",
        ("word_spelling", "listening", "cloze", "reading", "choice", "other"),
        implemented=False,
    ),
}


def spec_of(subject: str | None) -> SubjectSpec:
    """未知/空学科回落数学（练习册默认数学）。"""
    return SUBJECTS.get((subject or "").strip(), SUBJECTS["数学"])


def is_implemented(subject: str | None) -> bool:
    return spec_of(subject).implemented
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_work_modes.py -v`
Expected: PASS（11 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/subjects.py backend/tests/test_work_modes.py
git commit -m "feat(practice): 新增学科注册表 subjects（数学实现，语文英语占位）"
```

---

## Task 3: 数据模型与迁移

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/migrate_practice_groups.py`
- Test: `backend/tests/test_practice_groups.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_practice_groups.py
"""题组两级模型：表结构、可空性、迁移幂等。"""
from sqlalchemy import inspect

from app.models import PracticeQuestionGroup, Question
from conftest import make_user


def test_new_tables_registered(setup_db, db):
    names = set(inspect(db.get_bind()).get_table_names())
    assert "practice_question_groups" in names
    assert "practice_import_pages" in names


def test_question_has_group_columns(setup_db, db):
    cols = {c["name"] for c in inspect(db.get_bind()).get_columns("questions")}
    assert {"group_id", "seq_in_group", "is_example", "work_mode"} <= cols


def test_group_lesson_no_is_nullable(setup_db, db):
    """综合练习页没有「第N课时」，lesson_no 必须允许 NULL。"""
    cols = {c["name"]: c for c in inspect(db.get_bind()).get_columns(
        "practice_question_groups")}
    assert cols["lesson_no"]["nullable"] is True


def test_group_columns_defaults(setup_db, db):
    from app.models import QuestionBank

    user = make_user(db)
    bank = QuestionBank(user_id=user.id, title="练习册", subject="数学",
                        grade=5, source="practice_pdf")
    db.add(bank)
    db.flush()
    g = PracticeQuestionGroup(bank_id=bank.id, user_id=user.id,
                              stem="直接写出得数", work_mode="oral",
                              page_start=1, page_end=1)
    db.add(g)
    db.flush()
    assert g.need_process is False
    assert g.incomplete is False
    assert g.instruction == ""
    assert g.lesson_title == ""
    assert g.lesson_no is None


def test_migration_is_idempotent():
    """连跑两次不报错（列/索引已存在时跳过）。"""
    from app.migrate_practice_groups import migrate

    migrate()
    migrate()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -v`
Expected: FAIL — `ImportError: cannot import name 'PracticeQuestionGroup'`

- [ ] **Step 3: 加模型**

在 `backend/app/models.py` 里 `PracticeImportJob` 类之后追加：

```python
class PracticeQuestionGroup(Base):
    """练习册题组：一段题干 + 若干小题（跨页合并后的结果）。

    `Question.group_id` 是裸 INTEGER（不声明外键/CASCADE）：存量库不补外键、
    SQLite 默认不校验，统一在代码里显式删除，保证新旧库行为一致。
    """
    __tablename__ = "practice_question_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # 页面无「第N课时」标题时为 None（如综合练习页）
    lesson_no: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    lesson_title: Mapped[str] = mapped_column(String(128), default="")
    stem: Mapped[str] = mapped_column(LongText, default="")         # 题干（可含有限标记）
    instruction: Mapped[str] = mapped_column(LongText, default="")  # 引导语/说明
    work_mode: Mapped[str] = mapped_column(String(24), default="oral")
    need_process: Mapped[bool] = mapped_column(Boolean, default=False)
    page_start: Mapped[int] = mapped_column(Integer, default=0)
    page_end: Mapped[int] = mapped_column(Integer, default=0)
    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("pdf_documents.id", ondelete="SET NULL"), nullable=True)
    incomplete: Mapped[bool] = mapped_column(Boolean, default=False)  # 跨页合并不确定
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PracticeImportPage(Base):
    """导入时按页记录分析结果，供排查与手动修正页类型。"""
    __tablename__ = "practice_import_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("pdf_documents.id"), index=True)
    page_no: Mapped[int] = mapped_column(Integer)
    page_type: Mapped[str] = mapped_column(String(16), default="practice")
    raw_text: Mapped[str] = mapped_column(LongText, default="")  # 该页 AI 原始输出
    group_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok | failed
```

在 `Question` 类里（`image_path` 之后）追加 4 列：

```python
    # 练习册题组：group_id 是裸 INTEGER（不加外键/CASCADE，见 PracticeQuestionGroup 注释）
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seq_in_group: Mapped[int] = mapped_column(Integer, default=0)
    is_example: Mapped[bool] = mapped_column(Boolean, default=False)  # 示例行，不入待做
    work_mode: Mapped[str] = mapped_column(String(24), default="")
```

在 `Question.__table_args__` 里追加索引：

```python
    __table_args__ = (
        Index("ix_questions_bank_lesson", "bank_id", "lesson_no"),
        Index("ix_questions_group", "group_id", "seq_in_group"),
    )
```

- [ ] **Step 4: 写迁移**

```python
# backend/app/migrate_practice_groups.py
"""存量库补列与索引（练习册题组两级模型）。

新表由 `main.py` 启动时的 `schema_sync(engine, Base.metadata)` 创建；
`schema_sync` 只补列不补索引，所以这里显式建索引。
每步独立 try/except，保证幂等（列/索引已存在时跳过）。

⚠️ 本迁移**只做 schema 变更，绝不删数据**。
`DELETE FROM questions WHERE source_document_id IS NOT NULL` 这类清理若写进
启动迁移，每次重启都会清空练习册题目。清旧数据是一次性动作，由家长端
「重新导入」按钮显式触发。
"""
import logging

from sqlalchemy import text

from .database import engine

_log = logging.getLogger("uvicorn.error")

_STATEMENTS: list[tuple[str, str]] = [
    ("group_id", "ALTER TABLE questions ADD COLUMN group_id INTEGER"),
    ("seq_in_group", "ALTER TABLE questions ADD COLUMN seq_in_group INTEGER DEFAULT 0"),
    ("is_example", "ALTER TABLE questions ADD COLUMN is_example BOOLEAN DEFAULT 0"),
    ("work_mode", "ALTER TABLE questions ADD COLUMN work_mode VARCHAR(24) DEFAULT ''"),
    (
        "ix_questions_group",
        "CREATE INDEX ix_questions_group ON questions (group_id, seq_in_group)",
    ),
    (
        "ix_pqg_bank",
        "CREATE INDEX ix_pqg_bank ON practice_question_groups (bank_id)",
    ),
]


def migrate() -> None:
    for name, sql in _STATEMENTS:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception as exc:  # noqa: BLE001
            # 已存在（SQLite/MySQL 报错文案不同）或表还没建：记日志继续
            _log.info("题组迁移跳过 %s: %s", name, str(exc)[:120])


if __name__ == "__main__":
    migrate()
    print("练习册题组迁移完成")
```

- [ ] **Step 5: 挂到启动钩子**

`backend/app/main.py` 里，在 `_migrate_practice_import()` 那段之后追加：

```python
        try:
            from .migrate_practice_groups import migrate as _migrate_practice_groups

            _migrate_practice_groups()
        except Exception as exc:
            _log.warning("练习册题组迁移失败: %s", exc)
```

- [ ] **Step 6: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -v`
Expected: PASS（5 passed）

- [ ] **Step 7: 跑全量回归**

Run: `cd backend && python -m pytest -q`
Expected: 全部 PASS（此前 645+ 条）

- [ ] **Step 8: 提交**

```bash
git add backend/app/models.py backend/app/migrate_practice_groups.py backend/app/main.py backend/tests/test_practice_groups.py
git commit -m "feat(practice): 题组两级模型（PracticeQuestionGroup/PracticeImportPage + Question 4 列）"
```

---

## Task 4: `QuestionDraft` 与 `_persist_drafts` 透传

**Files:**
- Modify: `backend/app/core/source_adapter.py:6-24`
- Modify: `backend/app/routers/bank.py:107-165`（`_persist_drafts`）、`:177`（`_dict_to_draft`）
- Test: `backend/tests/test_practice_groups.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_practice_groups.py 末尾追加
def test_persist_drafts_writes_group_fields(setup_db, db):
    from app.core.source_adapter import QuestionDraft
    from app.models import Question, QuestionBank
    from app.routers.bank import _persist_drafts
    from conftest import make_user

    user = make_user(db)
    bank = QuestionBank(user_id=user.id, title="练习册", subject="数学",
                        grade=5, source="practice_pdf")
    db.add(bank)
    db.flush()

    g = PracticeQuestionGroup(bank_id=bank.id, user_id=user.id,
                              stem="直接写出得数", work_mode="pattern",
                              page_start=3, page_end=3)
    db.add(g)
    db.flush()

    d = QuestionDraft(qtype="fill_blank", question="1+1=____", answer="2")
    d.group_id = g.id
    d.seq_in_group = 2
    d.is_example = True
    d.work_mode = "pattern"
    _persist_drafts(db, bank, [d], "practice_pdf")
    db.commit()

    row = db.query(Question).filter_by(bank_id=bank.id).one()
    assert row.group_id == g.id
    assert row.seq_in_group == 2
    assert row.is_example is True
    assert row.work_mode == "pattern"


def test_dict_to_draft_keeps_practice_fields():
    """草稿预览→确认导入不能丢练习册字段。"""
    from app.routers.bank import _dict_to_draft

    d = _dict_to_draft({
        "qtype": "fill_blank", "question": "1+1=____", "answer": "2",
        "lesson_no": 5, "question_no": "3", "image_path": "uploads/x.png",
        "group_id": 11, "seq_in_group": 2, "is_example": True,
        "work_mode": "pattern",
    })
    assert d.lesson_no == 5
    assert d.image_path == "uploads/x.png"
    assert d.group_id == 11
    assert d.is_example is True
    assert d.work_mode == "pattern"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k "group_fields or dict_to_draft" -v`
Expected: FAIL — `AttributeError: 'QuestionDraft' object has no attribute 'group_id'`

- [ ] **Step 3: 加字段到 `QuestionDraft`**

`backend/app/core/source_adapter.py`，在 `image_path` 之后追加：

```python
    # 练习册题组：小题挂到题组下，示例行不入待做
    group_id: int | None = None
    seq_in_group: int = 0
    is_example: bool = False
    work_mode: str = ""
```

- [ ] **Step 4: 在 `_persist_drafts` 里透传**

`backend/app/routers/bank.py`，`Question(...)` 构造里 `image_path=` 之后追加：

```python
            group_id=d.group_id,
            seq_in_group=d.seq_in_group,
            is_example=d.is_example,
            work_mode=d.work_mode,
```

- [ ] **Step 5: 修 `_dict_to_draft` 丢字段**

`bank.py:181` 的 `_dict_to_draft` 现在逐字段手写回填，会丢练习册字段。

⚠️ **注意它不只是「过滤字段」**：真实签名为 `(item: dict) -> QuestionDraft | None`，
且有两个既有行为必须保留（`POST /import-drafts` 的调用方 `:541` 靠 `if d:` 过滤空条目）：

1. 非 dict 条目 → 返回 `None`
2. `question` 为空 → 返回 `None`
3. 基础字段归一化（`qtype` 默认 `short_answer`、`answer`/`analysis` 等 `strip()`）

所以**不能**换成裸的三行版本。正确做法是「先按 dataclass 字段名透传，再覆盖归一化」：

```python
def _dict_to_draft(item: dict) -> QuestionDraft | None:
    if not isinstance(item, dict):
        return None
    q = (item.get("question") or "").strip()
    if not q:
        return None
    # 先按 dataclass 字段名透传全部字段（避免漏字段），再对基础字段做归一化
    allowed = {f.name for f in fields(QuestionDraft)}
    base = {k: v for k, v in item.items() if k in allowed}
    base.update(
        qtype=(item.get("qtype") or "short_answer").strip(),
        question=q,
        options=item.get("options") or [],
        answer_json=item.get("answer_json") or {},
        answer=(item.get("answer") or "").strip(),
        analysis=(item.get("analysis") or "").strip(),
        difficulty=(item.get("difficulty") or "medium"),
        tags=item.get("tags") if isinstance(item.get("tags"), dict) else {},
        passage_title=(item.get("passage_title") or "").strip(),
        passage_content=(item.get("passage_content") or "").strip(),
    )
    return QuestionDraft(**base)
```

`bank.py` 顶部把已有的 `from dataclasses import asdict` 改成 `from dataclasses import asdict, fields`。

- [ ] **Step 6: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -v`
Expected: PASS（7 passed）

- [ ] **Step 7: 跑 bank 回归**

Run: `cd backend && python -m pytest -q -k "bank or draft"`
Expected: 全部 PASS

- [ ] **Step 8: 提交**

```bash
git add backend/app/core/source_adapter.py backend/app/routers/bank.py backend/tests/test_practice_groups.py
git commit -m "feat(practice): QuestionDraft 与 _persist_drafts 透传题组字段"
```

---

## Task 5: `ai.vision_json()`（图片 + JSON）

**Files:**
- Modify: `backend/app/services/ai.py`
- Test: `backend/tests/test_practice_groups.py`（追加）

**背景（已核实）**：`AIProvider.generate(prompt, system, json_mode)` **只收文本**，
没有图片入参；`ocr_image(db, image_bytes, instruction)` 能带图但**不支持 `json_mode`
也不接受 `system`**。整页分析两者都要，所以新增一个平行函数。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_practice_groups.py 末尾追加
import pytest


def test_vision_json_requires_configured_endpoint(setup_db, db):
    """未配置中转站时必须明确报错，而不是静默返回空串。"""
    import app.services.ai as ai_mod

    ai_mod.resolve = lambda *a, **k: type("R", (), {
        "api_key": "", "base_url": "", "options": {},
    })()
    with pytest.raises(RuntimeError):
        ai_mod.vision_json(db, b"\x89PNG", system="sys", prompt="p")


def test_vision_json_sends_json_mode_and_system(setup_db, db, monkeypatch):
    """断言：带 system 消息 + response_format=json_object + 图片。"""
    import app.services.ai as ai_mod

    captured = {}

    class _FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)

            class _Resp:
                choices = [type("C", (), {
                    "message": type("M", (), {"content": '{"page_type":"practice"}'})(),
                })()]

            return _Resp()

    class _FakeClient:
        def __init__(self, **kw):
            captured["client_kwargs"] = kw
            self.chat = type("C", (), {"completions": _FakeCompletions()})()

    monkeypatch.setattr(ai_mod, "_openai_client", lambda **kw: _FakeClient(**kw))
    monkeypatch.setattr(ai_mod, "resolve", lambda *a, **k: type("R", (), {
        "api_key": "k", "base_url": "http://x",
        "options": {"vision_model": "vl"},
    })())

    out = ai_mod.vision_json(db, b"\x89PNG", system="SYS", prompt="PROMPT")
    assert out.startswith("{")
    assert captured["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in captured["messages"]] == ["system", "user"]
    parts = captured["messages"][1]["content"]
    assert any(p.get("type") == "image_url" for p in parts)
    assert captured["model"] == "vl"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k vision_json -v`
Expected: FAIL — `AttributeError: module 'app.services.ai' has no attribute 'vision_json'`

- [ ] **Step 3: 写实现**

`backend/app/services/ai.py`：顶部补 `from .model_config import resolve`（模块级，
测试要 patch 它），末尾追加：

```python
def _openai_client(**kwargs):
    """薄封装，便于测试替换（避免真的建网络客户端）。"""
    from openai import OpenAI

    return OpenAI(**kwargs)


def vision_json(
    db: Session,
    image_bytes: bytes,
    system: str,
    prompt: str,
    *,
    timeout: float | None = None,
) -> str:
    """视觉模型 + JSON 输出。整页分析 / 图片题求答案用。

    与 `ocr_image` 的区别：带 system 消息、要求 `response_format=json_object`、有超时。
    与 `AIProvider.generate` 的区别：能带图片（后者只收文本）。

    未配置中转站时抛 RuntimeError（不静默返回空串，避免调用方把空当"无题目"）。
    """
    import base64

    r = resolve(db, "llm")
    vision_model = r.options.get("vision_model", "")
    if not vision_model:
        from ..models import ModelConfig

        row = db.query(ModelConfig).filter_by(key="vision_model").first()
        vision_model = row.value if row else "qwen3-vl-plus"
    if not r.api_key or not r.base_url:
        raise RuntimeError("中转站 API Key / Base URL 未配置，无法做视觉分析")

    client = _openai_client(
        api_key=r.api_key, base_url=r.base_url,
        timeout=timeout or 600.0, max_retries=0,
    )
    b64 = base64.b64encode(image_bytes).decode()
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({
        "role": "user",
        "content": [
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": prompt},
        ],
    })
    resp = client.chat.completions.create(
        model=vision_model,
        messages=messages,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""
```

> `ocr_image` 里原本那处函数内 `from .model_config import resolve` 可以保留（局部
> import 遮蔽模块级同名不受影响），也可删掉改用模块级——两者等价。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k vision_json -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/ai.py backend/tests/test_practice_groups.py
git commit -m "feat(practice): 新增 ai.vision_json（图片 + JSON + system）"
```

---

## Task 6: 数学整页分析器 `parsers/math_page.py`

**Files:**
- Create: `backend/app/services/parsers/__init__.py`
- Create: `backend/app/services/parsers/math_page.py`
- Test: `backend/tests/test_math_page_parser.py`

**设计要点**：`parse_page_analysis(raw) -> dict` 是**纯函数**（好测），
`analyze_page(db, image_bytes, subject) -> dict` 负责调 `vision_json` 再交给它。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_math_page_parser.py
"""页面分析 JSON 规范化：容错、排序、题型回落、页类型过滤。"""
import json

import pytest

from app.services.parsers.math_page import analyze_page, parse_page_analysis


def _raw(payload) -> str:
    return json.dumps(payload, ensure_ascii=False)


def test_parses_normal_payload():
    raw = _raw({
        "page_type": "practice",
        "groups": [{
            "stem": "不计算，运用规律直接写出得数",
            "instruction": "",
            "work_mode": "pattern",
            "need_process": False,
            "continues_next_page": False,
            "lesson_no": 3,
            "lesson_title": "第3课时 一个数除以小数",
            "items": [
                {"seq": 1, "y": 0.18, "text": "$1.08 \\div 0.9 = 1.2$",
                 "answer_hint": "1.2", "is_example": True},
                {"seq": 4, "y": 0.57, "text": "$1111.05 \\div 0.9 =$ ____",
                 "answer_hint": "", "is_example": False},
            ],
        }],
        "image_questions": [],
    })
    out = parse_page_analysis(raw)
    assert out["page_type"] == "practice"
    assert len(out["groups"]) == 1
    g = out["groups"][0]
    assert g["work_mode"] == "pattern"
    assert g["lesson_no"] == 3
    assert g["lesson_title"] == "第3课时 一个数除以小数"
    assert [i["seq"] for i in g["items"]] == [1, 4]
    assert g["items"][0]["is_example"] is True


def test_items_sorted_by_y_for_dense_grid():
    """一页 40 道口算：AI 返回顺序可能跳行，必须按 y 排。"""
    raw = _raw({
        "page_type": "practice",
        "groups": [{"stem": "", "work_mode": "oral", "items": [
            {"seq": 3, "y": 0.5, "text": "3+3=____"},
            {"seq": 1, "y": 0.1, "text": "1+1=____"},
            {"seq": 2, "y": 0.3, "text": "2+2=____"},
        ]}],
        "image_questions": [],
    })
    out = parse_page_analysis(raw)
    assert [i["seq"] for i in out["groups"][0]["items"]] == [1, 2, 3]


def test_unknown_work_mode_falls_back_to_other():
    raw = _raw({"page_type": "practice", "groups": [
        {"stem": "x", "work_mode": "no_such_mode", "items": []},
    ], "image_questions": []})
    assert parse_page_analysis(raw)["groups"][0]["work_mode"] == "other"


@pytest.mark.parametrize("bad_type", ["toc", "answer_key", "cover", "blank"])
def test_non_practice_page_type_kept_for_router_to_skip(bad_type):
    raw = _raw({"page_type": bad_type, "groups": [], "image_questions": []})
    assert parse_page_analysis(raw)["page_type"] == bad_type


def test_unknown_page_type_defaults_to_practice():
    """拿不准页类型时宁可多导（默认 practice）。"""
    raw = _raw({"page_type": "weird", "groups": [], "image_questions": []})
    assert parse_page_analysis(raw)["page_type"] == "practice"


def test_tolerates_noise_around_json():
    raw = '这是分析结果：\n{"page_type":"practice","groups":[],"image_questions":[]}\n完毕'
    assert parse_page_analysis(raw)["page_type"] == "practice"


@pytest.mark.parametrize("raw", ["", "not json", "{broken", "[]", "null"])
def test_malformed_input_returns_safe_empty(raw):
    out = parse_page_analysis(raw)
    assert out["page_type"] == "practice"
    assert out["groups"] == []
    assert out["image_questions"] == []


def test_missing_fields_get_defaults():
    raw = _raw({"page_type": "practice", "groups": [
        {"items": [{"text": "1+1=____"}]},
    ]})
    g = parse_page_analysis(raw)["groups"][0]
    assert g["stem"] == ""
    assert g["need_process"] is False
    assert g["continues_next_page"] is False
    assert g["lesson_no"] is None
    assert g["lesson_title"] == ""
    item = g["items"][0]
    assert item["seq"] == 1        # 缺 seq 时按出现顺序补
    assert item["is_example"] is False


def test_image_questions_validated():
    raw = _raw({"page_type": "practice", "groups": [], "image_questions": [
        {"start": 0.71, "end": 0.86, "title": "求涂色部分的面积"},
        {"start": 0.9, "end": 0.1, "title": "非法范围应丢弃"},
        {"start": "x", "end": None, "title": "类型错应丢弃"},
    ]})
    iq = parse_page_analysis(raw)["image_questions"]
    assert len(iq) == 1
    assert iq[0]["title"] == "求涂色部分的面积"


def test_analyze_page_calls_vision_json(setup_db, db, monkeypatch):
    import app.services.parsers.math_page as mp

    called = {}

    def _fake_vision(db_, image_bytes, system, prompt, **kw):
        called.update(system=system, prompt=prompt, bytes=image_bytes)
        return '{"page_type":"practice","groups":[],"image_questions":[]}'

    monkeypatch.setattr(mp, "vision_json", _fake_vision)
    out = mp.analyze_page(db, b"\x89PNG", subject="数学")
    assert out["page_type"] == "practice"
    assert "严禁" in called["system"]
    assert called["bytes"] == b"\x89PNG"
    # 提示词里的 LaTeX 必须是单反斜杠（json 里才写 \\div）
    assert "\\div" in called["system"]
    assert "\\\\div" not in called["system"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_math_page_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.parsers'`

- [ ] **Step 3: 建包与纯函数**

```bash
# backend/app/services/parsers/__init__.py  —— 空文件
```

```python
# backend/app/services/parsers/math_page.py
"""数学练习册整页分析：一次视觉调用返回页类型 + 题组 + 小题 + 图片题。

设计：`parse_page_analysis()` 是纯函数（只做 JSON 规范化，好测），
`analyze_page()` 负责取图调用 `ai.vision_json()` 再交给它。
换学科只需另写一个同结构的 `text_page.py`，编排层零改动。
"""
import json
import re

from ...core.work_modes import REGISTRY
from ..ai import vision_json

# 允许的页类型；非 practice 由编排层跳过
PAGE_TYPES = ("practice", "toc", "answer_key", "cover", "blank")

_PAGE_SYSTEM = (
    "你是小学数学练习册的题目结构化助手。看这一页的图片，把内容结构化成 JSON。\n"
    "\n"
    "输出格式：\n"
    '{"page_type":"practice|toc|answer_key|cover|blank",'
    '"groups":[{"stem":"题干","instruction":"引导语","lesson_no":3,'
    '"lesson_title":"第3课时 标题","work_mode":"题型id",'
    '"need_process":false,"continues_next_page":false,'
    '"items":[{"seq":1,"y":0.18,"text":"题干原文","answer_hint":"","is_example":false}]}],'
    '"image_questions":[{"start":0.71,"end":0.86,"title":"标题"}]}\n'
    "\n"
    "work_mode 只能取以下之一："
    + "、".join(f"{m.id}({m.label})" for m in REGISTRY.values()) + "\n"
    "\n"
    "【硬约束】\n"
    "1. 严禁计算！严禁把答案写进 text。text 只抄页面印刷的内容。\n"
    "2. 一页有几个大题就返回几个 group，不许自行合并或拆分。\n"
    "3. answer_hint 只在页面已经印出答案时填写（通常是示例行）。\n"
    "4. 拿不准 work_mode 时填 other，不要猜。\n"
    "5. 每道小题都要给 y（该题在这页的纵向比例 0~1），用于密集网格还原行列。\n"
    "6. 页尾的题被切断（题干/数字不完整）时，continues_next_page 置 true。\n"
    "7. 页首有「第N课时 标题」时填 lesson_no（整数 N）与 lesson_title；没有就都留空。\n"
    "\n"
    "【格式约束】\n"
    "1. 空位统一用 ____（不要用「（　）」「(  )」）。竖式里的方格挖空保留原样 □。\n"
    "2. 数学式用 $...$ 包裹基础 LaTeX，例如 $111.06 \\div 0.9 = 123.4$、$\\frac{3}{4}$。\n"
    "3. 中文叙述、标点、单位不得放进 $...$ 内部。\n"
    "4. 只用基础 LaTeX：\\frac \\sqrt ^ _ \\times \\div \\pm \\left( \\right) \\underline；"
    "禁用 \\begin{...}、\\text{}、\\color、\\require。\n"
    "5. 多行竖式/脱式：一行一个 $...$，行间用 \\n 分隔，不要用 \\begin{aligned}。\n"
    "6. 页面上需要看图才能作答的题（图形、统计图、方格图、钟面、展开图）放进 "
    "image_questions，给纵向范围，不要试图用文字还原。\n"
)

_PAGE_PROMPT = "分析这一页练习册图片，按 system 要求返回 JSON。只输出 JSON，不要解释。"

_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _safe_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _empty() -> dict:
    return {"page_type": "practice", "groups": [], "image_questions": []}


def _norm_item(raw: dict, fallback_seq: int) -> dict:
    seq = _safe_int(raw.get("seq"))
    return {
        "seq": seq if seq is not None else fallback_seq,
        "y": _safe_float(raw.get("y"), 0.0),
        "text": str(raw.get("text") or "").strip(),
        "answer_hint": str(raw.get("answer_hint") or "").strip(),
        "is_example": bool(raw.get("is_example")),
    }


def _norm_group(raw: dict) -> dict:
    mode = str(raw.get("work_mode") or "").strip()
    if mode not in REGISTRY:
        mode = "other"
    items_raw = raw.get("items")
    items: list[dict] = []
    if isinstance(items_raw, list):
        for idx, it in enumerate(items_raw, start=1):
            if isinstance(it, dict):
                items.append(_norm_item(it, idx))
    # 按 y 排序还原行列顺序。sorted 是稳定排序：同一 y（密集网格同一行）
    # 会保留 AI 的原始顺序，这是期望行为，不要改成二次排序。
    items.sort(key=lambda x: x["y"])
    return {
        "stem": str(raw.get("stem") or "").strip(),
        "instruction": str(raw.get("instruction") or "").strip(),
        "lesson_no": _safe_int(raw.get("lesson_no")),
        "lesson_title": str(raw.get("lesson_title") or "").strip(),
        "work_mode": mode,
        "need_process": bool(raw.get("need_process")),
        "continues_next_page": bool(raw.get("continues_next_page")),
        "items": items,
    }


def _norm_image(raw: dict) -> dict | None:
    start = _safe_float(raw.get("start"), -1.0)
    end = _safe_float(raw.get("end"), -1.0)
    if not (0.0 <= start < end <= 1.0):
        return None
    return {
        "start": start,
        "end": end,
        "title": str(raw.get("title") or "").strip(),
    }


def parse_page_analysis(raw: str) -> dict:
    """AI 原始输出 → 规范化 dict。任何异常都返回安全的空结构，绝不抛。"""
    try:
        data = json.loads(raw or "")
    except (ValueError, TypeError):
        m = _JSON_RE.search(raw or "")
        if not m:
            return _empty()
        try:
            data = json.loads(m.group(0))
        except (ValueError, TypeError):
            return _empty()

    if not isinstance(data, dict):
        return _empty()

    page_type = str(data.get("page_type") or "").strip()
    if page_type not in PAGE_TYPES:
        page_type = "practice"   # 拿不准宁可多导

    groups: list[dict] = []
    gs = data.get("groups")
    if isinstance(gs, list):
        for g in gs:
            if isinstance(g, dict):
                groups.append(_norm_group(g))

    images: list[dict] = []
    iqs = data.get("image_questions")
    if isinstance(iqs, list):
        for iq in iqs:
            if isinstance(iq, dict):
                norm = _norm_image(iq)
                if norm:
                    images.append(norm)

    return {"page_type": page_type, "groups": groups, "image_questions": images}


def analyze_page(db, image_bytes: bytes, *, subject: str = "数学") -> dict:
    """整页视觉分析。异常由调用方（编排层）捕获并记为该页失败。"""
    raw = vision_json(db, image_bytes, system=_PAGE_SYSTEM, prompt=_PAGE_PROMPT)
    return parse_page_analysis(raw)
```

> **提示词里的转义**：`_PAGE_SYSTEM` 是普通 Python 字符串，所以 `\\div` 在运行时是
> `\div`（单反斜杠）——这正是 LaTeX 要的。测试 `"\\div" in called["system"]` 校验的
> 就是这一点（Python 源码里的 `"\\div"` 也是单反斜杠）。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_math_page_parser.py -v`
Expected: PASS（约 16 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/parsers/ backend/tests/test_math_page_parser.py
git commit -m "feat(practice): 数学整页分析器（提示词 + JSON 规范化 + y 排序）"
```

---

## Task 7: 跨页合并

**Files:**
- Modify: `backend/app/services/practice_import.py`（追加 `_levenshtein` 与 `merge_cross_page_groups`）
- Test: `backend/tests/test_merge_groups.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_merge_groups.py
"""跨页合并：连续多页、工作模式不同、stem 不匹配、不得边遍历边丢组。"""
from app.services.practice_import import _levenshtein, merge_cross_page_groups


def _g(page, work_mode="oral", stem="直接写出得数", cont=False, items=None):
    return {
        "key": f"{page}-0",
        "page_start": page,
        "page_end": page,
        "work_mode": work_mode,
        "stem": stem,
        "continues_next_page": cont,
        "incomplete": False,
        "items": items or [{"seq": 1, "text": f"p{page}-1"}],
    }


def test_levenshtein_basic():
    assert _levenshtein("abc", "abc") == 0
    assert _levenshtein("", "abc") == 3
    assert _levenshtein("kitten", "sitting") == 3


def test_merges_continuation_into_previous_group():
    gs = [_g(1, cont=True), _g(2)]
    out = merge_cross_page_groups(gs)
    assert len(out) == 1
    assert out[0]["page_start"] == 1 and out[0]["page_end"] == 2
    assert len(out[0]["items"]) == 2


def test_merges_across_three_pages():
    gs = [_g(1, cont=True), _g(2, cont=True), _g(3)]
    out = merge_cross_page_groups(gs)
    assert len(out) == 1
    assert out[0]["page_end"] == 3
    assert len(out[0]["items"]) == 3


def test_does_not_merge_when_work_mode_differs():
    gs = [_g(1, work_mode="oral", cont=True), _g(2, work_mode="app")]
    out = merge_cross_page_groups(gs)
    assert len(out) == 2


def test_does_not_merge_when_stem_unrelated():
    gs = [_g(1, stem="直接写出得数", cont=True), _g(2, stem="解决问题并验算")]
    out = merge_cross_page_groups(gs)
    assert len(out) == 2
    assert out[0]["incomplete"] is True


def test_marks_incomplete_and_stops_chain():
    """合并失败必须把 continues_next_page 置 False，否则下一轮还会误吞。"""
    gs = [_g(1, stem="甲组题", cont=True), _g(2, stem="完全不同的乙组")]
    out = merge_cross_page_groups(gs)
    assert len(out) == 2
    assert out[0]["continues_next_page"] is False
    assert out[0]["incomplete"] is True
    assert out[1]["page_start"] == 2


def test_non_contiguous_pages_not_merged():
    """page_start 必须紧接上一组 page_end，跳页不合并。"""
    gs = [_g(1, cont=True), _g(5)]
    out = merge_cross_page_groups(gs)
    assert len(out) == 2


def test_empty_and_single():
    assert merge_cross_page_groups([]) == []
    assert len(merge_cross_page_groups([_g(1)])) == 1


def test_does_not_mutate_input():
    gs = [_g(1, cont=True), _g(2)]
    before = len(gs[0]["items"])
    merge_cross_page_groups(gs)
    assert len(gs[0]["items"]) == before


def test_empty_stem_merges_any():
    """stem 有一侧为空时不作为否决条件（页面没有题干，靠 work_mode 判）。"""
    gs = [_g(1, stem="", cont=True), _g(2, stem="直接写出得数")]
    out = merge_cross_page_groups(gs)
    assert len(out) == 1
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_merge_groups.py -v`
Expected: FAIL — `ImportError: cannot import name 'merge_cross_page_groups'`

- [ ] **Step 3: 写实现**

`backend/app/services/practice_import.py` 顶部 import 补 `import copy`，然后在
`build_drafts` 之前插入：

```python
def _levenshtein(a: str, b: str) -> int:
    """编辑距离（滚动数组）。用于判断相邻页的两段题干是否同一道题。"""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(
                prev[j] + 1,                 # 删除
                cur[j - 1] + 1,              # 插入
                prev[j - 1] + (ca != cb),    # 替换
            ))
        prev = cur
    return prev[-1]


def merge_cross_page_groups(groups: list[dict]) -> list[dict]:
    """全书扫完后统一合并被页面切断的题组。

    合并条件（全部满足才吞下一组）：
    1. 当前组 `continues_next_page` 为真
    2. 下一组 `page_start == 当前组 page_end + 1`（页码紧邻）
    3. `work_mode` 相同
    4. stem 相似（任一为空 → 视为相似；否则子串包含或编辑距离 ≤ 30%）

    合并失败时把 `continues_next_page` 置 False 并标 `incomplete=True`，
    否则下一轮还会误吞。

    **不修改入参**（入口深拷贝），调用方可安全复用原始 groups。
    """
    groups = copy.deepcopy(groups or [])
    merged: list[dict] = []
    i = 0
    while i < len(groups):
        cur = groups[i]
        merged.append(cur)
        # 合并成功后不前进外层游标，继续尝试吞下一组（支持跨 3 页以上）
        while cur.get("continues_next_page") and i + 1 < len(groups):
            nxt = groups[i + 1]
            if (nxt.get("page_start") != cur.get("page_end", 0) + 1
                    or cur.get("work_mode") != nxt.get("work_mode")):
                cur["incomplete"] = True
                cur["continues_next_page"] = False
                break
            a = (cur.get("stem") or "").strip()
            b = (nxt.get("stem") or "").strip()
            same_stem = (
                not a or not b
                or a in b or b in a
                or _levenshtein(a, b) <= max(len(a), len(b)) * 0.3
            )
            if not same_stem:
                cur["incomplete"] = True
                cur["continues_next_page"] = False
                break
            cur["items"].extend(nxt.get("items") or [])
            cur["page_end"] = nxt.get("page_end", cur.get("page_end"))
            cur["continues_next_page"] = bool(nxt.get("continues_next_page"))
            i += 1   # 吞掉 nxt
        i += 1
    return merged
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_merge_groups.py -v`
Expected: PASS（10 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/practice_import.py backend/tests/test_merge_groups.py
git commit -m "feat(practice): 跨页题组合并（支持跨 3 页以上，失败标 incomplete）"
```

---

## Task 8: `_strip_answer` 感知 `$` + `build_drafts` 写 `answer_json`

**Files:**
- Modify: `backend/app/services/practice_import.py:290-355`（`_strip_answer`、`build_drafts`）
- Test: `backend/tests/test_practice_import.py`（追加）

**两个必须修的点**：
1. `_strip_answer` 在第一个 `=` 截断，对 `$111.06 \div 0.9 = 123.4$` 会留**孤立的 `$`**。
2. `build_drafts` 不按 `work_mode` 写 `answer_json`，导致 `pattern`（`numeric_list`）
   与 `choice` 永远过不了发布闸门（`_is_aligned` 要求 `blanks` / `correct_index`）。

**`answer_hint` 的用途**：页面印好的示例答案要写进示例行的 `answer`——前端靠它展示
「1.08 ÷ 0.9 = 1.2」的完整样子。丢弃 `answer_hint` 就只剩裸算式。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_practice_import.py 末尾追加
from app.services.practice_import import _strip_answer, build_drafts


def test_strip_answer_closes_formula_and_adds_blank():
    """公式内截断必须重新闭合 $ 并补空位，而不是留一个孤立 $。"""
    out = _strip_answer(r"$111.06 \div 0.9 = 123.4$")
    assert out == r"$111.06 \div 0.9 =$ ____"
    assert out.count("$") % 2 == 0


def test_strip_answer_keeps_equation_with_variable():
    """含未知数的方程不截断（5.2 是方程的一部分）。"""
    src = r"$4x - 5.2 = 5.2$"
    assert _strip_answer(src) == src


def test_strip_answer_skips_example_rows():
    """示例行本来就要显示答案，完全不截断。"""
    src = r"$1.08 \div 0.9 = 1.2$"
    assert _strip_answer(src, is_example=True) == src


def test_strip_answer_legacy_plain_text_still_works():
    """没有 $ 的旧格式保持原行为。"""
    assert _strip_answer("8.9 + 4.5 = 13.4") == "8.9 + 4.5 ="


def test_strip_answer_no_equals_untouched():
    assert _strip_answer("求涂色部分的面积") == "求涂色部分的面积"


def test_strip_answer_right_side_not_numeric_untouched():
    src = r"$x + 1 = ?$"
    assert _strip_answer(src) == src


def test_strip_answer_always_keeps_dollar_pairing():
    for src in [
        r"$111.06 \div 0.9 = 123.4$",
        r"$1.08 \div 0.9 = 1.2$",
        r"$4x - 5.2 = 5.2$",
        r"$3.5 \times 2 = 7$",
    ]:
        assert _strip_answer(src).count("$") % 2 == 0, src


def test_build_drafts_passes_group_fields():
    drafts = build_drafts(
        [{
            "kind": "fill", "question": r"$1.08 \div 0.9 = 1.2$", "answer": "1.2",
            "group_id": 7, "seq_in_group": 3, "is_example": True,
            "work_mode": "pattern", "lesson_no": 5, "lesson_title": "第1课时",
            "page": 5,
        }],
        document_id=99,
    )
    d = drafts[0]
    assert d.group_id == 7
    assert d.seq_in_group == 3
    assert d.is_example is True
    assert d.work_mode == "pattern"
    # 示例行不截断，答案保留
    assert "1.2" in d.question


def test_build_drafts_writes_blanks_for_numeric_list():
    """numeric_list 必须把 blanks 写进 answer_json，否则永远过不了发布闸门。"""
    drafts = build_drafts(
        [{
            "kind": "fill", "question": "$1111.05 \\div 0.9 =$ ____",
            "answer": "1234.5, 12345", "blanks": ["1234.5", "12345"],
            "work_mode": "pattern", "is_example": False,
            "seq_in_group": 1, "group_id": 1,
        }],
        document_id=1,
    )
    d = drafts[0]
    assert d.answer_json.get("blanks") == ["1234.5", "12345"]
    # qtype 来自注册表，不是旧的 kind 映射
    assert d.qtype == "fill_blank"


def test_build_drafts_writes_correct_index_for_choice():
    drafts = build_drafts(
        [{
            "kind": "other", "question": "下列哪个是质数？",
            "answer": "B", "correct_index": 1,
            "work_mode": "choice", "is_example": False,
            "seq_in_group": 1, "group_id": 1,
        }],
        document_id=1,
    )
    d = drafts[0]
    assert d.qtype == "single_choice"
    assert d.answer_json.get("correct_index") == 1


def test_build_drafts_symbol_has_no_blanks_requirement():
    drafts = build_drafts(
        [{
            "kind": "fill", "question": "30.5 ○ 3.05", "answer": ">",
            "work_mode": "compare", "is_example": False,
            "seq_in_group": 1, "group_id": 1,
        }],
        document_id=1,
    )
    d = drafts[0]
    assert d.answer == ">"
    assert d.answer_json == {}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_practice_import.py -k "strip_answer or build_drafts" -v`
Expected: FAIL — `TypeError: _strip_answer() got an unexpected keyword argument 'is_example'`

- [ ] **Step 3: 重写 `_strip_answer`**

把 `backend/app/services/practice_import.py` 里现有的 `_strip_answer`（290-316 行）整体替换为下面的代码。

> ⚠️ **正则必须叫 `_FORMULA_RE`，不能叫 `_MATH_RE`**：文件第 28 行已经有一个
> `_MATH_RE = re.compile(r"[+\-−×÷*/=＝]")`，被 `_is_problem_line`（:58）和
> `parse_lesson_page`（:138）使用。若在本文件后半再定义同名常量，会在 import 时
> **静默改写模块全局**，把 `_is_problem_line` 的判定偷偷改坏（Task 8 之后
> `test_parse_lesson_page_*` 会莫名其妙变红，且报错位置与真正原因无关）。

```python
_FORMULA_RE = re.compile(r"\$([^$]+)\$")


def _strip_answer(question: str, *, is_example: bool = False) -> str:
    """去掉题干里「= 结果」的部分，但绝不破坏 `$...$` 的成对性。

    视觉模型有时会自己把算式算出来写进题干（如 `8.9＋4.5＝13.4`），必须截断，
    否则孩子直接看到答案。规则顺序不可颠倒：

    0. `is_example=True` → 原样返回（示例本来就该显示答案）
    1. 等号左侧含未知数 → 不截断（方程里的常数项属于题目本身）
    2. 只在第一个 `$...$` 内部判断「是否已算出答案」，不对整串做正则
    3. 截断点在公式内 → 重新闭合该公式并补 `____`
    4. 兜底：截断后 `$` 计数为奇数 → 放弃截断（宁可露答案，不要坏标记）
    """
    q = (question or "").strip()
    if not q or is_example:
        return q

    m = _FORMULA_RE.search(q)
    if m is None:
        # 旧格式（无公式外壳）：整串判断
        eq = re.search(r"[=＝]", q)
        if not eq:
            return q
        left = q[: eq.start()]
        if _has_variable(left):
            return q
        right = q[eq.end():].strip()
        if re.match(r"^[-−+]?\d", right):
            return left.rstrip(" =＝") + " ="
        return q

    inner = m.group(1)
    eq = re.search(r"[=＝]", inner)
    if not eq:
        return q
    left = inner[: eq.start()]
    if _has_variable(left):
        return q
    right = inner[eq.end():].strip()
    if not re.match(r"^[-−+]?\d", right):
        return q

    closed = f"${left.rstrip(' =＝')} =$"
    candidate = q[: m.start()] + closed + " ____" + q[m.end():]
    if candidate.count("$") % 2 != 0:
        return q
    return candidate
```

- [ ] **Step 4: 重写 `build_drafts`**

把现有 `build_drafts`（320-355 行）整体替换为：

```python
def build_drafts(
    aligned: list[dict],
    *,
    document_id: int,
    blanks_of=None,      # 保留形参兼容旧调用；新流程用 item["blanks"]
) -> list[QuestionDraft]:
    """已对齐的题 → QuestionDraft（供 bank._persist_drafts 落库）。

    `work_mode` 非空时按注册表定 qtype，并按 answer_kind 写 answer_json：
    - `numeric_list` → `{"blanks": [...]}`（发布闸门要求非空）
    - `choice`       → `{"correct_index": n}`
    - 其它           → `{}`

    `work_mode` 为空时走旧的 kind → qtype 映射（兼容既有题库/OCR 链路）。
    """
    from ..core.work_modes import answer_kind_of, legacy_qtype_of

    out: list[QuestionDraft] = []
    for q in aligned:
        mode = (q.get("work_mode") or "").strip()
        if mode:
            qtype = legacy_qtype_of(mode)
            kind = answer_kind_of(mode)
        else:
            qtype = QTYPE_OF_KIND.get((q.get("kind") or "oral").strip(), "oral")
            kind = ""

        d = QuestionDraft(
            qtype=qtype,
            question=_strip_answer(q.get("question") or "",
                                   is_example=bool(q.get("is_example"))),
            # 示例行的答案来自页面印好的 answer_hint
            answer=(q.get("answer") or q.get("answer_hint") or "").strip(),
            analysis=q.get("analysis") or "",
        )
        d.lesson_no = q.get("lesson_no")
        d.lesson_title = q.get("lesson_title") or ""
        d.question_no = str(q.get("question_no") or "")
        d.source_document_id = document_id
        d.tags = {"source": "practice_pdf", "page": q.get("page") or 0}

        # 题组两级：小题挂到组下；示例行不入待做
        d.group_id = q.get("group_id")
        d.seq_in_group = int(q.get("seq_in_group") or 0)
        d.is_example = bool(q.get("is_example"))
        d.work_mode = mode

        if q.get("image_path"):
            d.image_path = q["image_path"]
            d.tags["image_path"] = q["image_path"]

        # answer_json：发布闸门与判分都依赖它
        blanks = [str(x).strip() for x in (q.get("blanks") or []) if str(x).strip()]
        if kind == "numeric_list":
            if blanks:
                d.answer_json = {"blanks": blanks}
        elif kind == "choice":
            idx = q.get("correct_index")
            if idx is not None:
                d.answer_json = {"correct_index": int(idx)}
        elif not mode:
            # 旧路径：fill_blank 按空数切分答案。
            # 现有调用方（tests/test_practice_import.py:232,246）通过 blanks_of 回调传空数，
            # 必须兼容，否则那些测试会红。
            if qtype in ("fill_blank", "cloze"):
                n = int((blanks_of(q) if blanks_of else 0)
                        or q.get("blanks_count") or 0)
                old_blanks = split_blanks(d.answer, n) if n else None
                if old_blanks:
                    d.answer_json = {"blanks": old_blanks}
                elif n:
                    d.qtype = "oral"

        out.append(d)
    return out
```

> **`blanks_of` 形参是真在用的**，不是为兼容而留的空壳：`tests/test_practice_import.py`
> 有两处 `build_drafts(aligned, document_id=..., blanks_of=lambda q: 2)`，断言产出
> `qtype == "fill_blank"` 且 `answer_json["blanks"] == ["1", "2"]`。上面这行
> `n = int((blanks_of(q) if blanks_of else 0) or q.get("blanks_count") or 0)`
> 就是为它们准备的——**不要简化成只读 `q["blanks_count"]`**（该键全仓库不存在）。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_practice_import.py -k "strip_answer or build_drafts" -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/practice_import.py backend/tests/test_practice_import.py
git commit -m "fix(practice): _strip_answer 感知 \$ 边界，build_drafts 按 answer_kind 写 answer_json"
```

---

## Task 9: 判分门面 `math_grade.py`

**Files:**
- Create: `backend/app/services/math_grade.py`
- Test: `backend/tests/test_math_grade.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_math_grade.py
"""按 answer_kind 分派判分：number / numeric_list / symbol / choice / photo / text。"""
import pytest

from app.services.math_grade import grade_by_answer_kind


def test_number_uses_math_answer_tolerance():
    r = grade_by_answer_kind(None, answer_kind="number", answer="13.4",
                             student_answer="13.40")
    assert r["is_correct"] is True
    r2 = grade_by_answer_kind(None, answer_kind="number", answer="13.4",
                              student_answer="13.5")
    assert r2["is_correct"] is False


def test_number_empty_answer_is_pending():
    r = grade_by_answer_kind(None, answer_kind="number", answer="",
                             student_answer="5")
    assert r["is_correct"] is None
    assert r["ai_status"] == "pending"


def test_numeric_list_requires_all_blanks():
    r = grade_by_answer_kind(
        None, answer_kind="numeric_list", answer="1.2, 1.44",
        answer_json={"blanks": ["1.2", "1.44"]},
        blanks=["1.2", "1.44"],
    )
    assert r["is_correct"] is True

    r2 = grade_by_answer_kind(
        None, answer_kind="numeric_list", answer="1.2, 1.44",
        answer_json={"blanks": ["1.2", "1.44"]},
        blanks=["1.2", "1.45"],
    )
    assert r2["is_correct"] is False


def test_numeric_list_wrong_count_is_false():
    r = grade_by_answer_kind(
        None, answer_kind="numeric_list", answer="1.2, 1.44",
        answer_json={"blanks": ["1.2", "1.44"]},
        blanks=["1.2"],
    )
    assert r["is_correct"] is False


@pytest.mark.parametrize("student", [">", "＞", " > "])
def test_symbol_normalizes_fullwidth_and_space(student):
    r = grade_by_answer_kind(None, answer_kind="symbol", answer=">",
                             student_answer=student)
    assert r["is_correct"] is True


def test_symbol_mismatch():
    r = grade_by_answer_kind(None, answer_kind="symbol", answer=">",
                             student_answer="<")
    assert r["is_correct"] is False


def test_choice_compares_index():
    r = grade_by_answer_kind(
        None, answer_kind="choice", answer="B",
        answer_json={"correct_index": 1}, student_answer="1",
    )
    assert r["is_correct"] is True


def test_text_defers_to_caller():
    """text 交给既有的主观题判分，这里返回 None 而不是瞎判。"""
    r = grade_by_answer_kind(None, answer_kind="text", answer="参考",
                             student_answer="孩子写的")
    assert r["is_correct"] is None
    assert r["ai_status"] == "pending"


def test_photo_without_bytes_is_pending():
    r = grade_by_answer_kind(None, answer_kind="photo", answer="13.4",
                             photo_bytes=None)
    assert r["is_correct"] is None
    assert r["ai_status"] == "pending"


def test_photo_uses_vision_grader(monkeypatch):
    import app.services.math_grade as mg

    monkeypatch.setattr(mg, "grade_math_work_photo", lambda db, img, q, exp: {
        "final_answer": exp, "steps_plausible": True, "confidence": 0.9,
        "reason": "步骤正确", "ai_status": "ok", "ai_correct": True,
    })
    r = mg.grade_by_answer_kind(None, answer_kind="photo", answer="13.4",
                                question="8.9+4.5", photo_bytes=b"img")
    assert r["is_correct"] is True
    assert r["steps_plausible"] is True
    assert r["final_answer"] == "13.4"


def test_unknown_answer_kind_falls_back_to_text():
    r = grade_by_answer_kind(None, answer_kind="no_such", answer="x",
                             student_answer="y")
    assert r["is_correct"] is None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_math_grade.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.math_grade'`

- [ ] **Step 3: 写实现**

```python
# backend/app/services/math_grade.py
"""所有数学入口共用的判分门面。

**唯一一份**按 `answer_kind` 分派的实现。`practice_grade.grade_practice_item`
与未来的 `language_grade` 都只做「取字段 → 转交这里」的薄包装，不重复分派逻辑。

返回统一 dict：`{is_correct, ai_status, final_answer, steps_plausible, reason}`
- `is_correct` 为 `None` 表示「无法判定」（缺答案/待人工/AI 未完成），不是「判错」
"""
from .math_gen import grade_math_answer, grade_math_work_photo

# 全角 → 半角（比较符号）
_SYMBOL_MAP = str.maketrans({
    "＞": ">", "＜": "<", "＝": "=",
    "≥": ">=", "≤": "<=",
})


def _result(is_correct, *, ai_status="ok", final_answer="",
            steps_plausible=False, reason="") -> dict:
    return {
        "is_correct": is_correct,
        "ai_status": ai_status,
        "final_answer": final_answer,
        "steps_plausible": steps_plausible,
        "reason": reason,
    }


def _pending(reason: str) -> dict:
    return _result(None, ai_status="pending", reason=reason)


def _norm_symbol(s: str) -> str:
    return (s or "").strip().translate(_SYMBOL_MAP).replace(" ", "")


def _blanks_of(answer_json: dict | None) -> list[str]:
    if not isinstance(answer_json, dict):
        return []
    raw = answer_json.get("blanks")
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw]


def grade_by_answer_kind(
    db,
    *,
    answer_kind: str,
    answer: str,
    answer_json: dict | None = None,
    student_answer: str = "",
    blanks: list | None = None,
    photo_bytes: bytes | None = None,
    question: str = "",
) -> dict:
    """按 answer_kind 分派。绝不抛异常（未知 kind 回落 text）。"""
    kind = (answer_kind or "").strip()
    expected = (answer or "").strip()

    if kind == "number":
        if not expected:
            return _pending("缺少标准答案")
        ok = grade_math_answer(student_answer, expected)
        return _result(ok, final_answer=expected)

    if kind == "numeric_list":
        expected_blanks = _blanks_of(answer_json)
        if not expected_blanks:
            return _pending("缺少分空答案")
        got = [str(x).strip() for x in (blanks or [])]
        if len(got) != len(expected_blanks):
            return _result(False, final_answer=expected)
        ok = all(grade_math_answer(g, e) for g, e in zip(got, expected_blanks))
        return _result(ok, final_answer=expected)

    if kind == "symbol":
        if not expected:
            return _pending("缺少标准答案")
        ok = _norm_symbol(student_answer) == _norm_symbol(expected)
        return _result(ok, final_answer=expected)

    if kind == "choice":
        idx = (answer_json or {}).get("correct_index")
        if idx is None:
            return _pending("缺少正确选项")
        try:
            ok = int(str(student_answer).strip()) == int(idx)
        except (TypeError, ValueError):
            ok = False
        return _result(ok, final_answer=expected or str(idx))

    if kind == "photo":
        if not photo_bytes:
            return _pending("未上传作答照片")
        if not expected:
            return _pending("缺少标准答案")
        r = grade_math_work_photo(db, photo_bytes, question or "", expected)
        status = r.get("ai_status") or "pending"
        # pending_review / failed 都不算判错
        ok = bool(r.get("ai_correct")) if status == "ok" else None
        return _result(
            ok,
            ai_status=status,
            final_answer=r.get("final_answer") or "",
            steps_plausible=bool(r.get("steps_plausible")),
            reason=r.get("reason") or "",
        )

    # text / 未知：交给调用方走既有的主观题判分
    return _pending("需主观判分")
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_math_grade.py -v`
Expected: PASS（约 14 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/math_grade.py backend/tests/test_math_grade.py
git commit -m "feat(practice): 新增判分门面 math_grade.grade_by_answer_kind"
```

---

## Task 10: 薄包装 `practice_grade.py` 与 `solve_math_items` 新返回结构

**Files:**
- Create: `backend/app/services/practice_grade.py`
- Modify: `backend/app/services/practice_solve.py`
- Test: `backend/tests/test_math_grade.py`（追加）、`backend/tests/test_practice_import.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_math_grade.py 末尾追加
def test_grade_practice_item_reads_orm_fields(setup_db, db, monkeypatch):
    """薄包装只负责取字段，分派逻辑仍在 grade_by_answer_kind。"""
    import app.services.practice_grade as pg
    from app.models import Question, QuestionBank
    from conftest import make_user

    called = {}

    def _fake(db_, **kwargs):
        called.update(kwargs)
        return {"is_correct": True, "ai_status": "ok", "final_answer": "1.2",
                "steps_plausible": False, "reason": ""}

    monkeypatch.setattr(pg, "grade_by_answer_kind", _fake)

    user = make_user(db)
    bank = QuestionBank(user_id=user.id, title="卷", subject="数学", grade=5)
    db.add(bank)
    db.flush()
    q = Question(bank_id=bank.id, user_id=user.id, qtype="fill_blank",
                 qtype_category="blank", question="1+1=____",
                 answer="1.2, 1.44", answer_json='{"blanks":["1.2","1.44"]}',
                 work_mode="pattern")
    db.add(q)
    db.commit()

    r = pg.grade_practice_item(db, q, student_answer="1.2, 1.44")
    assert r["is_correct"] is True
    assert called["answer_kind"] == "numeric_list"
    assert called["answer"] == "1.2, 1.44"
    assert called["answer_json"] == {"blanks": ["1.2", "1.44"]}
    assert called["blanks"] == ["1.2", "1.44"]
```

```python
# backend/tests/test_practice_import.py 末尾追加
def test_solve_math_items_returns_dict_shape(monkeypatch):
    """返回结构从 dict[int, str] 改为 dict[int, dict]。"""
    import app.services.practice_solve as ps

    monkeypatch.setattr(ps, "_provider_ready", lambda db: True)
    monkeypatch.setattr(ps, "_call_solver", lambda db, chunk: {
        0: {"kind": "number", "answer": "13.4"},
        1: {"kind": "numeric_list", "blanks": ["1.2", "1.44"]},
    })

    out = ps.solve_math_items(None, [{"question": "a"}, {"question": "b"}])
    assert out[0]["answer"] == "13.4"
    assert out[1]["blanks"] == ["1.2", "1.44"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_math_grade.py -k practice_item -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.practice_grade'`

- [ ] **Step 3: 写 `practice_grade.py`**

```python
# backend/app/services/practice_grade.py
"""练习册判分入口：从 ORM 对象取字段，转交 math_grade。

这是 `math_grade.grade_by_answer_kind()` 的**薄包装**——按 answer_kind 分派的
具体逻辑只有一份，在 math_grade.py 里。此处只做「ORM 字段 → 判分参数」的搬运，
避免 bank.py / practice.py 各自拼字段。
"""
import json

from ..core.work_modes import answer_kind_of
from .math_grade import grade_by_answer_kind


def _parse_json(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def _blanks_from(answer_json: dict) -> list[str]:
    raw = answer_json.get("blanks")
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw]


def grade_practice_item(
    db,
    question,
    student_answer: str = "",
    *,
    blanks: list | None = None,
    photo_bytes: bytes | None = None,
) -> dict:
    """判一道练习册小题。返回 {is_correct, ai_status, final_answer,
    steps_plausible, reason}。

    `blanks` 为多空题的逐空作答；不传则从 `student_answer` 按逗号切。
    """
    work_mode = getattr(question, "work_mode", "") or ""
    answer_json = _parse_json(getattr(question, "answer_json", "") or "")
    expected_blanks = _blanks_from(answer_json)

    if blanks is None:
        if expected_blanks and student_answer:
            blanks = [s.strip() for s in student_answer.split(",")]
        else:
            blanks = []

    return grade_by_answer_kind(
        db,
        answer_kind=answer_kind_of(work_mode),
        answer=getattr(question, "answer", "") or "",
        answer_json=answer_json,
        student_answer=student_answer,
        blanks=blanks,
        photo_bytes=photo_bytes,
        question=getattr(question, "question", "") or "",
    )
```

- [ ] **Step 4: 重写 `practice_solve.py`**

```python
# backend/app/services/practice_solve.py
"""AI 求解：把题面批量交给 LLM 算出答案。

返回结构 `{列表下标: {"kind", "answer", "blanks"}}`：
- `number`       → {"kind": "number", "answer": "13.4"}
- `numeric_list` → {"kind": "numeric_list", "blanks": ["1.2","1.44"], "answer": "1.2, 1.44"}
- `symbol`       → {"kind": "symbol", "answer": ">"}
"""
import json
import re

_SOLVE_SYSTEM = (
    "你是小学数学老师，负责算出每道题的标准答案。\n"
    "只输出 JSON，格式：\n"
    '{"answers":[{"index":0,"kind":"number","answer":"13.4"},'
    '{"index":1,"kind":"numeric_list","blanks":["1.2","1.44"]},'
    '{"index":2,"kind":"symbol","answer":">"}]}\n'
    "kind 只能是 number / numeric_list / symbol。\n"
    "- 单答案填 kind=number, answer=最终结果（保留原题小数位，不写单位、不写过程）。\n"
    "- 一题多空填 kind=numeric_list，blanks 按空位顺序排列，不要填 answer。\n"
    "- 比较大小填 kind=symbol，answer 是 > < = 之一。\n"
    "index 与输入编号严格对应。示例行不要计算。"
)

_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _provider_ready(db) -> bool:
    """fake provider 或未配置时不求解（缺答案进「待补答案」）。"""
    try:
        from .ai import get_provider

        return get_provider(db).name != "fake"
    except Exception:
        return False


def _parse_solve(raw: str) -> dict[int, dict]:
    """把 LLM 返回的 JSON 解析成 {index: {kind, answer, blanks}}。"""
    try:
        data = json.loads(raw or "")
    except (ValueError, TypeError):
        m = _JSON_RE.search(raw or "")
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
        except (ValueError, TypeError):
            return {}

    items = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return {}

    out: dict[int, dict] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            idx = int(it.get("index"))
        except (TypeError, ValueError):
            continue
        kind = str(it.get("kind") or "number").strip()
        if kind == "numeric_list":
            raw_blanks = it.get("blanks")
            blanks = ([str(x).strip() for x in raw_blanks]
                      if isinstance(raw_blanks, list) else [])
            blanks = [b for b in blanks if b]
            if not blanks:
                continue
            out[idx] = {"kind": "numeric_list", "blanks": blanks,
                        "answer": ", ".join(blanks)}
            continue
        ans = str(it.get("answer") or "").strip()
        if not ans:
            continue
        out[idx] = {"kind": "symbol" if kind == "symbol" else "number",
                    "answer": ans}
    return out


def _call_solver(db, chunk: list[dict]) -> dict[int, dict]:
    from .ai import get_provider

    provider = get_provider(db)
    lines = [f"{i}. {it.get('question', '')}" for i, it in enumerate(chunk)]
    prompt = (
        "算出下面每道题的最终答案，index 从 0 开始按顺序编号。\n"
        + "\n".join(lines)
    )
    raw = provider.generate(prompt=prompt, system=_SOLVE_SYSTEM, json_mode=True)
    return _parse_solve(raw)


def solve_math_items(
    db,
    items: list[dict],
    *,
    batch_size: int = 20,
    on_progress=None,
) -> dict[int, dict]:
    """批量求答案。返回 {列表下标: {kind, answer, blanks}}。

    未配置 provider / 调用失败时返回已成功的部分（缺的进「待补答案」）。"""
    if not items:
        return {}
    if not _provider_ready(db):
        return {}

    answers: dict[int, dict] = {}
    total = len(items)
    for start in range(0, total, batch_size):
        chunk = items[start:start + batch_size]
        try:
            got = _call_solver(db, chunk)
        except Exception:
            got = {}
        for local_idx, payload in got.items():
            if 0 <= local_idx < len(chunk):
                answers[start + local_idx] = payload
        if on_progress is not None:
            try:
                on_progress(len(answers), total)
            except Exception:
                pass
    return answers
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_math_grade.py tests/test_practice_import.py -k "practice_item or solve_math" -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/practice_grade.py backend/app/services/practice_solve.py backend/tests/
git commit -m "feat(practice): 判分薄包装 practice_grade + solve_math_items 按 kind 返回"
```

---

## Task 11: 发布闸门按 `answer_kind` + 旧题回退

**Files:**
- Modify: `backend/app/services/practice_import.py`（`_is_aligned`）
- Test: `backend/tests/test_practice_groups.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_practice_groups.py 末尾追加
def test_is_aligned_legacy_questions_unchanged(setup_db, db):
    """work_mode 为空的老题必须走原逻辑：cloze 无 blanks 不发布。"""
    from app.models import Question
    from app.services.practice_import import _is_aligned

    q = Question(qtype="cloze", qtype_category="blank", question="x",
                 answer="a", answer_json='{"blanks":[]}', work_mode="")
    assert _is_aligned(q) is False


def test_is_aligned_new_numeric_list_requires_blanks(setup_db, db):
    from app.models import Question
    from app.services.practice_import import _is_aligned

    q = Question(qtype="fill_blank", qtype_category="blank", question="x",
                 answer="1.2, 1.44", answer_json='{"blanks":["1.2","1.44"]}',
                 work_mode="pattern")
    assert _is_aligned(q) is True

    q2 = Question(qtype="fill_blank", qtype_category="blank", question="x",
                  answer="1.2", answer_json='{"blanks":[]}', work_mode="pattern")
    assert _is_aligned(q2) is False


def test_is_aligned_new_symbol_and_choice_do_not_need_blanks(setup_db, db):
    """symbol/choice 不是多空题，有答案就该发布（旧逻辑会误挡）。"""
    from app.models import Question
    from app.services.practice_import import _is_aligned

    sym = Question(qtype="fill_blank", qtype_category="blank",
                   question="30.5 ○ 3.05", answer=">", answer_json="{}",
                   work_mode="compare")
    assert _is_aligned(sym) is True

    ch = Question(qtype="single_choice", qtype_category="choice", question="x",
                  answer="B", answer_json='{"correct_index":1}',
                  work_mode="choice")
    assert _is_aligned(ch) is True


def test_is_aligned_empty_answer_never_published(setup_db, db):
    from app.models import Question
    from app.services.practice_import import _is_aligned

    for mode in ("oral", "pattern", "compare", "photo", "app", ""):
        q = Question(qtype="oral", qtype_category="subjective", question="x",
                     answer="", answer_json="{}", work_mode=mode)
        assert _is_aligned(q) is False, mode
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k is_aligned -v`
Expected: FAIL — `test_is_aligned_new_symbol_and_choice_do_not_need_blanks` 失败
（新分支还不存在，symbol 走旧逻辑被挡）

- [ ] **Step 3: 重写 `_is_aligned`**

```python
def _is_aligned_legacy(q) -> bool:
    """旧题（work_mode 为空）的发布判定，保持原行为不变。

    存量题库的 cloze/fill_blank 依赖 blanks 校验；若一律走新的 answer_kind 分支，
    会因不再检查 blanks 而被误发布。
    """
    if q.qtype in ("fill_blank", "cloze"):
        try:
            data = json.loads(q.answer_json or "{}")
        except (ValueError, TypeError):
            return False
        return bool(data.get("blanks"))
    return True


def _is_aligned(q) -> bool:
    """已对齐 = 有答案。多空题型还要求逐空答案非空。

    `work_mode` 为空的旧题走 `_is_aligned_legacy()`，行为完全不变。
    """
    from ..core.work_modes import answer_kind_of

    if not (q.answer or "").strip():
        return False
    mode = (getattr(q, "work_mode", "") or "").strip()
    if not mode:
        return _is_aligned_legacy(q)

    kind = answer_kind_of(mode)
    if kind == "numeric_list":
        try:
            data = json.loads(q.answer_json or "{}")
        except (ValueError, TypeError):
            return False
        return bool(data.get("blanks"))
    if kind == "choice":
        try:
            data = json.loads(q.answer_json or "{}")
        except (ValueError, TypeError):
            return False
        return data.get("correct_index") is not None
    return True
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k is_aligned -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 跑既有 aligned/publish 回归**

Run: `cd backend && python -m pytest tests/test_practice_import.py -k "publish or aligned" -q`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/practice_import.py backend/tests/test_practice_groups.py
git commit -m "feat(practice): 发布闸门按 answer_kind 判定，旧题走 legacy 分支"
```

---

## Task 12: 重写导入编排 `run_import_job`

**Files:**
- Modify: `backend/app/services/practice_image.py`（新增 `render_page_png`）
- Modify: `backend/app/services/practice_import.py`（重写编排）
- Test: `backend/tests/test_practice_groups.py`（追加）

**关键设计**：题组先建、小题后挂；示例行跳过求答案但**要发布**（前端需要读它来展示）；
图片题走视觉求答案。

**删除放在 Task 16**，本任务只做重写，旧函数暂留（新代码不调用）。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_practice_groups.py 末尾追加
def _mk_job(db, prefix, pages, doc_name):
    """建 parent + bank + document + job，返回 (job_id, bank_id, doc_id)。"""
    from app.models import PdfDocument, PracticeImportJob, QuestionBank
    from conftest import make_account

    parent = make_account(db, f"{prefix}_p", role="parent")
    doc = PdfDocument(filename=doc_name, subject="数学",
                      storage_path=f"D:/tmp/{doc_name}", content_kind="practice")
    db.add(doc)
    db.flush()
    bank = QuestionBank(user_id=parent.id, title="练习册", subject="数学",
                        grade=5, source="practice_pdf")
    db.add(bank)
    db.flush()
    job = PracticeImportJob(user_id=parent.id, bank_id=bank.id, document_id=doc.id,
                            total_pages=pages, question_start_page=1,
                            question_end_page=pages)
    db.add(job)
    db.commit()
    return job.id, bank.id, doc.id


def test_run_import_job_creates_groups_and_items(setup_db, db, monkeypatch):
    """2 页 → 1 个题组（跨页合并）+ 4 个小题（3 示例 + 1 待做）。"""
    from app.models import PracticeQuestionGroup, Question
    from app.services import practice_import as pi

    job_id, bank_id, _doc_id = _mk_job(db, "rj1", 2, "b.pdf")

    page1 = {
        "page_type": "practice",
        "groups": [{
            "stem": "不计算，运用规律直接写出得数",
            "instruction": "", "lesson_no": 3,
            "lesson_title": "第3课时 一个数除以小数",
            "work_mode": "pattern", "need_process": False,
            "continues_next_page": True,
            "items": [
                {"seq": 1, "y": 0.2, "text": "$1.08 \\div 0.9 = 1.2$",
                 "answer_hint": "1.2", "is_example": True},
                {"seq": 2, "y": 0.4, "text": "$11.106 \\div 0.9 = 12.34$",
                 "answer_hint": "12.34", "is_example": True},
            ],
        }],
        "image_questions": [],
    }
    page2 = {
        "page_type": "practice",
        "groups": [{
            "stem": "不计算，运用规律直接写出得数",
            "instruction": "", "lesson_no": 3,
            "lesson_title": "第3课时 一个数除以小数",
            "work_mode": "pattern", "need_process": False,
            "continues_next_page": False,
            "items": [
                {"seq": 3, "y": 0.2, "text": "$111.06 \\div 0.9 = 123.4$",
                 "answer_hint": "123.4", "is_example": True},
                {"seq": 4, "y": 0.4, "text": "$1111.05 \\div 0.9 =$ ____",
                 "answer_hint": "", "is_example": False},
            ],
        }],
        "image_questions": [],
    }

    # render_page_png 收到的是 pno-1（0-based），所以 fake 的键是 0/1
    monkeypatch.setattr("app.services.practice_image.render_page_png",
                        lambda path, idx, dpi=150: f"png{idx}".encode())
    monkeypatch.setattr("app.services.parsers.math_page.analyze_page",
                        lambda db_, img, **kw: {0: page1, 1: page2}[int(img[-1:])])
    # 该组是 pattern（answer_kind=numeric_list），必须返回 blanks，
    # 否则 answer_json={} → 发布闸门挡下 → todo[0].status 不会是 published
    monkeypatch.setattr(
        "app.services.practice_solve.solve_math_items",
        lambda db_, items, **kw: {
            0: {"kind": "numeric_list", "blanks": ["1234.5"],
                "answer": "1234.5"},
        },
    )

    pi.run_import_job(job_id)

    db.expire_all()
    from app.models import PracticeImportJob

    job = db.get(PracticeImportJob, job_id)
    assert job.status == "done", job.error

    groups = db.query(PracticeQuestionGroup).filter_by(bank_id=bank_id).all()
    assert len(groups) == 1
    assert groups[0].page_start == 1 and groups[0].page_end == 2
    assert groups[0].lesson_no == 3
    assert groups[0].lesson_title == "第3课时 一个数除以小数"

    qs = (db.query(Question).filter_by(bank_id=bank_id)
          .order_by(Question.seq_in_group).all())
    assert len(qs) == 4
    assert sum(1 for q in qs if q.is_example) == 3
    todo = [q for q in qs if not q.is_example]
    assert len(todo) == 1
    assert todo[0].group_id == groups[0].id
    assert todo[0].answer == "1234.5"
    assert json.loads(todo[0].answer_json)["blanks"] == ["1234.5"]
    assert todo[0].status == "published"
    # 示例行也发布（前端要读它来展示），但不进每日一练（Task 15 过滤）
    assert all(q.status == "published" for q in qs if q.is_example)


def test_run_import_job_skips_non_practice_pages(setup_db, db, monkeypatch):
    """目录页/答案页不入库，但要留页记录。"""
    from app.models import PracticeImportPage, PracticeQuestionGroup, Question
    from app.services import practice_import as pi

    job_id, bank_id, doc_id = _mk_job(db, "rj2", 2, "c.pdf")

    monkeypatch.setattr("app.services.practice_image.render_page_png",
                        lambda path, idx, dpi=150: b"x")
    monkeypatch.setattr("app.services.parsers.math_page.analyze_page",
                        lambda db_, img, **kw: {
                            "page_type": "toc", "groups": [],
                            "image_questions": []})

    pi.run_import_job(job_id)

    db.expire_all()
    assert db.query(PracticeQuestionGroup).filter_by(bank_id=bank_id).count() == 0
    assert db.query(Question).filter_by(bank_id=bank_id).count() == 0
    pages = db.query(PracticeImportPage).filter_by(document_id=doc_id).all()
    assert len(pages) == 2
    assert all(p.page_type == "toc" for p in pages)


def test_run_import_job_records_page_rows(setup_db, db, monkeypatch):
    from app.models import PracticeImportPage
    from app.services import practice_import as pi

    job_id, _bank_id, doc_id = _mk_job(db, "rj3", 1, "d.pdf")

    monkeypatch.setattr("app.services.practice_image.render_page_png",
                        lambda path, idx, dpi=150: b"x")
    monkeypatch.setattr("app.services.parsers.math_page.analyze_page",
                        lambda db_, img, **kw: {
                            "page_type": "practice",
                            "groups": [{
                                "stem": "", "instruction": "", "lesson_no": None,
                                "lesson_title": "", "work_mode": "oral",
                                "need_process": False,
                                "continues_next_page": False,
                                "items": [{"seq": 1, "y": 0.1, "text": "1+1=____",
                                           "answer_hint": "", "is_example": False}],
                            }],
                            "image_questions": []})
    monkeypatch.setattr(
        "app.services.practice_solve.solve_math_items",
        lambda db_, items, **kw: {0: {"kind": "number", "answer": "2"}},
    )

    pi.run_import_job(job_id)

    db.expire_all()
    pages = db.query(PracticeImportPage).filter_by(document_id=doc_id).all()
    assert len(pages) == 1
    assert pages[0].page_no == 1
    assert pages[0].page_type == "practice"
    assert pages[0].group_count == 1


def test_run_import_job_marks_failed_page(setup_db, db, monkeypatch):
    """AI 抛异常时该页标失败，job 标 failed 且可重试。"""
    from app.models import PracticeImportJob, PracticeImportPage
    from app.services import practice_import as pi

    job_id, _bank_id, doc_id = _mk_job(db, "rj4", 1, "e.pdf")

    monkeypatch.setattr("app.services.practice_image.render_page_png",
                        lambda path, idx, dpi=150: b"x")

    def _boom(db_, img, **kw):
        raise RuntimeError("vision down")

    monkeypatch.setattr("app.services.parsers.math_page.analyze_page", _boom)

    pi.run_import_job(job_id)

    db.expire_all()
    job = db.get(PracticeImportJob, job_id)
    assert job.status == "failed"
    assert job.failed_pages == "[1]"
    pages = db.query(PracticeImportPage).filter_by(document_id=doc_id).all()
    assert pages[0].status == "failed"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k run_import_job -v`
Expected: FAIL — 现有 `run_import_job` 不建题组，`len(groups) == 1` 失败

- [ ] **Step 3: 在 `practice_image.py` 暴露 `render_page_png`**

`backend/app/services/practice_image.py` 里，在 `_render_page_png` 之后追加：

```python
def render_page_png(pdf_path: str, page_index: int, dpi: int = 150) -> bytes:
    """把 PDF 某页渲染成 PNG 字节流（page_index 0-based）。失败返回 b""。

    整页分析用：一次视觉调用同时拿到 OCR 文本与结构，取代旧的
    `_ocr_text` + `detect_image_questions` 两次调用。
    """
    try:
        return _render_page_png(pdf_path, page_index, dpi=dpi)
    except Exception:
        return b""
```

先确认 `_render_page_png` 的真实名字与返回类型（`rg -n "_render_page_png" app/services/practice_image.py`）；
若它返回路径而非 bytes，这里要转成读取文件字节。

- [ ] **Step 4: 重写编排**

在 `practice_import.py` 里**追加**下面这些新函数（旧函数暂留，Task 16 删）：

```python
def _kind_of(work_mode: str) -> str:
    """work_mode → build_drafts 的 kind 参数。

    ⚠️ 实际已不参与 qtype 决策：`build_drafts` 在 `work_mode` 非空时直接用
    `legacy_qtype_of(mode)`，`kind` 只被 `work_mode` 为空的旧路径读取。
    保留它只为让 item dict 结构稳定（旧路径/调试时还能看到 kind）。
    """
    return {
        "oral": "oral", "equation": "equation", "pattern": "fill",
        "letter_pattern": "fill", "compare": "fill", "unit_compare": "fill",
        "vertical": "vertical", "step": "step", "fill_vertical": "vertical",
        "geometry": "image", "app": "app", "choice": "other", "judge": "other",
        "other": "other",
    }.get(work_mode, "other")


def _groups_from_pages(page_results: list[tuple[int, dict]]) -> list[dict]:
    """把各页分析结果展开成待合并的题组列表（带 page_start/page_end/key）。"""
    groups: list[dict] = []
    for pno, result in page_results:
        if result.get("page_type") != "practice":
            continue
        for idx, g in enumerate(result.get("groups") or []):
            items = [{**it, "page": pno} for it in (g.get("items") or [])]
            groups.append({
                "key": f"{pno}-{idx:02d}",     # 两位补零，字符串排序也正确
                "page_start": pno,
                "page_end": pno,
                "stem": g.get("stem") or "",
                "instruction": g.get("instruction") or "",
                "lesson_no": g.get("lesson_no"),
                "lesson_title": g.get("lesson_title") or "",
                "work_mode": g.get("work_mode") or "other",
                "need_process": bool(g.get("need_process")),
                "continues_next_page": bool(g.get("continues_next_page")),
                "incomplete": False,
                "items": items,
            })
    return groups


def _image_group(pno: int, info: dict, pdf_path: str) -> dict | None:
    """裁出图片题的图，返回一个自成一组、items 只有 1 条的题组。"""
    from .practice_image import crop_question_image

    out = (
        f"uploads/practice_images/p{pno}_"
        f"{int(info['start'] * 100)}_{int(info['end'] * 100)}.png"
    )
    saved = crop_question_image(pdf_path, pno - 1, info["start"], info["end"], out)
    if not saved:
        return None
    title = info.get("title") or f"第{pno}页 图形题"
    return {
        "key": f"{pno}-img",
        "page_start": pno,
        "page_end": pno,
        "stem": title,
        "instruction": "",
        "lesson_no": None,
        "lesson_title": "",
        "work_mode": "geometry",
        "need_process": True,
        "continues_next_page": False,
        "incomplete": False,
        "items": [{
            "seq": 1, "y": info["start"], "text": title,
            "answer_hint": "", "is_example": False,
            "page": pno, "image_path": saved,
        }],
    }


def _read_upload(path: str) -> bytes:
    import os

    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return b""


def _extract_answer(raw: str) -> str:
    """从视觉模型的 JSON 里取 answer。"""
    try:
        data = json.loads(raw or "{}")
    except (ValueError, TypeError):
        m = re.search(r"\{[\s\S]*\}", raw or "")
        if not m:
            return ""
        try:
            data = json.loads(m.group(0))
        except (ValueError, TypeError):
            return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("answer") or "").strip()


def _solve_groups(db, groups: list[dict], *, on_progress=None) -> None:
    """按组求答案，结果写回 it["answer"] / it["blanks"] / it["correct_index"]。

    示例行跳过（页面已印答案，用它自己的 answer_hint）。
    图片题（有 image_path）走视觉求答案；纯文本题走 solve_math_items。
    """
    from .ai import vision_json
    from .practice_solve import solve_math_items

    # 1) 文本题：按 answer_kind 分流
    solve_items: list[dict] = []
    solve_refs: list[dict] = []
    choice_refs: list[dict] = []
    for g in groups:
        for it in g["items"]:
            if it.get("is_example") or it.get("image_path"):
                continue
            # 示例行以外的题才求解
            if g["work_mode"] in ("choice", "judge"):
                choice_refs.append(it)
                continue
            solve_items.append({
                "question": it.get("text") or "",
                "work_mode": g["work_mode"],
            })
            solve_refs.append(it)

    # 2) 选择题：单独问「正确选项是哪个」
    for it in choice_refs:
        it["correct_index"] = _solve_choice(db, it.get("text") or "")
        if it["correct_index"] is not None:
            it["answer"] = _LETTERS[it["correct_index"]] if (
                it["correct_index"] < len(_LETTERS)) else ""

    solved = solve_math_items(db, solve_items, on_progress=on_progress) if solve_items else {}
    for idx, payload in solved.items():
        if 0 <= idx < len(solve_refs):
            ref = solve_refs[idx]
            ref["answer"] = payload.get("answer") or ""
            ref["blanks"] = payload.get("blanks") or []

    # 3) 图片题：把裁出的 PNG 送视觉模型算答案
    for g in groups:
        for it in g["items"]:
            if not it.get("image_path") or it.get("is_example"):
                continue
            if (it.get("answer") or "").strip():
                continue
            try:
                raw = vision_json(
                    db,
                    _read_upload(it["image_path"]),
                    system="你是小学数学老师。看图片里的题目，只输出 JSON："
                           '{"answer":"最终结果数字"}。算不出就输出 {"answer":""}。',
                    prompt="算出这道题的最终答案。",
                )
                it["answer"] = _extract_answer(raw)
            except Exception:
                it["answer"] = ""     # 进「待补答案」由家长填


_LETTERS = "ABCD"


def _solve_choice(db, question: str) -> int | None:
    """让模型选出正确选项（0 起）。失败返回 None（该题进待补，不瞎猜）。"""
    if not question.strip():
        return None
    try:
        from .ai import get_provider

        provider = get_provider(db)
        if provider.name == "fake":
            return None
        raw = provider.generate(
            prompt=(
                "下面是一道选择题，请判断正确选项。只输出 JSON："
                '{"correct":"A"}，correct 只能是 A/B/C/D。\n\n' + question
            ),
            system="你是小学数学老师，负责判断选择题的正确选项。只输出 JSON。",
            json_mode=True,
        )
        data = json.loads(raw or "{}")
        letter = str(data.get("correct") or "").strip().upper()
        return _LETTERS.index(letter) if letter in _LETTERS else None
    except Exception:
        return None


def _record_page(db, document_id: int, page_no: int, page_type: str,
                 raw_text: str, group_count: int, status: str) -> None:
    """落一行页记录（唯一约束 document_id+page_no，用 upsert 语义）。"""
    from ..models import PracticeImportPage

    row = (db.query(PracticeImportPage)
           .filter_by(document_id=document_id, page_no=page_no).first())
    if row is None:
        row = PracticeImportPage(document_id=document_id, page_no=page_no)
        db.add(row)
    row.page_type = page_type
    row.raw_text = raw_text[:60000]
    row.group_count = group_count
    row.status = status
    db.commit()


def _tick(job_id: int, done: int, total: int, items: int) -> None:
    """独立 session 刷进度（长分析期间主 session 缓存会过期）。"""
    from ..database import SessionLocal as _SL
    from ..models import PracticeImportJob as _Job

    s2 = _SL()
    try:
        j2 = s2.get(_Job, job_id)
        if j2 is not None:
            j2.done_pages = min(done, total)
            j2.question_count = items
            s2.commit()
    except Exception:
        s2.rollback()
    finally:
        s2.close()


def _set_counts(job_id: int, *, aligned: int, questions: int) -> None:
    from ..database import SessionLocal as _SL
    from ..models import PracticeImportJob as _Job

    s2 = _SL()
    try:
        j2 = s2.get(_Job, job_id)
        if j2 is not None:
            j2.aligned_count = aligned
            j2.question_count = questions
            s2.commit()
    except Exception:
        s2.rollback()
    finally:
        s2.close()


def run_import_job(job_id: int, retry_pages: list[int] | None = None) -> None:
    """后台执行导入：逐页视觉分析 → 跨页合并 → 求答案 → 建题组 → 挂小题 → 发布。

    `retry_pages` 非空时只重跑这些页（会先删掉这些页对应的旧题组与小题）。
    """
    from ..database import SessionLocal
    from ..models import (
        PdfDocument, PracticeImportJob, PracticeImportPage,
        PracticeQuestionGroup, Question, QuestionBank,
    )
    from ..routers.bank import _persist_drafts
    from .parsers.math_page import analyze_page
    from .practice_image import render_page_png

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
        job.aligned_count = 0
        job.question_count = 0
        job.published_count = 0
        db.commit()

        q_start = job.question_start_page or 1
        # 答案页可选：没填就用 total_pages 兜底（三处派生逻辑必须字面一致）
        q_end = job.question_end_page or job.total_pages or q_start
        if q_end < q_start:
            q_end = q_start
        pages = list(range(q_start, q_end + 1))
        if retry_pages:
            wanted = set(retry_pages)
            picked_pages = [p for p in pages if p in wanted]
            if picked_pages:
                pages = picked_pages

        # 重跑：先删这些页对应的题组与小题（group_id 无外键，必须显式删）
        if retry_pages:
            old = (db.query(PracticeQuestionGroup)
                   .filter(PracticeQuestionGroup.bank_id == bank.id,
                           PracticeQuestionGroup.page_start.in_(pages))
                   .all())
            gids = [g.id for g in old]
            if gids:
                db.query(Question).filter(
                    Question.group_id.in_(gids)).delete(synchronize_session=False)
                db.query(PracticeQuestionGroup).filter(
                    PracticeQuestionGroup.id.in_(gids)).delete(
                    synchronize_session=False)
            db.query(PracticeImportPage).filter(
                PracticeImportPage.document_id == doc.id,
                PracticeImportPage.page_no.in_(pages),
            ).delete(synchronize_session=False)
            db.commit()

        # 逐页分析
        page_results: list[tuple[int, dict]] = []
        failed_pages: list[int] = []
        image_groups: list[dict] = []
        seen_items = 0
        for idx, pno in enumerate(pages, start=1):
            img = render_page_png(doc.storage_path, pno - 1, dpi=150)
            if not img:
                failed_pages.append(pno)
                _record_page(db, doc.id, pno, "practice", "", 0, "failed")
                _tick(job_id, idx, len(pages), seen_items)
                continue
            try:
                result = analyze_page(db, img, subject=bank.subject or "数学")
            except Exception:
                failed_pages.append(pno)
                _record_page(db, doc.id, pno, "practice", "", 0, "failed")
                _tick(job_id, idx, len(pages), seen_items)
                continue

            page_results.append((pno, result))
            _record_page(
                db, doc.id, pno, result.get("page_type") or "practice",
                json.dumps(result, ensure_ascii=False),
                len(result.get("groups") or []), "ok",
            )
            for info in result.get("image_questions") or []:
                g = _image_group(pno, info, doc.storage_path)
                if g:
                    image_groups.append(g)
            seen_items += sum(len(g.get("items") or [])
                              for g in (result.get("groups") or []))
            _tick(job_id, idx, len(pages), seen_items)

        # 跨页合并（图片题自成一组，不参与合并）
        groups = _groups_from_pages(page_results)
        groups = merge_cross_page_groups(groups) + image_groups
        groups.sort(key=lambda g: (g["page_start"], g["key"]))

        job.status = "aligning"
        job.question_count = sum(len(g["items"]) for g in groups)
        db.commit()

        _solve_groups(
            db, groups,
            on_progress=lambda done, total: _set_counts(
                job_id, aligned=done, questions=total),
        )
        job.aligned_count = sum(
            1 for g in groups for it in g["items"] if (it.get("answer") or "").strip()
        )
        db.commit()

        # 题组先建，小题后挂
        all_drafts = []
        for g in groups:
            row = PracticeQuestionGroup(
                bank_id=bank.id, user_id=bank.user_id,
                lesson_no=g.get("lesson_no"),
                lesson_title=g.get("lesson_title") or "",
                stem=g.get("stem") or "",
                instruction=g.get("instruction") or "",
                work_mode=g.get("work_mode") or "other",
                need_process=bool(g.get("need_process")),
                page_start=g["page_start"], page_end=g["page_end"],
                source_document_id=job.document_id,
                incomplete=bool(g.get("incomplete")),
            )
            db.add(row)
            db.flush()

            items = []
            for seq, it in enumerate(g["items"], start=1):
                # 示例行的答案来自页面印好的 answer_hint（AI 不重算）
                answer = (it.get("answer") or it.get("answer_hint") or "").strip()
                items.append({
                    "kind": _kind_of(g["work_mode"]),
                    "question": it.get("text") or "",
                    "answer": answer,
                    "blanks": it.get("blanks") or [],
                    "correct_index": it.get("correct_index"),
                    "seq_in_group": seq,
                    "is_example": bool(it.get("is_example")),
                    "work_mode": g.get("work_mode") or "other",
                    "lesson_no": g.get("lesson_no") or g["page_start"],
                    "lesson_title": g.get("lesson_title") or "",
                    "image_path": it.get("image_path") or "",
                    "page": g["page_start"],
                    "group_id": row.id,
                })
            all_drafts.extend(build_drafts(items, document_id=job.document_id))
        db.commit()

        _persist_drafts(db, bank, all_drafts, "practice_pdf")
        bank.source = "practice_pdf"     # _persist_drafts 会把 manual 改成 third_party
        db.commit()

        # 示例行也发布：前端要读它来展示「印好的示例」，但不进每日一练
        # （task_gen._pick_practice_questions 过滤 is_example == False）
        db.query(Question).filter(
            Question.bank_id == bank.id, Question.is_example.is_(True)
        ).update({"status": "published"}, synchronize_session=False)
        job.published_count = publish_aligned(db, bank.id)
        db.commit()

        job.failed_pages = json.dumps(sorted(failed_pages))
        job.done_pages = max(0, len(pages) - len(failed_pages))
        job.status = "failed" if failed_pages else "done"
        job.error = f"{len(failed_pages)} 页识别失败，可重试" if failed_pages else ""
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

> **`lesson_no` 兜底**：练习册的「第N课时」在每个单元会重新从 1 开始，直接用 AI 给的
> 课时号作 `lesson_no` 会撞车（旧实现踩过：1769 题压成 10 组）。所以这里
> `lesson_no = g["lesson_no"] or g["page_start"]` —— 有课时号用课时号，没有用页码；
> 撞车风险由 `PracticeQuestionGroup` 的组内序号（`seq_in_group`）+ 题组 id 隔离，
> 而 `_pick_practice_questions` 按 `lesson_no` 推进时仍可能有跨单元重号。
> **若观察到跨单元撞车，改成「页序作 lesson_no，真实课时号只进 lesson_title」**（旧行为）。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k run_import_job -v`
Expected: PASS（4 passed）

- [ ] **Step 6: 注意：此时旧测试仍是红灯（预期）**

`tests/test_practice_import.py` 里依赖旧管线（`_ocr_text`、旧 `run_import_job` 断言）的
用例会 FAIL。**这是预期的**，Task 16 统一处理。预期红灯清单：

- `test_run_import_job_publishes_aligned_and_records_failures`
- `test_run_import_job_all_ok_marks_done`
- `test_qtype_category_is_derived_not_hardcoded`
- `test_equation_section_kind`

除这 4 个以外**不应**出现新增红灯；若有，先排查是不是本任务引入的 bug。

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/practice_import.py backend/app/services/practice_image.py backend/tests/test_practice_groups.py
git commit -m "feat(practice): 重写导入编排（整页分析 → 跨页合并 → 求答案 → 题组+小题入库）"
```

---

## Task 13: `bank.py` 提交分派与题目列表

**Files:**
- Modify: `backend/app/routers/bank.py`（`list_bank_questions`、`submit_bank`）
- Test: `backend/tests/test_practice_groups.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_practice_groups.py 末尾追加
def _bank_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.bank import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_submit_dispatches_by_work_mode(setup_db, db):
    """有 work_mode 的题走 grade_practice_item（number 判分）。"""
    from app.models import Question, QuestionBank
    from conftest import parent_child

    # 必须用 parent_child：require_learning_user 会校验家长绑定
    parent, child, _ph, child_h = parent_child(db)
    bank = QuestionBank(user_id=child.id, title="卷", subject="数学", grade=5)
    db.add(bank)
    db.flush()
    q = Question(bank_id=bank.id, user_id=child.id, qtype="oral",
                 qtype_category="subjective", question="1+1=____", answer="2",
                 answer_json="{}", work_mode="oral", status="published")
    db.add(q)
    db.commit()

    r = _bank_client().post("/api/banks/submit", headers=child_h, json={
        "bank_id": bank.id,
        "answers": [{"question_id": q.id, "text": "2"}],
    })
    assert r.status_code == 200, r.text
    assert r.json()["answers"][0]["is_correct"] is True


def test_submit_wrong_answer_is_false(setup_db, db):
    from app.models import Question, QuestionBank
    from conftest import parent_child

    parent, child, _ph, child_h = parent_child(db)
    bank = QuestionBank(user_id=child.id, title="卷", subject="数学", grade=5)
    db.add(bank)
    db.flush()
    q = Question(bank_id=bank.id, user_id=child.id, qtype="oral",
                 qtype_category="subjective", question="1+1=____", answer="2",
                 answer_json="{}", work_mode="oral", status="published")
    db.add(q)
    db.commit()

    r = _bank_client().post("/api/banks/submit", headers=child_h, json={
        "bank_id": bank.id,
        "answers": [{"question_id": q.id, "text": "3"}],
    })
    assert r.status_code == 200
    assert r.json()["answers"][0]["is_correct"] is False


def test_bank_questions_include_group_info(setup_db, db):
    from app.models import Question, QuestionBank
    from conftest import parent_child

    parent, child, _ph, child_h = parent_child(db)
    bank = QuestionBank(user_id=child.id, title="卷", subject="数学", grade=5)
    db.add(bank)
    db.flush()
    g = PracticeQuestionGroup(bank_id=bank.id, user_id=child.id,
                              stem="直接写出得数", work_mode="pattern",
                              page_start=1, page_end=1)
    db.add(g)
    db.flush()
    q = Question(bank_id=bank.id, user_id=child.id, qtype="fill_blank",
                 qtype_category="blank", question="1+1=____", answer="2",
                 status="published", group_id=g.id, seq_in_group=2,
                 work_mode="pattern")
    db.add(q)
    db.commit()

    r = _bank_client().get(f"/api/banks/{bank.id}/questions", headers=child_h)
    assert r.status_code == 200
    item = r.json()[0]
    assert item["group_stem"] == "直接写出得数"
    assert item["work_mode"] == "pattern"
    assert item["input_ui"] == "keypad"
    assert item["answer_kind"] == "numeric_list"
    assert item["seq_in_group"] == 2
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k "submit_dispatches or group_info" -v`
Expected: FAIL — 响应缺 `group_stem` 等键

- [ ] **Step 3: 改题目列表返回体**

`bank.py` 的 `list_bank_questions` 整体替换为：

```python
@router.get("/{bank_id}/questions")
def list_bank_questions(
    bank_id: int,
    ids: str = "",
    _auth: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..core.work_modes import answer_kind_of, input_ui_of
    from ..models import PracticeQuestionGroup

    q = db.query(Question).filter_by(bank_id=bank_id, status="published")
    if ids.strip():
        qids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        if qids:
            q = q.filter(Question.id.in_(qids))
    qs = q.order_by(Question.id).all()
    pids = {x.passage_id for x in qs if x.passage_id}
    passages = {}
    if pids:
        for p in db.query(ReadingPassage).filter(ReadingPassage.id.in_(pids)).all():
            passages[p.id] = {"id": p.id, "title": p.title, "content": p.content,
                              "subject": p.subject}

    gids = {x.group_id for x in qs if x.group_id}
    groups = {}
    if gids:
        for g in db.query(PracticeQuestionGroup).filter(
                PracticeQuestionGroup.id.in_(gids)).all():
            groups[g.id] = g

    out = []
    for item in qs:
        g = groups.get(item.group_id)
        mode = item.work_mode or (g.work_mode if g else "")
        out.append({
            "id": item.id, "qtype": item.qtype,
            "qtype_category": item.qtype_category,
            "question": item.question, "options": json.loads(item.options or "[]"),
            "answer": item.answer, "analysis": item.analysis,
            "difficulty": item.difficulty,
            "tags": json.loads(item.tags or "{}"),
            "passage_id": item.passage_id,
            "passage": item.passage_id and passages.get(item.passage_id),
            # 题组两级：前端据此展示题干/示例、按 input_ui 渲染
            "group_id": item.group_id,
            "group_stem": (g.stem if g else ""),
            "seq_in_group": item.seq_in_group,
            "is_example": item.is_example,
            "work_mode": mode,
            "input_ui": input_ui_of(mode),
            "answer_kind": answer_kind_of(mode),
        })
    return out
```

- [ ] **Step 4: 改 submit 分派**

`bank.py` 的 `submit_bank` 里，把判分那两行替换成：

```python
        answer_json = json.loads(qq.answer_json or "{}")
        student = {k: a.get(k) for k in ("selected_index", "blanks", "pairs", "text")
                   if a.get(k) is not None}

        mode = (getattr(qq, "work_mode", "") or "").strip()
        if mode:
            # 有 work_mode → 走练习册判分门面（按 answer_kind 分派）
            from ..services.practice_grade import grade_practice_item

            pr = grade_practice_item(
                db, qq,
                student_answer=str(a.get("text") or "").strip(),
                blanks=a.get("blanks"),
            )
            r = {
                "is_correct": pr.get("is_correct"),
                "correct_answer_text": qq.answer,
                "detail": pr,
            }
        elif qq.qtype_category == "subjective":
            r = grade_subjective_with_ai(db, answer_json, student)
        else:
            r = grade_question(qq.qtype_category, answer_json, student)
```

`record_answer` / `Mistake` 里的 `is_correct=r["is_correct"] is True` 已是严格判断，
`None`（待判）不会被记成错题 —— 无需改。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k "submit or group_info" -v`
Expected: PASS（3 passed）

- [ ] **Step 6: 跑 bank 回归**

Run: `cd backend && python -m pytest -q -k "bank or submit"`
Expected: 全部 PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/routers/bank.py backend/tests/test_practice_groups.py
git commit -m "feat(practice): 题目列表返回题组信息，submit 按 work_mode 分派判分"
```

---

## Task 14: 导入路由（题组浏览、页类型修正、答案页可选）

**Files:**
- Modify: `backend/app/routers/practice_import.py`
- Modify: `backend/app/main.py`（续跑 `q_end`）
- Test: `backend/tests/test_practice_groups.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_practice_groups.py 末尾追加
def _practice_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.practice_import import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_missing_answers_excludes_examples(setup_db, db):
    """示例行不该出现在「待补答案」清单里（孩子不用做）。"""
    from app.models import Question, QuestionBank
    from conftest import parent_child

    parent, child, parent_h, _ch = parent_child(db)
    bank = QuestionBank(user_id=parent.id, title="册", subject="数学", grade=5,
                        source="practice_pdf")
    db.add(bank)
    db.flush()
    db.add(Question(bank_id=bank.id, user_id=parent.id, qtype="fill_blank",
                    qtype_category="blank", question="示例", answer="",
                    status="pending", is_example=True, work_mode="pattern"))
    db.add(Question(bank_id=bank.id, user_id=parent.id, qtype="fill_blank",
                    qtype_category="blank", question="待做", answer="",
                    status="pending", is_example=False, work_mode="pattern"))
    db.commit()

    r = _practice_client().get(
        f"/api/practice-import/missing-answers?bank_id={bank.id}",
        headers=parent_h)
    assert r.status_code == 200
    assert [i["question"] for i in r.json()["items"]] == ["待做"]


def test_questions_endpoint_returns_work_mode(setup_db, db):
    from app.models import Question, QuestionBank
    from conftest import parent_child

    parent, _child, parent_h, _ch = parent_child(db)
    bank = QuestionBank(user_id=parent.id, title="册", subject="数学", grade=5,
                        source="practice_pdf")
    db.add(bank)
    db.flush()
    db.add(Question(bank_id=bank.id, user_id=parent.id,
                    qtype="fill_blank", qtype_category="blank",
                    question="1+1=____", answer="2", status="published",
                    work_mode="pattern"))
    db.commit()

    r = _practice_client().get(
        f"/api/practice-import/questions?bank_id={bank.id}", headers=parent_h)
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["work_mode"] == "pattern"
    assert item["answer_kind"] == "numeric_list"
    assert item["input_ui"] == "keypad"


def test_page_types_endpoint(setup_db, db):
    from app.models import PdfDocument, PracticeImportPage
    from conftest import make_account, auth_headers

    parent = make_account(db, "pg_p", role="parent")
    doc = PdfDocument(filename="e.pdf", subject="数学", storage_path="D:/e.pdf",
                      content_kind="practice")
    db.add(doc)
    db.flush()
    db.add(PracticeImportPage(document_id=doc.id, page_no=1, page_type="toc",
                              group_count=0))
    db.add(PracticeImportPage(document_id=doc.id, page_no=2,
                              page_type="practice", group_count=3))
    db.commit()

    r = _practice_client().get(
        f"/api/practice-import/pages?document_id={doc.id}",
        headers=auth_headers(parent))
    assert r.status_code == 200
    pages = r.json()["pages"]
    assert [p["page_no"] for p in pages] == [1, 2]
    assert pages[0]["page_type"] == "toc"


def test_patch_page_type(setup_db, db):
    from app.models import PdfDocument, PracticeImportPage
    from conftest import make_account, auth_headers

    parent = make_account(db, "pp_p", role="parent")
    doc = PdfDocument(filename="f.pdf", subject="数学", storage_path="D:/f.pdf",
                      content_kind="practice")
    db.add(doc)
    db.flush()
    db.add(PracticeImportPage(document_id=doc.id, page_no=1, page_type="toc"))
    db.commit()

    r = _practice_client().patch(
        f"/api/practice-import/pages/1?document_id={doc.id}",
        headers=auth_headers(parent), json={"page_type": "practice"})
    assert r.status_code == 200
    assert r.json()["page_type"] == "practice"

    db.expire_all()
    row = db.query(PracticeImportPage).filter_by(document_id=doc.id,
                                                 page_no=1).one()
    assert row.page_type == "practice"


def test_patch_page_type_rejects_unknown():
    from app.models import PdfDocument, PracticeImportPage
    ...
```

> 最后一条 `test_patch_page_type_rejects_unknown` 请补全：建 parent + doc + page，
> PATCH `{"page_type": "garbage"}`，断言 `status_code == 400`。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k "missing_answers or returns_work_mode or page_types or patch_page_type" -v`
Expected: FAIL — `/api/practice-import/pages` 404

- [ ] **Step 3: 改 `missing-answers` 过滤示例**

`practice_import.py` 的 `missing_answers` 查询加条件：

```python
    q = (
        db.query(Question)
        .filter(Question.bank_id == bank_id,
                Question.status == "pending",
                (Question.answer == "") | (Question.answer.is_(None)),
                Question.is_example.is_(False))     # 示例行不是待做题
        .order_by(Question.lesson_no, Question.id)
    )
```

- [ ] **Step 4: `questions` 路由返回 work_mode 三件套**

`practice_import.py` 的 `list_questions` 返回体每项补：

```python
        "work_mode": item.work_mode or "",
        "answer_kind": answer_kind_of(item.work_mode or ""),
        "input_ui": input_ui_of(item.work_mode or ""),
        "group_id": item.group_id,
        "seq_in_group": item.seq_in_group,
        "is_example": item.is_example,
```

文件顶部加：

```python
from ..core.work_modes import answer_kind_of, input_ui_of
```

- [ ] **Step 5: 新增学科校验（拒绝未实现的学科）**

spec §7 要求「上传 语文/英语 练习册时返回 400，不静默按数学乱导」。
`import_practice_pdf` 的签名里**没有 `body`** —— 学科在已加载的 `bank` 上。
在 `bank = _require_own_bank(bank_id, user, db)` 之后、`_vision_ready` 校验之前加：

```python
    from ..core.subjects import is_implemented

    if not is_implemented(bank.subject):
        raise HTTPException(
            status_code=400,
            detail=f"{bank.subject or '该'}学科练习册解析器尚未实现（当前仅支持数学）",
        )
```

补一条测试（`_practice_client()` 已在上面的测试块里建好）：

```python
# backend/tests/test_practice_groups.py 末尾追加
def test_import_rejects_unimplemented_subject(setup_db, db):
    """语文/英语练习册返回 400，不静默按数学解析。"""
    from app.models import QuestionBank
    from conftest import parent_child

    parent, _child, parent_h, _ch = parent_child(db)
    bank = QuestionBank(user_id=parent.id, title="语文练习册",
                        subject="语文", grade=5, source="practice_pdf")
    db.add(bank)
    db.commit()

    r = _practice_client().post(
        f"/api/banks/{bank.id}/import-practice-pdf",
        headers=parent_h,
        files={"file": ("a.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"answer_start_page": "1", "answer_end_page": "2"},
    )
    assert r.status_code == 400
    assert "尚未实现" in r.json()["detail"]
```

- [ ] **Step 6: 新增页类型查询与修正路由**

```python
class PageTypeReq(BaseModel):
    page_type: str


_PAGE_TYPES = ("practice", "toc", "answer_key", "cover", "blank")


@router.get("/api/practice-import/pages")
def list_pages(document_id: int, _auth: User = Depends(require_learning_user),
               db: Session = Depends(get_db)):
    """列出某文档已分析的页（供家长排查/修正页类型）。"""
    from ..models import PracticeImportPage

    rows = (db.query(PracticeImportPage)
            .filter_by(document_id=document_id)
            .order_by(PracticeImportPage.page_no).all())
    return {"pages": [{
        "page_no": r.page_no, "page_type": r.page_type,
        "group_count": r.group_count, "status": r.status,
    } for r in rows]}


@router.patch("/api/practice-import/pages/{page_no}")
def patch_page_type(page_no: int, req: PageTypeReq, document_id: int,
                    _auth: User = Depends(require_role("parent", "admin")),
                    db: Session = Depends(get_db)):
    """把某页的类型改掉（如 toc → practice），供之后重新解析该页。"""
    from ..models import PracticeImportPage

    if req.page_type not in _PAGE_TYPES:
        raise HTTPException(400, f"page_type 必须是 {_PAGE_TYPES} 之一")
    row = (db.query(PracticeImportPage)
           .filter_by(document_id=document_id, page_no=page_no).first())
    if row is None:
        raise HTTPException(404, "该页没有分析记录")
    row.page_type = req.page_type
    db.commit()
    return {"page_no": row.page_no, "page_type": row.page_type}
```

- [ ] **Step 7: 答案页改为可选 —— 先抽公共函数，再改三处调用**

**先抽一个共用函数**，从结构上消除「三处派生不一致」这类回归：

`backend/app/routers/practice_import.py` 里新增（放在路由定义之前）：

```python
def _derive_page_range(
    *, question_start_page, question_end_page,
    answer_start_page, answer_end_page, total_pages: int,
) -> tuple[int, int]:
    """派生题面页范围。

    答案页可选：不填答案页时题面页到最后一页为止。
    ⚠️ 绝不能写成 `(answer_start_page or 1) - 1` —— 答案页为 None 时会得到 0 页。
    提供了答案页则收窄到答案页之前，少跑几次视觉调用。
    """
    q_start = int(question_start_page or 1)
    if q_start < 1:
        q_start = 1
    q_end = question_end_page
    if not q_end and answer_start_page:
        q_end = int(answer_start_page) - 1
    q_end = int(q_end or total_pages or q_start)
    if q_end < q_start:
        q_end = q_start
    return q_start, q_end
```

然后**三处**都改用它（表达式不再各自手写）：

| 文件 | 位置 | 改法 |
| --- | --- | --- |
| `app/routers/practice_import.py` | 上传接口（原 `:169`） | `q_start, q_end = _derive_page_range(...)`，入参用函数已有的 `total` |
| `app/routers/practice_import.py` | `_job_payload`（原 `:192`） | `q_start, q_end = _derive_page_range(...)`，入参用 `job.total_pages` |
| `app/main.py` | 断点续跑（原 `:87`） | `from .routers.practice_import import _derive_page_range`，调用同签名 |

`run_import_job`（`practice_import.py:559`）里也要改成调用它：

```python
    from ..routers.practice_import import _derive_page_range

    q_start, q_end = _derive_page_range(
        question_start_page=job.question_start_page,
        question_end_page=job.question_end_page,
        answer_start_page=job.answer_start_page,
        answer_end_page=job.answer_end_page,
        total_pages=job.total_pages or 1,
    )
```

**并把上传校验里的「必须填写答案页起止页」400 去掉**，改为「填了才校验范围」。

⚠️ **注意上传接口的参数是 `str = Form("")`，不是 `int | None`**。必须先经 `_int()`
解析成整数再比较，否则 `"" < 1` 会抛 `TypeError`。原文在 `:114-118`：

```python
    a_start, a_end = _int(answer_start_page), _int(answer_end_page)
    if not a_start or not a_end:
        raise HTTPException(status_code=400, detail="必须填写答案页起止页（扫描版无法自动识别）")
```

改成（**必须放在 `total` 计算之后**，因为要校验 `a_end > total`）：

```python
    a_start, a_end = _int(answer_start_page), _int(answer_end_page)
    if a_start is not None and a_end is not None:
        if a_start < 1 or a_end > total:
            raise HTTPException(status_code=400, detail="答案页范围不合法")
        if a_start > a_end:
            raise HTTPException(status_code=400, detail="答案页起止顺序不对")
```

> ⚠️ **位置很重要**：这段校验要用到 `total`（PDF 页数），必须挪到
> `render_pages()` 之后（原代码 `:163` 附近）。原来的「必填」校验在 `:114-118`
> （`total` 之前），照搬会 `NameError`，并连带打挂**保留**的
> `test_import_rejects_without_vision_model`（它传 `answer_start_page=100/end=107`）。

- [ ] **Step 8: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k "missing_answers or returns_work_mode or page_types or patch_page_type" -v`
Expected: PASS（5 passed）

Run: `cd backend && python -m pytest tests/test_practice_import.py -k "rejects or vision" -v`
Expected: PASS（确认 `test_import_rejects_without_vision_model` 没被打挂）

- [ ] **Step 9: `pdf.py` 删文档时清理题组与页记录**

`PracticeImportPage.document_id` 是无 `ondelete` 外键，`PracticeQuestionGroup.source_document_id`
是 `SET NULL`。删一本已导入的练习册时：MySQL（生产，FK 强制）会因
`practice_import_pages` 的外键 **IntegrityError**；SQLite 则留孤儿记录。
`Question.group_id` 是裸 INTEGER，删文档不会级联，也会留孤儿。

在 `backend/app/routers/pdf.py` 的 `delete_document` 里，**删文档之前**加
（⚠️ 该函数参数名是 `document_id`，不是 `doc_id` —— 用 `rg -n "def delete_document" app/routers/pdf.py` 确认）：

```python
    # 练习册导入产物无外键级联，必须显式清理
    from ..models import PracticeImportPage, PracticeQuestionGroup, Question

    gids = [g.id for g in db.query(PracticeQuestionGroup)
            .filter_by(source_document_id=document_id).all()]
    if gids:
        db.query(Question).filter(Question.group_id.in_(gids)).delete(
            synchronize_session=False)
        db.query(PracticeQuestionGroup).filter(
            PracticeQuestionGroup.id.in_(gids)).delete(synchronize_session=False)
    db.query(PracticeImportPage).filter_by(document_id=document_id).delete(
        synchronize_session=False)
    db.query(Question).filter(Question.source_document_id == document_id).delete(
        synchronize_session=False)
    db.flush()
```

> 顺序：**先删小题 → 再删题组 → 再删页记录 → 最后删文档**。
> 只删该文档自己的题（`source_document_id == doc_id`），不碰其他卷。

补一条测试：

```python
# backend/tests/test_practice_groups.py 末尾追加
def test_delete_document_cleans_practice_rows(setup_db, db):
    """删练习册文档时，题组/页记录/小题都要清掉（无外键级联）。"""
    from app.models import (
        PdfDocument, PracticeImportPage, PracticeQuestionGroup, Question,
        QuestionBank,
    )
    from app.routers.pdf import delete_document  # 或走 TestClient
    from conftest import make_account

    parent = make_account(db, "del_p", role="parent")
    doc = PdfDocument(filename="g.pdf", subject="数学",
                      storage_path="D:/g.pdf", content_kind="practice")
    db.add(doc)
    db.flush()
    bank = QuestionBank(user_id=parent.id, title="册", subject="数学", grade=5,
                        source="practice_pdf")
    db.add(bank)
    db.flush()
    g = PracticeQuestionGroup(bank_id=bank.id, user_id=parent.id, stem="x",
                              work_mode="oral", page_start=1, page_end=1,
                              source_document_id=doc.id)
    db.add(g)
    db.flush()
    db.add(Question(bank_id=bank.id, user_id=parent.id, qtype="oral",
                    qtype_category="subjective", question="1+1", answer="2",
                    group_id=g.id, source_document_id=doc.id))
    db.add(PracticeImportPage(document_id=doc.id, page_no=1))
    db.commit()
    doc_id = doc.id

    delete_document(document_id=doc_id, db=db)   # 按真实签名调用

    db.expire_all()
    assert db.query(PracticeImportPage).filter_by(document_id=doc_id).count() == 0
    assert db.query(PracticeQuestionGroup).filter_by(
        source_document_id=doc_id).count() == 0
    assert db.query(Question).filter_by(source_document_id=doc_id).count() == 0
```

> 先 `rg -n "def delete_document" app/routers/pdf.py` 确认完整签名
> （可能还需要 `user` 参数），按真实签名写测试或改走
> `TestClient` 调 `DELETE /api/pdf/documents/{id}`。

- [ ] **Step 10: 提交**

```bash
git add backend/app/routers/practice_import.py backend/app/main.py backend/app/services/practice_import.py backend/tests/test_practice_groups.py
git commit -m "feat(practice): 题组浏览/页类型修正/答案页可选（抽 _derive_page_range 统一三处派生）"
```

---

## Task 15: `task_gen` 抽题排除示例、带出题组题干

**Files:**
- Modify: `backend/app/services/task_gen.py`（`_pick_practice_questions`、`_gen_bank_practice_tasks`）
- Test: `backend/tests/test_practice_groups.py`（追加）

**注意**：题库练习的 `Task(...)` 建在 `_gen_bank_practice_tasks`（`task_gen.py:364`），
**不是** `generate_tasks_for_user`（`task_gen.py:476`，它只是调度）。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_practice_groups.py 末尾追加
def test_pick_practice_questions_excludes_examples(setup_db, db):
    """抽题只抽待做小题，示例行不能被抽到。"""
    from datetime import date

    from app.models import Question, QuestionBank
    from app.services.task_gen import _pick_practice_questions
    from conftest import make_account

    child = make_account(db, "tk_c", role="child")
    bank = QuestionBank(user_id=child.id, title="册", subject="数学", grade=5,
                        source="practice_pdf")
    db.add(bank)
    db.flush()
    for i in range(3):
        db.add(Question(bank_id=bank.id, user_id=child.id,
                        qtype="fill_blank", qtype_category="blank",
                        question=f"示例{i}", answer="1", status="published",
                        lesson_no=1, is_example=True, work_mode="pattern"))
    db.add(Question(bank_id=bank.id, user_id=child.id, qtype="fill_blank",
                    qtype_category="blank", question="待做", answer="2",
                    status="published", lesson_no=1, is_example=False,
                    work_mode="pattern"))
    db.commit()

    picked, lesson_no, _title = _pick_practice_questions(
        db, bank, child.id, date(2026, 11, 22), 5)
    assert [q.question for q in picked] == ["待做"]
    assert lesson_no == 1


def test_group_context_includes_examples(setup_db, db):
    """抽中的题要能带出所属题组题干与示例行。"""
    from app.models import Question, QuestionBank
    from app.services.task_gen import _group_context
    from conftest import make_account

    child = make_account(db, "tk_c2", role="child")
    bank = QuestionBank(user_id=child.id, title="册", subject="数学", grade=5,
                        source="practice_pdf")
    db.add(bank)
    db.flush()
    g = PracticeQuestionGroup(bank_id=bank.id, user_id=child.id,
                              stem="不计算，运用规律直接写出得数",
                              instruction="", work_mode="pattern",
                              page_start=1, page_end=1)
    db.add(g)
    db.flush()
    ex = Question(bank_id=bank.id, user_id=child.id, qtype="fill_blank",
                  qtype_category="blank", question="示例1", answer="1.2",
                  status="published", group_id=g.id, seq_in_group=1,
                  is_example=True, work_mode="pattern")
    todo = Question(bank_id=bank.id, user_id=child.id, qtype="fill_blank",
                    qtype_category="blank", question="待做", answer="2",
                    status="published", group_id=g.id, seq_in_group=2,
                    is_example=False, work_mode="pattern")
    db.add_all([ex, todo])
    db.commit()

    ctx = _group_context(db, [todo.id])
    assert len(ctx) == 1
    assert ctx[0]["stem"] == "不计算，运用规律直接写出得数"
    assert ctx[0]["examples"][0]["question"] == "示例1"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k "pick_practice or group_context" -v`
Expected: FAIL — 示例行被抽到 / `_group_context` 不存在

- [ ] **Step 3: 抽题排除示例**

`task_gen.py` 的 `_pick_practice_questions` 里 `base` 查询加过滤：

```python
    base = (
        db.query(Question)
        .filter_by(bank_id=bank.id, status="published")
        .filter(Question.is_example.is_(False))   # 示例行不是待做题
        .order_by(Question.lesson_no, Question.id)
    )
```

- [ ] **Step 4: 新增 `_group_context` 并接到 `_gen_bank_practice_tasks`**

在 `_pick_practice_questions` 之后追加：

```python
def _group_context(db: Session, question_ids: list[int]) -> list[dict]:
    """给抽中的小题带上所属题组题干与示例行，便于孩子理解引导语。"""
    from ..models import PracticeQuestionGroup, Question

    if not question_ids:
        return []
    qs = db.query(Question).filter(Question.id.in_(question_ids)).all()
    gids = {q.group_id for q in qs if q.group_id}
    if not gids:
        return []
    groups = {g.id: g for g in db.query(PracticeQuestionGroup)
              .filter(PracticeQuestionGroup.id.in_(gids)).all()}
    examples: dict[int, list[dict]] = {}
    for ex in (db.query(Question)
               .filter(Question.group_id.in_(gids),
                       Question.is_example.is_(True))
               .order_by(Question.seq_in_group).all()):
        examples.setdefault(ex.group_id, []).append(
            {"question": ex.question, "answer": ex.answer})
    out = []
    for gid in sorted(gids):
        g = groups.get(gid)
        if g is None:
            continue
        out.append({
            "group_id": g.id,
            "stem": g.stem,
            "instruction": g.instruction,
            "work_mode": g.work_mode,
            "examples": examples.get(gid, []),
        })
    return out
```

然后在 `_gen_bank_practice_tasks`（约 `task_gen.py:401-415`）里，`Task(...)` 的
`content=json.dumps({...})` 加一项：

```python
                "groups": _group_context(db, [q.id for q in picked]),
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k "pick_practice or group_context" -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 跑 task_gen 回归**

Run: `cd backend && python -m pytest -q -k "task_gen or daily"`
Expected: 全部 PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/task_gen.py backend/tests/test_practice_groups.py
git commit -m "feat(practice): 每日一练抽题排除示例行并带出题组题干"
```

---

## Task 16: `ocr_import` 对齐 + 删除旧解析函数与失效测试

**Files:**
- Modify: `backend/app/services/ocr_import.py`
- Modify: `backend/app/services/practice_import.py`（删旧函数）
- Modify: `backend/tests/test_practice_import.py`（删失效用例 + 新增替代用例）

- [ ] **Step 1: 补 `$...$` 与 `work_mode` 到 `_STRUCTURE_SYSTEM`**

`backend/app/services/ocr_import.py:47` 的白名单改为：

```python
    "content 只允许这些标记：# ## ** * <u> /ipa/ ____ $...$（加粗、斜体、下划线、"
    "音标、填空、数学式）。数学式用 $...$ 包裹基础 LaTeX（如 $\\frac{3}{4}$），"
    "中文、标点、单位不得放进 $...$ 内部。\n"
```

题目字段说明（同文件 44-46 行）加 `work_mode`：

```python
    '"question":"题干","options":[{"label":"选项","value":0}],"answer_json":{...},'
    '"answer":"标准答案","analysis":"解析","work_mode":"oral|vertical|step|equation|'
    'pattern|compare|unit_compare|fill_vertical|letter_pattern|geometry|app|choice|'
    'judge|other"}。\n'
```

- [ ] **Step 2: 让 draft 带上 `work_mode`**

`ocr_import.py` 的 `_flatten_import` 里，构造 `QuestionDraft` 后补：

```python
        d.work_mode = str(item.get("work_mode") or "").strip()
```

- [ ] **Step 3: 删除 `practice_import.py` 里已无人调用的旧函数**

**必须逐个确认「除本文件外无引用」再删**。用一条 `rg` 把候选符号一起查
（PowerShell 与 Bash 通用，避免 `for` 循环）：

```bash
cd backend && rg -n "parse_lesson_page|parse_answer_page|align_answers|align_by_order|_answers_of|_is_problem_line|_split_row|_section_kind|_parse_pages|_append_image_question|_IMAGE_HINT_RE|_ocr_text" --glob '!app/services/practice_import.py' .
```

**判定规则**：
- 输出为空 → 该符号可删。
- **有命中在 `tests/`** → 先按 Step 4 删/改对应测试，再删函数。
- **有命中在 `app/` 业务代码** → **不能删**，先改调用方。

**已知仍被本文件使用的符号（不要删）**：
- `QTYPE_OF_KIND` —— `build_drafts` 在 `work_mode` 为空时仍用
- `split_blanks` —— `build_drafts` 旧路径（`fill_blank` 按空数切分）仍用
- `_has_variable`、`_strip_answer`、`build_drafts`、`_is_aligned`、`publish_aligned`、
  `merge_cross_page_groups`、`_levenshtein` —— 都还在用

**可删**：`parse_lesson_page`、`parse_answer_page`、`align_answers`、`align_by_order`、
`_answers_of`、`_is_problem_line`、`_split_row`、`_section_kind`、`_parse_pages`、
`_append_image_question`、`_IMAGE_HINT_RE`、`_ocr_text`

- [ ] **Step 4: 删掉失效的旧测试，补上替代用例**

从 `backend/tests/test_practice_import.py` 按**函数名**定位（不要按行号，行号已偏移），
删除这些测试：

| 要删的测试（按函数名） | 原因 |
| --- | --- |
| `test_parse_lesson_page*`（约 5 个） | 函数已删 |
| `test_align_answers*` | 同上 |
| `test_align_by_order*` | 同上 |
| `test_split_blanks*` | 同上 |
| `test_parse_answer_page*` | 同上 |
| `test_split_row*` | 同上 |
| `test_section_kind*` **以及 `test_equation_section_kind`** | 同一个已删函数 `_section_kind`（注意：实际函数名是 `test_equation_section_kind`，`test_section_kind*` 匹配不到它，两者都要删） |
| `test_qtype_category_is_derived_not_hardcoded` | 引用 `QTYPE_OF_KIND`（但 `QTYPE_OF_KIND` 本身**保留**，只是这个测试断言的是旧映射） |
| `test_run_import_job_publishes_aligned_and_records_failures` | patch `pi._ocr_text`，管线已变 |
| `test_run_import_job_all_ok_marks_done` | 同上 |
| `test_import_rejects_without_answer_pages` | 答案页已可选，400 不再返回 |

> **`QTYPE_OF_KIND` 与 `split_blanks` 不要删**（`build_drafts` 旧路径仍在用）。
> 只删 `test_qtype_category_is_derived_not_hardcoded`，保留这两个符号。

**保留并确认仍通过**：`test_practice_tables_exist`、`_persist_drafts` 相关、
`build_drafts` 相关（含 `blanks_of=` 那两个）、`_strip_answer` 相关、
`publish_aligned` 相关、**`test_import_rejects_without_vision_model`**。

**补一条正向测试替代被删的 `test_import_rejects_without_answer_pages`**
（答案页可选是行为变更，必须有正向覆盖）。`_derive_page_range` 由 **Task 14 Step 7** 创建：

```python
# backend/tests/test_practice_import.py 末尾追加
def test_derive_page_range_without_answer_pages():
    """答案页可选：不填时题面页跑到最后一页，而不是 0 页。"""
    from app.routers.practice_import import _derive_page_range

    q_start, q_end = _derive_page_range(
        question_start_page=None, question_end_page=None,
        answer_start_page=None, answer_end_page=None, total_pages=12)
    assert (q_start, q_end) == (1, 12)


def test_derive_page_range_narrows_when_answer_page_given():
    """提供了答案页则收窄到答案页之前，少跑几次视觉调用。"""
    from app.routers.practice_import import _derive_page_range

    q_start, q_end = _derive_page_range(
        question_start_page=None, question_end_page=None,
        answer_start_page=96, answer_end_page=107, total_pages=107)
    assert (q_start, q_end) == (1, 95)


def test_derive_page_range_explicit_question_end_wins():
    from app.routers.practice_import import _derive_page_range

    q_start, q_end = _derive_page_range(
        question_start_page=3, question_end_page=40,
        answer_start_page=96, answer_end_page=107, total_pages=107)
    assert (q_start, q_end) == (3, 40)
```

- [ ] **Step 5: 跑全量后端测试**

Run: `cd backend && python -m pytest -q`
Expected: 全部 PASS，无 ImportError / collection error

若仍有 FAIL，逐个看：多半是某个旧测试还在引用已删符号 → 按 Step 4 继续清理。

- [ ] **Step 6: 实测一次真实导入（强烈建议）**

启动后端（必须 `cd backend` 再起），上传一本练习册 PDF，观察：

```bash
# 另开终端
curl -s "http://127.0.0.1:8010/api/practice-import/jobs/1" -H "Authorization: Bearer <token>"
```

人工核对清单：

- [ ] `practice_question_groups` 组数 ≈ 页面上**大题**数（不是小题数）
- [ ] 找规律那类题：3 个示例 + 1 个待做，示例 `is_example=True`
- [ ] 示例行 `status=published`（前端能读到），但不进每日一练
- [ ] `practice_import_pages` 有每页记录，目录页 `page_type != practice`
- [ ] 待补答案清单里没有示例行
- [ ] 题干里的公式是 `$...$` 包裹的基础 LaTeX，没有 `\\\\div` 这类双反斜杠

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/ocr_import.py backend/app/services/practice_import.py backend/app/routers/practice_import.py backend/tests/
git commit -m "refactor(practice): ocr_import 白名单补 LaTeX/work_mode，删除旧行级解析与失效测试"
```

---

## 完成标准（计划一验收清单）

- [ ] `cd backend && python -m pytest -q` 全绿
- [ ] `work_modes` / `subjects` 注册表有测试守护，新增题型只加一行
- [ ] 迁移**只做 schema**，重启不丢数据（`migrate()` 跑两次幂等）
- [ ] 导入后：题组数 = 大题数；小题挂 `group_id`；示例行 `is_example=True`
- [ ] 示例行**发布**（前端可读）但**不进每日一练、不进待补清单**
- [ ] 发布闸门：`work_mode` 为空的旧题行为不变；`symbol`/`choice` 不再被误挡
- [ ] `numeric_list` 题的 `answer_json.blanks` 非空（`build_drafts` 按 `answer_kind` 写）
- [ ] `_strip_answer` 对任何输入都保持 `$` 成对
- [ ] `POST /api/banks/submit` 对有 `work_mode` 的题走 `grade_practice_item`
- [ ] 答案页不填也能跑满 `total_pages`（`_derive_page_range` 三处共用）
- [ ] 上传语文/英语练习册返回 400（不静默按数学解析）
- [ ] 删练习册文档后无孤儿题组/页记录/小题
- [ ] 目录页/答案页不入库，但留 `PracticeImportPage` 记录可修正

## 明确不在本计划范围

- 前端渲染（`parent-web` 的 KaTeX、Flutter 的 `math_text`）→ 计划二
- 每日一练页面的多空/拍照提交、`PracticeAttempt` 写入 → 计划二（表已建好）
- 语文/英语解析器 → 未来（注册表已留位）
- 表格题还原 → 走裁图（`geometry`），不做文本表格
