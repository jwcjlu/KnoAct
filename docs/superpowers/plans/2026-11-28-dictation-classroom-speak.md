# 语文听写课堂式报读 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 语文听写在任务生成时补全组词/短释义，固化 `speak_text` 供 TTS；单字宽判接受组词；家长可见「报读待补」。

**Architecture:** 新增纯函数模块拼装报读与查缺；`_gen_dictation` 选出词后批量补线索并写入 `Task.content`；可复用线索存 `WordBank.dictation_cue`（JSON，不碰 `extra`）；手写批改请求带 `accept`，服务端按命中重判；Flutter 播 `speak_text`；任务列表附带 `speak_incomplete_count`。

**Tech Stack:** FastAPI + SQLAlchemy + pytest；Flutter（Riverpod）；parent-web 原生 JS。

**Spec:** `docs/superpowers/specs/2026-11-28-dictation-classroom-speak-design.md`

**测试命令：** 从 `backend/` 跑 `python -m pytest …`（用 Bash 的 python；详见 AGENTS.md）。Flutter：`E:\dev\flutter\bin\flutter test …`。

---

## 文件结构

| 文件 | 职责 |
|------|------|
| Create: `backend/app/services/dictation_speak.py` | 报法分类、从 extra 种子化、拼 `speak_text`/`accept`、查缺、读/写 cue |
| Create: `backend/app/services/dictation_cue_fill.py` | 批量 AI 补组词/短释义（可 mock） |
| Modify: `backend/app/models.py` | `WordBank.dictation_cue` |
| Modify: `backend/app/services/task_gen.py` | `_gen_dictation` 语文路径 enrichment |
| Modify: `backend/app/services/handwriting.py` | prompt 含 accept；服务端按 accept 重判 |
| Modify: `backend/app/routers/tasks.py` | `_to_dict` 增加 `speak_incomplete_count` |
| Modify: `student-app/lib/features/dictation/data/dictation_repository.dart` | `DictWord` 解析 `speak_text`/`accept` |
| Modify: `student-app/lib/features/dictation/…` | 播报与批改载荷 |
| Modify: `parent-web/app.js` | 「报读待补 N」展示 |
| Test: `backend/tests/test_dictation_speak.py` | 纯函数 + 生成 + 批改 |
| Test: `backend/tests/test_handwriting.py` | accept 重判 |
| Test: `student-app/test/features/dictation/…` | 解析 / speak 字段 |

---

### Task 1: `dictation_speak` 纯函数（分类 / 种子 / 拼装）

**Files:**
- Create: `backend/app/services/dictation_speak.py`
- Test: `backend/tests/test_dictation_speak.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_dictation_speak.py`：

```python
from app.services.dictation_speak import (
    classify_speak_mode,
    seed_compound_from_extra,
    gloss_from_extra,
    build_speak_payload,
    parse_cue,
    dump_cue,
)


def test_classify_kind_write_is_char():
    assert classify_speak_mode(kind="write", word="事") == "char"


def test_classify_kind_phrase_is_word():
    assert classify_speak_mode(kind="phrase", word="认真") == "word"


def test_classify_fallback_by_len():
    assert classify_speak_mode(kind="", word="事") == "char"
    assert classify_speak_mode(kind="weird", word="认真") == "word"


def test_seed_compound_from_extra():
    assert seed_compound_from_extra("事", "shì 事情") == "事情"
    assert seed_compound_from_extra("事", "shì 故事很长的解释") is None


def test_gloss_from_extra_short():
    assert gloss_from_extra("认真", "rènzhēn 做事仔细") == "做事仔细"
    assert gloss_from_extra("认真", "rènzhēn " + ("很长" * 10)) is None


def test_build_speak_char_complete():
    p = build_speak_payload(word="事", kind="write", compound="事情", gloss_short=None)
    assert p["speak_text"] == "事，事情的事"
    assert p["speak_incomplete"] is False
    assert p["accept"] == ["事", "事情"]


def test_build_speak_word_complete():
    p = build_speak_payload(word="认真", kind="phrase", compound=None, gloss_short="做事仔细")
    assert p["speak_text"] == "认真，做事仔细"
    assert p["accept"] == ["认真"]


def test_build_speak_fallback():
    p = build_speak_payload(word="事", kind="write", compound=None, gloss_short=None)
    assert p["speak_text"] == "事，事"
    assert p["speak_incomplete"] is True
    assert p["accept"] == ["事"]


def test_cue_roundtrip():
    raw = dump_cue({"compound": "事情", "gloss_short": "", "source": "ai"})
    assert parse_cue(raw)["compound"] == "事情"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_dictation_speak.py -v`  
