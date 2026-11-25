# 语文册末识字/写字/词语表回填 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在语文拆课提取末自动检测册末（或单元末）识字表/写字表/词语表，按课序回填各课对应 `kind`；知识点抽取不变。

**Architecture:** 平行于英语 `_detect_word_list` → `apply_word_list`。新增 `_detect_chinese_word_tables`（多段 `{kind,start,end}`）+ `parse_chinese_table_text`（课号桶）+ `apply_chinese_word_tables`；用 `_replace_lesson_words_kind` **只替换单一 kind**，避免误删另两类。挂在 `_run_extract` 语文分支末。

**Tech Stack:** FastAPI、SQLAlchemy、现有 OCR/`_page_text`、pytest。

**Spec:** `docs/superpowers/specs/2026-11-25-chinese-back-matter-tables-design.md`

**Prerequisite:** 分支基于已合并 `#8` 的 `origin/master`（含 `WordBank.kind`、`word_kinds.py`、按 `(word,kind)` 的 `_replace_lesson_words`）。本地若落后先 `git fetch && git rebase origin/master`（保留本仓库已提交的 design spec）。

---

## File map

| Path | Role |
| --- | --- |
| `backend/app/services/pdf_split.py` | 语文册末表检测、裁末课、`is_cn_table_title` |
| `backend/app/services/lesson_extract.py` | 解析课号桶、`_replace_lesson_words_kind`、`apply_chinese_word_tables` |
| `backend/app/routers/pdf.py` | `_run_extract` 语文末调用回填 |
| `backend/app/services/task_gen.py` | 听写排除汇总课标题 |
| `backend/tests/test_chinese_back_matter.py` | 解析/回填/不碰其它 kind 与知识点 |
| `backend/tests/test_pdf_split.py` | 检测与裁页（若已有 word_list 测则并列） |

---

### Task 1: 标题判断 + 页检测（pdf_split）

**Files:**
- Modify: `backend/app/services/pdf_split.py`
- Create/Modify: `backend/tests/test_chinese_back_matter.py`（或扩 `test_pdf_split.py`）

- [ ] **Step 1: 失败测试**

```python
from app.services.pdf_split import (
    is_cn_table_title,
    _page_is_cn_word_table,
    _cn_table_kind_from_text,
)

def test_is_cn_table_title():
    assert is_cn_table_title("词语表")
    assert is_cn_table_title("识字表")
    assert is_cn_table_title("写字表")
    assert not is_cn_table_title("桂花雨")

def test_page_kind_from_heading():
    assert _cn_table_kind_from_text("词语表\n1\n桂花 故乡") == "phrase"
    assert _cn_table_kind_from_text("写字表\n兰 桂") == "write"
    assert _cn_table_kind_from_text("识字表（会认的字）\n杭") == "recognize"
    assert _page_is_cn_word_table("词语表\n1 桂花 故乡")
    assert not _page_is_cn_word_table("第 1 课 桂花雨\n课文正文……")
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && python -m pytest tests/test_chinese_back_matter.py::test_is_cn_table_title tests/test_chinese_back_matter.py::test_page_kind_from_heading -v
```

Expected: FAIL import / not defined

- [ ] **Step 3: 实现检测辅助**

在 `pdf_split.py`（靠近 `is_word_list_title`）增加：

```python
_CN_TABLE_TITLES = ("识字表", "写字表", "词语表")
_CN_TABLE_KIND = {"识字表": "recognize", "写字表": "write", "词语表": "phrase"}

def is_cn_table_title(title: str) -> bool:
    t = (title or "").strip()
    return t in _CN_TABLE_TITLES or t in {"识字表汇总", "写字表汇总", "词语表汇总"}

def _cn_table_kind_from_text(text: str) -> str | None:
    head = "\n".join((text or "").strip().splitlines()[:5])
    for name, kind in _CN_TABLE_KIND.items():
        if name in head:
            return kind
    return None

def _page_is_cn_word_table(text: str) -> bool:
    return _cn_table_kind_from_text(text) is not None
```

