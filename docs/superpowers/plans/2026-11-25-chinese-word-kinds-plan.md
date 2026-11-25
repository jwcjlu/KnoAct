# 语文识字 / 写字 / 词语三分 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `WordBank` 增加 `kind`（识字/写字/词语/英语 word），拆课与家长编辑分栏，听写与复习生词按孩子配置过滤；认/写同字分掌握度。

**Architecture:** 单列 `kind` + `(lesson_id, kind, word)` 唯一；提取产出扁平 `{word,extra,kind}`；`_replace_lesson_words` 按 `(norm_word, kind)` 匹配掌握度；`_gen_dictation` / `_gen_review` 共用 `enabled_kinds(user)` 过滤。孩子级键 `dictation_kinds_语文` JSON。听力本版不改。

**Tech Stack:** FastAPI、SQLAlchemy、`schema_sync`、parent-web 原生 JS、现有听写 Flutter/Web。

**Spec:** `docs/superpowers/specs/2026-11-25-chinese-word-kinds-design.md`

---

## File map

| Path | Role |
| --- | --- |
| `backend/app/models.py` | `WordBank.kind` + UniqueConstraint |
| `backend/app/migrate_word_kind.py` | UPDATE kind + 去重 + 建唯一索引 |
| `backend/app/main.py` | 启动调用 migrate |
| `backend/app/services/word_kinds.py` | 常量、校验、`enabled_kinds`、序列化 |
| `backend/app/services/lesson_extract.py` | 三分提取 + `_replace_lesson_words` 按 kind 匹配 |
| `backend/app/routers/pdf.py` | `_run_extract` 写 kind + 走 `_replace_lesson_words`；PUT/GET words 带 kind |
| `backend/app/services/task_gen.py` | dictation/review 过滤 + content 带 kind |
| `backend/app/routers/learning.py` | preferences 读写 `dictation_kinds_语文` |
| `backend/app/services/child_config.py` | getter 默认三开 |
| `parent-web/app.js` | 课编辑三栏 + 学习配置三勾选 |
| `backend/tests/test_word_kinds.py` | 新测 |

---

### Task 1: 模型 `kind` + 常量模块

**Files:**
- Modify: `backend/app/models.py`（`WordBank`）
- Create: `backend/app/services/word_kinds.py`
- Create: `backend/tests/test_word_kinds.py`

- [ ] **Step 1: 失败测试**

```python
from app.models import WordBank
from app.services import word_kinds as wk

def test_word_bank_has_kind_column():
    cols = {c.name for c in WordBank.__table__.columns}
    assert "kind" in cols

def test_valid_kinds():
    assert wk.KIND_RECOGNIZE == "recognize"
    assert set(wk.CN_KINDS) == {"recognize", "write", "phrase"}
    assert wk.normalize_kind("write") == "write"
    try:
        wk.normalize_kind("unknown")
        assert False
    except ValueError:
        pass
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend; python -m pytest tests/test_word_kinds.py -v
```

- [ ] **Step 3: 实现**

`WordBank` 在 `extra` 后：

```python
kind: Mapped[str] = mapped_column(String(16), default="phrase")
```

`__table_args__` 增加（若已有则合并）：

```python
UniqueConstraint("lesson_id", "kind", "word", name="uq_word_banks_lesson_kind_word"),
```

注意：迁移完成前本地测试库可能因重复无法建约束——Task 2 先跑去重；若 create_all 在空库上无问题。测试库用 conftest 空库则 OK。

`word_kinds.py`：

```python
KIND_RECOGNIZE, KIND_WRITE, KIND_PHRASE, KIND_WORD = "recognize", "write", "phrase", "word"
CN_KINDS = (KIND_RECOGNIZE, KIND_WRITE, KIND_PHRASE)
ALL_KINDS = CN_KINDS + (KIND_WORD,)
DEFAULT_CN_ENABLED = list(CN_KINDS)

def normalize_kind(k: str) -> str:
    k = (k or "").strip()
    if k not in ALL_KINDS:
        raise ValueError(f"invalid kind: {k}")
    return k

def default_kind_for_subject(subject: str) -> str:
    return KIND_PHRASE if (subject or "") == "语文" else KIND_WORD
```

- [ ] **Step 4: 测通过 + commit**

```bash
git add backend/app/models.py backend/app/services/word_kinds.py backend/tests/test_word_kinds.py
git commit -m "feat(words): WordBank.kind 与合法枚举"
```

---