Expected: FAIL（`ModuleNotFoundError` / import error）

- [ ] **Step 3: 实现纯函数**

Create `backend/app/services/dictation_speak.py`：

```python
"""语文听写课堂报读：分类、种子化、拼装 speak_text/accept。"""
from __future__ import annotations
import json
import re

from .word_kinds import KIND_PHRASE, KIND_RECOGNIZE, KIND_WORD, KIND_WRITE

_HAN = re.compile(r"[\u4e00-\u9fff]+")


def _han_len(s: str) -> int:
    return len("".join(_HAN.findall(s or "")))


def _han_only(s: str) -> str:
    return "".join(_HAN.findall(s or ""))


def classify_speak_mode(*, kind: str | None, word: str) -> str:
    k = (kind or "").strip()
    if k in (KIND_WRITE, KIND_RECOGNIZE):
        return "char"
    if k in (KIND_PHRASE, KIND_WORD):
        return "word"
    return "char" if _han_len(word) <= 1 else "word"


def _extra_gloss_part(extra: str) -> str:
    parts = (extra or "").strip().split()
    if len(parts) <= 1:
        return (extra or "").strip()
    return " ".join(parts[1:]).strip()


def seed_compound_from_extra(word: str, extra: str) -> str | None:
    g = _han_only(_extra_gloss_part(extra))
    if not g or word not in g:
        return None
    n = _han_len(g)
    if 2 <= n <= 4:
        return g
    return None


def gloss_from_extra(word: str, extra: str) -> str | None:
    g = _extra_gloss_part(extra).strip()
    if not g:
        return None
    # 去掉可能的非汉字噪音后量汉字长度；保留原文短释义供播报
    if _han_len(g) == 0 or _han_len(g) > 8:
        return None
    return g


def parse_cue(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def dump_cue(cue: dict) -> str:
    return json.dumps(cue or {}, ensure_ascii=False)


def valid_compound(word: str, compound: str | None) -> str | None:
    c = (compound or "").strip()
    if not c or word not in c:
        return None
    if not (2 <= _han_len(c) <= 4):
        return None
    return c


def valid_gloss(gloss: str | None) -> str | None:
    g = (gloss or "").strip()
    if not g or _han_len(g) == 0 or _han_len(g) > 8:
        return None
    return g


def build_speak_payload(
    *, word: str, kind: str | None, compound: str | None, gloss_short: str | None
) -> dict:
    mode = classify_speak_mode(kind=kind, word=word)
    if mode == "char":
        c = valid_compound(word, compound)
        if c:
            return {
                "speak_text": f"{word}，{c}的{word}",
                "speak_incomplete": False,
                "accept": [word, c],
            }
        return {
            "speak_text": f"{word}，{word}",
            "speak_incomplete": True,
            "accept": [word],
        }
    g = valid_gloss(gloss_short)
    if g:
        return {
            "speak_text": f"{word}，{g}",
            "speak_incomplete": False,
            "accept": [word],
        }
    return {
        "speak_text": f"{word}，{word}",
        "speak_incomplete": True,
        "accept": [word],
    }


def resolve_cues_for_word(*, word: str, kind: str | None, extra: str, cue_raw: str | None) -> dict:
    """合并 dictation_cue + extra 种子，返回 {compound, gloss_short, source}。"""
    cue = parse_cue(cue_raw)
    compound = valid_compound(word, cue.get("compound"))
    gloss = valid_gloss(cue.get("gloss_short"))
    source = cue.get("source") or ""
    mode = classify_speak_mode(kind=kind, word=word)
    if mode == "char" and not compound:
        seeded = seed_compound_from_extra(word, extra)
        if seeded:
            compound, source = seeded, source or "extra"
    if mode == "word" and not gloss:
        seeded_g = gloss_from_extra(word, extra)
        if seeded_g:
            gloss, source = seeded_g, source or "extra"
    return {"compound": compound or "", "gloss_short": gloss or "", "source": source}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_dictation_speak.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/dictation_speak.py backend/tests/test_dictation_speak.py
git commit -m "feat(dictation): add classroom speak pure helpers"
```