续页：已在某 kind 表内时，若本页无新表标题但含课号行 `^\s*\d{1,2}\s*$` 或大量汉字词，视为续页（`_page_continues_cn_table`）。

`_detect_chinese_word_tables(pdf_path, subject, texts, total_pages, db) -> list[dict]`：

- `subject != "语文"` → `[]`
- 全书扫描（不仅末 16 页，因单元末也可能出现；可先扫全文文本页，扫描版对候选页 OCR）
- 命中后向后扩 `end`，直到非续页或碰上另一表标题（另一表开新段）
- 返回 `[{ "kind", "title", "start_page", "end_page" }, ...]`（1-based 页码）

在 `detect_lessons_from_pdf` 语文路径：若检测到表，将落入表页的末课 `end_page` 裁到 `min(表 start)-1`（仿英语 Word list）。可选：为每种表各追加一课 `title=识字表/写字表/词语表`（`extract_status=done`），便于家长查看；**听写必须排除**（Task 5）。

- [ ] **Step 4: 跑测通过 + commit**

```bash
cd backend && python -m pytest tests/test_chinese_back_matter.py::test_is_cn_table_title tests/test_chinese_back_matter.py::test_page_kind_from_heading -v
git add backend/app/services/pdf_split.py backend/tests/test_chinese_back_matter.py
git commit -m "feat(pdf_split): 语文册末识字/写字/词语表页检测"
```

---

### Task 2: 解析课号桶

**Files:**
- Modify: `backend/app/services/lesson_extract.py`
- Modify: `backend/tests/test_chinese_back_matter.py`

- [ ] **Step 1: 失败测试（用用户截图结构）**

```python
from app.services.lesson_extract import parse_chinese_table_text

_PHRASE_SAMPLE = """
词语表
1
桂花 故乡 时节 欣赏 糕饼 成熟 完整
茶叶
2
播种 收获 食品 吩咐 价钱 可贵 果实
体面
4
地道 平原 扫荡 封锁 武装 粉碎 简直
"""

def test_parse_chinese_table_groups_by_lesson_no():
    by = parse_chinese_table_text(_PHRASE_SAMPLE, kind="phrase")
    assert [w["word"] for w in by[1]][:3] == ["桂花", "故乡", "时节"]
    assert any(w["word"] == "茶叶" for w in by[1])
    assert any(w["word"] == "体面" for w in by[2])
    assert 3 not in by
    assert by[4][0]["word"] == "地道"
    assert all(w.get("kind") == "phrase" for rows in by.values() for w in rows)

def test_parse_write_table_single_chars():
    raw = "写字表\n1\n兰 桂 曼\n2\n亩 亭 吩\n"
    by = parse_chinese_table_text(raw, kind="write")
    assert [w["word"] for w in by[1]] == ["兰", "桂", "曼"]
    assert [w["word"] for w in by[2]] == ["亩", "亭", "吩"]
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && python -m pytest tests/test_chinese_back_matter.py::test_parse_chinese_table_groups_by_lesson_no -v
```

- [ ] **Step 3: 实现 `parse_chinese_table_text`**