### Task 2: 迁移去重 + 唯一索引

**Files:**
- Create: `backend/app/migrate_word_kind.py`
- Modify: `backend/app/main.py`（startup 调用，对齐 `migrate_reading_passage`）
- Test: `backend/tests/test_word_kinds.py`（追加）

- [ ] **Step 1: 测试迁移语义（可用 SessionLocal + 手工插重复行）**

```python
def test_migrate_dedupes_same_lesson_kind_word(db_session):
    # 插两行同 lesson/kind/word，挂 mastery 在较大 id
    # 跑 migrate(db_session)
    # 断言只剩一行；mastery.word_bank_id 指向保留的最小 id
    ...
```

- [ ] **Step 2: 实现 `def migrate(db: Session) -> None`**

逻辑：

1. 确保列存在（依赖 schema_sync 已跑，或本文件 ALTER）。  
2. `UPDATE word_banks SET kind='phrase' WHERE subject='语文' AND (kind IS NULL OR kind='')`  
3. 非语文：`kind='word'`  
4. 找重复 `(lesson_id, kind, word)`：保留 `min(id)`，把 mastery/mistake 的 `word_bank_id` 从重复 id 改到 keep，再 DELETE 重复。  
5. 创建唯一索引（若不存在）：SQLite `CREATE UNIQUE INDEX IF NOT EXISTS ...`；MySQL 同等。

- [ ] **Step 3: main.py** 在 schema_sync 之后，与其它 migrate 同样：

```python
try:
    from .migrate_word_kind import migrate as _migrate_word_kind
    _migrate_word_kind(db)
except Exception:
    db.rollback()
    logging.exception("migrate_word_kind failed")
```

- [ ] **Step 4: commit**

```bash
git commit -m "feat(words): 迁移 kind 默认值并去重建唯一索引"
```

---

### Task 3: 三分提取 + `_replace_lesson_words` + `_run_extract`

**Files:**
- Modify: `backend/app/services/lesson_extract.py`
- Modify: `backend/app/routers/pdf.py`（`_run_extract`）
- Test: `backend/tests/test_word_kinds.py` 或 `test_pdf_router.py`

- [ ] **Step 1: 失败测试**

同课旧有 recognize「箩」与 write「箩」；新 items 仍两行不同 kind → 两行 mastery 各自跟到对应新 id，**不交叉**。

- [ ] **Step 2: 改 `_replace_lesson_words`**

- `items` 每项必须含 `kind`（调用方保证）。  
- `old_by_key[(norm_word, kind)] = list`  
- 新建 `WordBank(..., kind=item["kind"])`  
- 匹配 `bucket.pop(0)` 按 `(norm, kind)`  

- [ ] **Step 3: 更新语文提取 prompt / 解析**

- AI 输出三段：`识字：` / `写字：` / `词语：`（或「识字表」等），解析为 flat list with kind。  
- Fallback 正则按标题切。  
- 英语路径给 `kind=word`。  
- `extract_lesson_content` 返回的 `words` 每项含 `kind`。

- [ ] **Step 4: 改 `_run_extract`（关键）**

现状：`purge_lesson_content` 后裸 `WordBank(...)` 插入，**丢 kind、丢掌握度跟词**。

改为：

1. `content = extract_lesson_content(...)`（words 已带 kind）。  
2. **词表**：`_replace_lesson_words(db, lesson, content["words"])`（不要对词表再走会 detach 全部词的 purge，或 purge 时排除 words 后由 replace 处理——实现时选一种，结果须保留 `(word,kind)` 掌握度）。  
3. 知识点 / 课文 / 阅读题：可继续先清再写（与现网一致）。  
4. 英语条目一律 `kind=word`。

- [ ] **Step 4b: 英语书末词表路径**

`apply_word_list` / `_ensure_word_list_lesson` / `_sync_word_list`（`_run_extract` 尾段）传入 `_replace_lesson_words` 的 items **必须补** `kind: "word"`，否则 replace 断言/缺字段会炸。

- [ ] **Step 5: commit**

```bash
git commit -m "feat(extract): 语文三分提取；_run_extract 按 word+kind 跟掌握度"
```

---

### Task 4: `PUT/GET` 课内容带 kind

**Files:**
- Modify: `backend/app/routers/pdf.py`（`LessonContentIn` Word 模型、`update_lesson_content`、list 序列化）
- Test: `backend/tests/test_pdf_router.py` 追加

规则（spec）：