---

### Task 2: `WordBank.dictation_cue` 列

**Files:**
- Modify: `backend/app/models.py`（`WordBank`）
- Test: 可在 `test_dictation_speak.py` 增加 ORM 读写烟测，或依赖 `schema_sync` + 现有 conftest

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_dictation_speak.py` 追加（用 conftest 的 `db` fixture；若无则按 `test_task_gen.py` 的 helper）：

```python
def test_wordbank_dictation_cue_column(setup_db, db):
    from app.models import Lesson, PdfDocument, WordBank
    # 最小插入：按 test_task_gen 现有建课方式取一个 lesson_id
    # 断言 WordBank(..., dictation_cue='{"compound":"事情"}') 可 commit 并读回
```

实现时对照 `backend/tests/test_task_gen.py` 里创建 `WordBank` 的 helper，复制最小 fixture。

- [ ] **Step 2: 跑测确认失败**（无该列 / TypeError）

- [ ] **Step 3: 改模型**

在 `WordBank` 的 `extra` 旁增加：

```python
dictation_cue: Mapped[str] = mapped_column(LongText, default="")  # JSON {compound,gloss_short,source}
```

`schema_sync` 启动时会补列；pytest 用 `create_all` 的话新库直接有列。确认 `backend/tests/conftest.py` 是否 `create_all`——有则测通。

- [ ] **Step 4: 测试通过并 Commit**

```bash
git add backend/app/models.py backend/tests/test_dictation_speak.py
git commit -m "feat(models): WordBank.dictation_cue for speak compounds"
```

---

### Task 3: AI 补全服务（可 mock）

**Files:**
- Create: `backend/app/services/dictation_cue_fill.py`
- Test: `backend/tests/test_dictation_speak.py`（或 `test_dictation_cue_fill.py`）

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import MagicMock, patch
from app.services.dictation_cue_fill import fill_missing_cues


def test_fill_missing_cues_writes_compound(setup_db, db):
    # 用 conftest.make_lesson / test_task_gen 方式建 WordBank(word="事", kind="write", extra="", dictation_cue="")
    # mock provider.generate 返回 JSON：{"items":[{"id": wb.id, "compound": "事情", "gloss_short": ""}]}
    # 断言调用时 timeout=15（或计划常量 FILL_TIMEOUT_SEC）
    # fill_missing_cues(db, [wb])
    # 断言 parse_cue(wb.dictation_cue)["compound"] == "事情"


def test_fill_missing_cues_ai_failure_noop(setup_db, db):
    with patch("app.services.dictation_cue_fill.get_provider", side_effect=RuntimeError("no ai")):
        fill_missing_cues(db, [wb])  # 不抛；cue 仍空


def test_fill_missing_cues_passes_short_timeout(setup_db, db):
    # mock generate，断言 kwargs/positional 含 timeout≈15
```

- [ ] **Step 2: 实现**

`fill_missing_cues(db, words: list[WordBank], timeout: float = 15.0) -> None`：

1. 对每条 `resolve_cues_for_word`；若 mode=char 且无 compound，或 mode=word 且无 gloss → 入 `need`。  
2. `need` 空则返回。  
3. `get_provider(db).generate(prompt, system=..., json_mode=True, timeout=timeout)`（**短超时，默认 15s**；超时/异常则整批不写，由上层兜底 `speak_incomplete`）。  
4. 解析 `items`；校验后写回：`valid_compound`；AI 回写的 gloss 额外要求汉字长 **4–8**（比 `extra` 种子的「仅 ≤8」更严）。`dump_cue(..., source=ai)`，`db.flush()`。  
5. 任何异常 swallow，不抛。