```python
_LESSON_NO_LINE = re.compile(r"^\s*(\d{1,2})\s*$")
_HAN_TOKEN = re.compile(r"[\u4e00-\u9fff]+")

def parse_chinese_table_text(raw: str, kind: str) -> dict[int, list[dict]]:
    """册末表文本 → {lesson_no: [{word, extra, kind}, ...]}。同课同词去重保序。"""
    kind = normalize_kind(kind)
    by: dict[int, list[dict]] = {}
    seen: dict[int, set[str]] = {}
    cur: int | None = None
    for line in (raw or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s in _CN_TABLE_TITLES or s.startswith(tuple(_CN_TABLE_TITLES)):
            continue
        m = _LESSON_NO_LINE.match(s)
        if m:
            cur = int(m.group(1))
            by.setdefault(cur, [])
            seen.setdefault(cur, set())
            continue
        if cur is None:
            # 行首课号 + 词： "1 桂花 故乡"
            m2 = re.match(r"^(\d{1,2})\s+(.+)$", s)
            if m2:
                cur = int(m2.group(1))
                by.setdefault(cur, [])
                seen.setdefault(cur, set())
                s = m2.group(2)
            else:
                continue
        for tok in _HAN_TOKEN.findall(s):
            if kind in ("recognize", "write") and len(tok) > 1:
                # 写字/识字表：逐字；若整段是多字无空格也拆成单字
                chars = list(tok) if kind != "phrase" else [tok]
            else:
                chars = [tok]
            if kind == "phrase" and len(tok) < 2:
                continue  # 词语表跳过单字噪声
            for w in (list(tok) if kind in ("recognize", "write") and len(tok) > 1 else [tok]):
                if kind == "phrase" and len(w) < 2:
                    continue
                if w in seen[cur]:
                    continue
                seen[cur].add(w)
                by[cur].append({"word": w, "extra": "", "kind": kind})
    return {n: rows for n, rows in by.items() if rows}
```

注意：上面循环里写字拆字逻辑写了两遍草稿——实现时收成一处：  
- `phrase`：每个 `findall` 出的连续汉字串整词入库（len≥2）  
- `recognize`/`write`：每个串若 len==1 入库；若 len>1 且无间隔，**拆成单字**入库（教材常「兰桂曼」连排）

另增 `extract_chinese_table_units(pdf_path, db, kind, start_page, end_page) -> dict[int,list]`：对该页区间 `_lesson_texts` / OCR 后 `parse_chinese_table_text`。

- [ ] **Step 4: 跑测通过 + commit**

```bash
cd backend && python -m pytest tests/test_chinese_back_matter.py -k parse_chinese -v
git add backend/app/services/lesson_extract.py backend/tests/test_chinese_back_matter.py
git commit -m "feat(extract): 解析语文册末表课号分桶"
```

---

### Task 3: 按 kind 子集替换 + apply

**Files:**
- Modify: `backend/app/services/lesson_extract.py`
- Modify: `backend/tests/test_chinese_back_matter.py`

- [ ] **Step 1: 失败测试**

```python
from app.models import KnowledgePoint, WordBank
from app.services.lesson_extract import apply_chinese_word_tables
from app.services.word_kinds import KIND_PHRASE, KIND_RECOGNIZE, KIND_WRITE
from conftest import make_document, make_lesson

def test_replace_kind_only_leaves_other_kinds_and_points(db, monkeypatch):
    import app.services.lesson_extract as le
    doc = make_document(db, subject="语文", filename="语文.pdf", storage_path="x.pdf")
    l1 = make_lesson(db, subject="语文", title="桂花雨", document=doc, start_page=7, end_page=9)
    l2 = make_lesson(db, subject="语文", title="落花生", document=doc, start_page=10, end_page=11)
    db.add_all([
        WordBank(lesson_id=l1.id, subject="语文", word="杭", extra="", kind=KIND_RECOGNIZE),
        WordBank(lesson_id=l1.id, subject="语文", word="旧词", extra="", kind=KIND_PHRASE),
        KnowledgePoint(lesson_id=l1.id, subject="语文", category="本课", content="借物抒情"),
    ])
    db.commit()
    monkeypatch.setattr(le, "_detect_chinese_word_tables", lambda *a, **k: [
        {"kind": KIND_PHRASE, "title": "词语表", "start_page": 90, "end_page": 91},
    ])
    monkeypatch.setattr(le, "extract_chinese_table_units", lambda pdf, db, kind, sp, ep: {
        1: [{"word": "桂花", "extra": "", "kind": KIND_PHRASE},
            {"word": "故乡", "extra": "", "kind": KIND_PHRASE}],
        2: [{"word": "播种", "extra": "", "kind": KIND_PHRASE}],
    } if kind == KIND_PHRASE else {})
    # apply 需要能找到 detect：可直接测 _replace + apply 内部；此处调 apply_chinese_word_tables
    r = apply_chinese_word_tables(db, doc.id, "x.pdf")
    assert r["words"] >= 3
    phrases = [w.word for w in db.query(WordBank).filter_by(lesson_id=l1.id, kind=KIND_PHRASE)]
    assert set(phrases) == {"桂花", "故乡"}
    assert "旧词" not in phrases
    assert db.query(WordBank).filter_by(lesson_id=l1.id, kind=KIND_RECOGNIZE, word="杭").count() == 1
    assert db.query(KnowledgePoint).filter_by(lesson_id=l1.id).count() == 1

def test_missing_lesson_no_does_not_clear_kind(db, monkeypatch):
    import app.services.lesson_extract as le
    doc = make_document(db, subject="语文", filename="语文.pdf", storage_path="x.pdf")
    l3 = make_lesson(db, subject="语文", title="第三课", document=doc, start_page=12, end_page=14)
    # 课序：仅一课 → lesson_no=1；表只有 4 → 不应清空
    db.add(WordBank(lesson_id=l3.id, subject="语文", word="留", extra="", kind=KIND_PHRASE))
    db.commit()
    monkeypatch.setattr(le, "_detect_chinese_word_tables", lambda *a, **k: [
        {"kind": KIND_PHRASE, "title": "词语表", "start_page": 90, "end_page": 90},
    ])
    monkeypatch.setattr(le, "extract_chinese_table_units", lambda *a, **k: {
        4: [{"word": "地道", "extra": "", "kind": KIND_PHRASE}],
    })
    apply_chinese_word_tables(db, doc.id, "x.pdf")
    assert db.query(WordBank).filter_by(lesson_id=l3.id, word="留").count() == 1
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && python -m pytest tests/test_chinese_back_matter.py::test_replace_kind_only_leaves_other_kinds_and_points -v
```