- 语文：每词必填合法 `kind`，否则返回错误（与现网课内容 API 一致：可用 `{"error": ...}` 体；家长端认 `r.error`）。  
- 英语：缺省 `word`。  
- 有 `id` 且 kind **未变**：原地改 word/extra。  
- 有 `id` 但 kind **变了**：当作删旧 + 新建（不迁 mastery）——实现：不把旧 id 加入 kept，新插入无 id 行。前端跨栏应清 id。  
- GET 课 words 返回 `kind`。

- [ ] **Step 1–4: TDD + commit**

```bash
git commit -m "feat(pdf): 课生词 API 读写 kind（语文必填）"
```

---

### Task 5: 听写 / 复习过滤 + content.kind

**Files:**
- Modify: `backend/app/services/child_config.py`（`get_dictation_kinds_cn`）
- Modify: `backend/app/services/task_gen.py`
- Modify: `backend/app/routers/learning.py`（**含扩展 `PreferencesReq`**）
- Test: `backend/tests/test_word_kinds.py` + `test_dictation_preferences.py` / `test_task_gen.py`

```python
def get_dictation_kinds_cn(db, child_id) -> list[str]:
    # ChildConfig key dictation_kinds_语文，JSON list；坏数据回落 DEFAULT_CN_ENABLED
```

`PreferencesReq` 增加：`dictation_kinds_语文: list[str] | None = None`。  
PUT：校验每项 ∈ CN_KINDS，`json.dumps` 写入 ChildConfig。  
GET：`json.loads` + 回落默认三开。

`_gen_dictation`：在查到 `words` 后：

```python
if subject == "语文":
    allowed = set(get_dictation_kinds_cn(db, user_id))
    words = [w for w in words if w.kind in allowed]
else:
    words = [w for w in words if (w.kind or "word") == "word"]
if not words:
    return None
```

content 带 `kind`。`_gen_review`：同样过滤；过滤后空则 `return None`。

- [ ] **测试：** 只开 write 时抽到的词全是 write；全关 → dictation 不生成。  
- [ ] **commit**

```bash
git commit -m "feat(dictation): 按 dictation_kinds 过滤听写与复习生词"
```

---

### Task 6: parent-web 三栏编辑 + 学习配置勾选

**Files:**
- Modify: `parent-web/app.js`（`startLessonEdit` / `saveLessonEdit` / `addLessonWord` / 渲染 / 学习配置）

- [ ] **`startLessonEdit`**：map 保留 `kind`（缺省按学科：语文 `phrase`，英语 `word`）。  
- [ ] **三栏 UI**：按 kind 分栏；跨栏移动时 **清空 id**。  
- [ ] **`addLessonWord(kind)`**：新词默认该栏 kind。  
- [ ] **`saveLessonEdit`**：body.words 每项提交 `kind`（及 id/word/extra）。  
- [ ] 展示芯片按 kind 分组。  
- [ ] **学习配置 `dictation_kinds_语文`（勿走现有字符串套路）**：  
  - `loadLearningPreferences`：对该键 **不要** `String(r[k])`；保留数组（或 `JSON.parse`），坏数据回落 `['recognize','write','phrase']`；勾选框按数组 includes 回显。  
  - `saveLearningConfig`：由三 checkbox 组装 **JSON 数组**（如 `['write','phrase']`），经 `PUT /api/learning/preferences` 的 `dictation_kinds_语文` 字段提交；**禁止**写成 `'true'/'false'` 字符串。  
  - 将该键纳入与其它听写参数相同的 `childKeys` / preferences 写入路径。  

```bash
git commit -m "feat(parent-web): 生词三栏编辑与听写类型开关"
```

---

### Task 7: 回归

```bash
cd backend; python -m pytest tests/test_word_kinds.py tests/test_dictation_preferences.py tests/test_pdf_router.py tests/test_task_gen.py -v
```

若个别文件不存在，用：`pytest -k "word_kind or dictation or pdf_router or task_gen" -v`。

修正因 content 多 `kind` 字段导致的断言。Flutter 听写若强校验 JSON 字段则放宽。

```bash
git commit -m "test: 对齐 kind 后的听写/课内容断言"
```

---

## 风险

1. **唯一约束 vs 未去重库**：必须 Task 2 先于生产加约束。  
2. **旧语文全在 phrase**：验收说明「重拆或手调后三类才齐」。  
3. **`_gen_listening` 本版不滤 kind**（spec 非目标）。  
4. PowerShell 用 `;` 不用 `&&`。  