Prompt 要点：小学适用；单字组词 2–4 字且含该字；词语释义 4–8 字；只返回 JSON。

- [ ] **Step 3: 测试通过并 Commit**

```bash
git add backend/app/services/dictation_cue_fill.py backend/tests/test_dictation_speak.py
git commit -m "feat(dictation): AI fill missing compounds/gloss for speak"
```

---

### Task 4: 接入 `_gen_dictation`

**Files:**
- Modify: `backend/app/services/task_gen.py`（`_gen_dictation` 返回 `Task` 前）
- Test: `backend/tests/test_task_gen.py` 或 `test_dictation_speak.py`

- [ ] **Step 1: 写失败测试**

```python
def test_dictation_content_has_speak_text_for_chinese(setup_db, db):
    # 造语文课 + WordBank(word="事", kind="write", extra="shì 事情")
    # generate_daily_tasks / _gen_dictation
    # content JSON 每项含 speak_text, speak_incomplete, accept
    # 因 extra 种子：「事，事情的事」, incomplete False, accept 含「事情」


def test_dictation_english_unchanged_no_speak_required(setup_db, db):
    # 英语听写 content 可不含 speak_text；不得调用 fill_missing_cues
```

**Mock 路径（重要）：** 因 `fill_missing_cues` 在函数内 import，测试必须：

```python
with patch("app.services.dictation_cue_fill.fill_missing_cues") as m:
    ...
```

不要 patch `app.services.task_gen.fill_missing_cues`（局部 import 绑不到）。

- [ ] **Step 2: 改 `_gen_dictation`**

在 `picked = picked[:count]` 之后、`return Task(...)` 之前：

```python
items = []
if subject == "语文":
    from .dictation_cue_fill import fill_missing_cues
    from .dictation_speak import build_speak_payload, resolve_cues_for_word, dump_cue, parse_cue
    fill_missing_cues(db, picked)  # 内部 timeout=15；失败则后续 incomplete
    db.flush()
    for w in picked:
        cues = resolve_cues_for_word(
            word=w.word, kind=w.kind, extra=w.extra or "",
            cue_raw=getattr(w, "dictation_cue", None) or "",
        )
        # 若 resolve 从 extra 种子出了 compound 且原 cue 空，写回以免重复 AI
        if cues.get("compound") or cues.get("gloss_short"):
            existing = parse_cue(getattr(w, "dictation_cue", None) or "")
            if not existing.get("compound") and cues.get("compound"):
                existing["compound"] = cues["compound"]
                existing["source"] = cues.get("source") or "extra"
            if not existing.get("gloss_short") and cues.get("gloss_short"):
                existing["gloss_short"] = cues["gloss_short"]
                existing["source"] = existing.get("source") or cues.get("source") or "extra"
            w.dictation_cue = dump_cue(existing)
        payload = build_speak_payload(
            word=w.word, kind=w.kind,
            compound=cues.get("compound") or None,
            gloss_short=cues.get("gloss_short") or None,
        )
        items.append({
            "id": w.id, "word": w.word, "extra": w.extra, "kind": w.kind,
            **payload,
        })
else:
    items = [{"id": w.id, "word": w.word, "extra": w.extra, "kind": w.kind} for w in picked]

# Task.content = json.dumps(items, ...)
```

注意：现有 content 已含 `kind`（约 L171–174）；替换那段列表推导即可。

- [ ] **Step 3: 测试通过并 Commit**

```bash
git add backend/app/services/task_gen.py backend/tests/test_task_gen.py backend/tests/test_dictation_speak.py
git commit -m "feat(task_gen): enrich Chinese dictation with classroom speak_text"
```

---

### Task 5: 手写批改支持 `accept`