- [ ] **Step 3: 实现**

```python
def _replace_lesson_words_kind(db: Session, lesson, kind: str, items: list[dict]) -> None:
    """只替换该课该 kind；其它 kind 不动。items 为空则 no-op（由调用方保证有表才调用）。"""
    from ..models import WordBank
    from .cleanup import detach_words
    kind = normalize_kind(kind)
    subject = lesson.subject or "语文"
    old = db.query(WordBank).filter_by(lesson_id=lesson.id, kind=kind).all()
    old_by_key: dict[str, list] = {}
    for w in old:
        old_by_key.setdefault(_norm_word(w.word), []).append(w)
    used: set[int] = set()
    for item in items:
        key = _norm_word(item["word"])
        bucket = old_by_key.get(key) or []
        if bucket:
            row = bucket.pop(0)
            row.word = item["word"]
            row.extra = item.get("extra") or ""
            row.kind = kind
            used.add(row.id)
        else:
            db.add(WordBank(
                lesson_id=lesson.id, subject=subject,
                word=item["word"], extra=item.get("extra") or "", kind=kind,
            ))
    drop = [w.id for w in old if w.id not in used]
    detach_words(db, drop)
    if drop:
        db.query(WordBank).filter(WordBank.id.in_(drop)).delete(synchronize_session=False)


def apply_chinese_word_tables(db: Session, document_id: int, pdf_path: str) -> dict:
    from ..models import Lesson
    texts = _page_text(pdf_path) or []
    tables = _detect_chinese_word_tables(pdf_path, "语文", texts, len(texts), db)
    if not tables:
        return {"tables": 0, "lessons": 0, "words": 0}
    lessons = (
        db.query(Lesson)
        .filter_by(document_id=document_id, subject="语文")
        .order_by(Lesson.start_page, Lesson.id)
        .all()
    )
    lessons = [l for l in lessons if not is_cn_table_title(l.title) and not is_word_list_title(l.title)]
    updated = words_n = 0
    for tbl in tables:
        by = extract_chinese_table_units(
            pdf_path, db, tbl["kind"], tbl["start_page"], tbl["end_page"],
        )
        for idx, lesson in enumerate(lessons, start=1):
            items = by.get(idx)
            if not items:
                continue
            _replace_lesson_words_kind(db, lesson, tbl["kind"], items)
            updated += 1
            words_n += len(items)
    db.commit()
    return {"tables": len(tables), "lessons": updated, "words": words_n}
```