**Files:**
- Modify: `backend/app/services/handwriting.py`
- Modify: `backend/app/routers/learning.py`（注释更新 `GradeHandwritingReq.words`）
- Test: `backend/tests/test_handwriting.py`

- [ ] **Step 1: 写失败测试**

```python
def test_grading_instruction_includes_accept():
    from app.services.handwriting import _grading_instruction
    text = _grading_instruction([
        {"index": 0, "word": "事", "accept": ["事", "事情"]},
    ])
    assert "事情" in text


def test_apply_accept_overrides_model():
    from app.services.handwriting import apply_accept
    results = [{"index": 0, "written": "事情", "is_correct": False}]
    words = [{"index": 0, "word": "事", "accept": ["事", "事情"]}]
    out = apply_accept(results, words)
    assert out[0]["is_correct"] is True
```

- [ ] **Step 2: 实现**

- `_grading_instruction`：每行展示 `标准：{word}；也可接受：{accept 逗号分隔}`（无 accept 则仅 word）。  
- 新增 `apply_accept(results, words)`：按 index 对齐；若 `written` 去掉空白后 ∈ `accept`（缺省则 `[word]`）→ `is_correct=True`；若 written 非空且不在 accept → 可保持模型结果或强制 False（推荐：**在 accept 内则 True，否则保留模型 is_correct**，避免 OCR 微差误杀——但宽判场景「事情」必须 True）。  
- `grade_handwriting` 末尾：`return apply_accept(parse_grading_result(raw), words)`。

- [ ] **Step 3: 测试通过并 Commit**

```bash
git add backend/app/services/handwriting.py backend/tests/test_handwriting.py backend/app/routers/learning.py
git commit -m "feat(handwriting): accept compound as correct for char dictation"
```

---

### Task 6: Flutter — 解析 `speak_text` / `accept` 并播报、批改（含错词重写）

**Files:**
- Modify: `student-app/lib/features/dictation/data/dictation_repository.dart`
- Modify: `student-app/lib/features/dictation/paper_dictation_controller.dart`（`PaperWrongWord`、`speakText`、`_gradeWordPayload`、建 wrong 列表）
- Modify: `student-app/lib/features/dictation/ui/dictation_on_screen_view.dart`
- Modify: `student-app/lib/features/dictation/dictation_controller.dart`
- Test: `student-app/test/features/dictation/`（含 `paper_dictation_controller_test.dart`）

- [ ] **Step 1: 写失败测试（Dart）**

```dart
test('DictWord parses speak_text and accept', () {
  final w = DictWord.fromJson({
    'id': 1,
    'word': '事',
    'extra': 'shì 事情',
    'speak_text': '事，事情的事',
    'accept': ['事', '事情'],
  });
  expect(w.speakText, '事，事情的事');
  expect(w.accept, ['事', '事情']);
});

test('DictWord speakText falls back to word', () {
  final w = DictWord.fromJson({'id': 1, 'word': '事', 'extra': ''});
  expect(w.speakText, '事');
});
```

另加：错词重写轮 `speakText()` 仍返回原 `speak_text`；`_gradeWordPayload` 在 rewriting 时带 `accept`（可测 controller 的 payload 构造或通过 public API）。

- [ ] **Step 2: 扩展 `DictWord`（带默认值，避免旧测试编不过）**

```dart
const DictWord({
  required this.id,
  required this.word,
  required this.extra,
  this.speakTextRaw,
  this.accept = const [],
});
final String? speakTextRaw;
final List<String> accept;
String get speakText =>
    (speakTextRaw != null && speakTextRaw!.isNotEmpty) ? speakTextRaw! : word;
```

`fromJson` 解析 `speak_text`、`accept`。

- [ ] **Step 3: `PaperWrongWord` 保留报读线索**

扩展字段：`speakText`（String）、`accept`（`List<String>`），构造与 `copyWith` 带默认 `''` / `const []`。

在 `_applyGradeResults` 首轮建 wrong 时从 `DictWord` 拷贝：