从 `pdf_split` 导入 `_detect_chinese_word_tables`、`is_cn_table_title`。

- [ ] **Step 4: 跑测通过 + commit**

```bash
cd backend && python -m pytest tests/test_chinese_back_matter.py -v
git add backend/app/services/lesson_extract.py backend/tests/test_chinese_back_matter.py
git commit -m "feat(extract): 册末表按 kind 回填各课"
```

---

### Task 4: 挂到 `_run_extract`

**Files:**
- Modify: `backend/app/routers/pdf.py`
- Modify: `backend/tests/test_pdf_router.py`（若有 extract 测；否则 `test_chinese_back_matter.py` 里 mock 一层）

- [ ] **Step 1: 在 `_run_extract` 英语 sync 旁增加语文**

```python
from ..services.lesson_extract import apply_chinese_word_tables, apply_word_list, extract_lesson_content

# 循环内写 WordBank 时须带 kind（#8 已做）；本任务只加末段：

        if any(t.get("subject") == "英语" for t in tasks):
            prog["current"] = "Word list"
            _sync_word_list(document_id, storage_path, prog)
        if any(t.get("subject") == "语文" for t in tasks):
            prog["current"] = "册末字词表"
            _sync_chinese_word_tables(document_id, storage_path, prog)
```

```python
def _sync_chinese_word_tables(document_id: int, storage_path: str, prog: dict) -> None:
    db = SessionLocal()
    try:
        apply_chinese_word_tables(db, document_id, storage_path)
    except Exception as e:
        prog["error"] = str(e)[:300]
    finally:
        db.close()
```

各课已 `extract_status==done` 且再点提取时：英语有 `_run_word_list_sync`；语文可对称——若全部 done 仍 POST extract，走 `_sync_chinese_word_tables`（读现有 `extract` 分支，英语怎么走语文就怎么走）。

- [ ] **Step 2: 测 + commit**

```bash
cd backend && python -m pytest tests/test_chinese_back_matter.py tests/test_word_list.py tests/test_pdf_router.py -v --tb=short
git add backend/app/routers/pdf.py backend/tests
git commit -m "feat(pdf): 语文提取末自动同步册末字词表"
```

---

### Task 5: 听写排除汇总课

**Files:**
- Modify: `backend/app/services/task_gen.py`（`_content_lesson_ids` 或过滤 title 处）
- 已有英语：`is_word_list_title` — 并列 `is_cn_table_title`

- [ ] **Step 1: 找到排除点并改**

```python
from .pdf_split import is_cn_table_title, is_word_list_title

# 选课时：
if is_word_list_title(lesson.title) or is_cn_table_title(lesson.title):
    continue
```

- [ ] **Step 2: 单测或扩现有 dictation 测：汇总课词不进听写池**

- [ ] **Step 3: commit**

```bash
git add backend/app/services/task_gen.py backend/tests
git commit -m "fix(dictation): 排除语文册末汇总课"
```

---

### Task 6: 回归

- [ ] **Step 1: 全量相关测**

```bash
cd backend && python -m pytest tests/test_chinese_back_matter.py tests/test_word_list.py tests/test_word_kinds.py tests/test_pdf_split.py tests/test_pdf_router.py -v --tb=short
```

Expected: 全绿

- [ ] **Step 2: 手工（有样张 PDF 时）**  
  上传人教语文 → 提取 → 桂花雨 `phrase` 含「桂花/故乡…」；知识点仍在；无词语表课号的课该 kind 不被清空。

- [ ] **Step 3: 收尾 commit（若有文档微调）**

```bash
git status
# 无则跳过
```

---

## 执行方式

实现时用 **subagent-driven-development**（推荐）按 Task 1→6 推进；每 Task 内严格 TDD。  
工作树：从含 `#8` 的 `origin/master` 拉 `feature/chinese-back-matter-tables`。