```dart
PaperWrongWord(
  word: w.word, id: w.id, pinyin: w.pinyin, meaning: w.meaning,
  yours: ..., written: ...,
  speakText: w.speakText, accept: w.accept,
)
```

- [ ] **Step 4: 播报与批改（主路径 + 重写）**

- `_currentWord` 在 rewriting 时：用 `PaperWrongWord` 合成 `DictWord(..., speakTextRaw: w.speakText, accept: w.accept)`（或直接让 `speakText()` 读 wrong 条目）。  
- `speakText()` → 当前条目的课堂句，**重听同一句**（禁止回退成单字）。  
- `_gradeWordPayload()` 两支都带 accept：

```dart
{'index': i, 'word': ..., 'accept': acceptList.isEmpty ? [word] : acceptList}
```

- 屏幕书写 `submitHandwriting` 同样传 `accept`。  
- `dictation_on_screen_view` → `speak(word.speakText)`。

- [ ] **Step 5: 跑测**

Run: `E:\dev\flutter\bin\flutter test test/features/dictation/`  
Expected: PASS（含既有 `paper_dictation_controller_test`）

- [ ] **Step 6: Commit**

```bash
git add student-app/lib/features/dictation student-app/test/features/dictation
git commit -m "feat(student-app): speak classroom prompt and send accept"
```

---

### Task 7: 家长端「报读待补」

**Files:**
- Modify: `backend/app/routers/tasks.py`（`_to_dict`）
- Modify: `parent-web/app.js`（`renderTaskTab`）
- Test: `backend/tests/test_tasks.py`（若无则新建最小测，或在 API 测里断言）

- [ ] **Step 1: 后端 helper + 测试**

```python
def speak_incomplete_count(content: str) -> int:
    try:
        data = json.loads(content or "[]")
    except (ValueError, TypeError):
        return 0
    if not isinstance(data, list):
        return 0
    return sum(1 for x in data if isinstance(x, dict) and x.get("speak_incomplete") is True)
```

可放在 `dictation_speak.py`；`_to_dict`：

```python
"speak_incomplete_count": speak_incomplete_count(t.content) if t.task_type == "dictation" else 0,
```

- [ ] **Step 2: 家长 UI**

在 `renderTaskTab` 的 meta 或 title 旁：

```javascript
const incomplete = (t.task_type==='dictation' && t.speak_incomplete_count>0)
  ? `<span style="font-size:11px;color:#c05b4a">报读待补 ${t.speak_incomplete_count}</span>` : '';
```

展开待补词列表（YAGNI 最小）：点击或在 `detail` 下用 `<details>` 列出 `content` 里 `speak_incomplete` 的 `word`（家长端已有 `t.content` 字符串，可 `JSON.parse`）。

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/tasks.py backend/app/services/dictation_speak.py parent-web/app.js backend/tests/
git commit -m "feat(parent): show dictation speak_incomplete count"
```

---

### Task 8: 回归与收尾

- [ ] **Step 1: 后端全量相关测**

Run: `cd backend && python -m pytest tests/test_dictation_speak.py tests/test_task_gen.py tests/test_handwriting.py -v`  
Expected: PASS

- [ ] **Step 2: Flutter analyze（dictation 相关）**

Run: `E:\dev\flutter\bin\flutter analyze lib/features/dictation`  
Expected: no issues

- [ ] **Step 3: 手动冒烟（可选）**

1. 强制生成语文听写任务，查 DB/API `content` 含 `speak_text`  
2. 学生端重听听到「字，组词的字」  
3. AI 关掉时任务仍出且 `speak_incomplete_count>0`，家长可见  

- [ ] **Step 4: 最终 commit（若有漏网）**

---

## 实现注意

- **cwd**：后端测试与 uvicorn 均在 `backend/`。  
- **幂等**：`generate` force 会重跑 fill；已有合格 cue 不重复 AI。  
- **宽判**：错题本仍记目标 `word`，不要把组词建成新 `WordBank`。  
- **英语**：整条 enrichment 跳过。  
- **不要**改 `WordBank.extra` 格式（提示解析依赖空格拆分）。
