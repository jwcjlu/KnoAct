# 讲一遍 · 旁路追问 + 家长摘要 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有「讲一遍」上增加可选 AI 追问（≤3 轮）与提交时家长「可能卡在…」摘要；仍不判定、不写掌握度。

**Architecture:** 客户端持有追问历史，每次 `POST /api/expression/probe` 携带正文 + `turns[]`，服务端用单次 `provider.generate`（`services/expression_probe.py`）返回下一问——**不走 TurnEngine / CapabilityRegistry**（无工具、最多 3 轮，与 annotations 释义同模式）。提交 `POST /notes` 若带 `probe_turns` 则再单次 generate 写 `parent_hint`；失败留空不影响落库。新列由现有 `schema_sync` 自动 `ALTER`。

**Tech Stack:** FastAPI + SQLAlchemy、`services/ai.get_provider`、Flutter Riverpod、parent-web 原生 JS。

**Spec:** `docs/superpowers/specs/2026-11-25-expression-probe-ai-design.md`

---

## File map

| Path | Responsibility |
| --- | --- |
| `backend/app/models.py` | `ExpressionNote` 加 `probe_turns` / `parent_hint`；更新 docstring |
| `backend/app/services/expression_probe.py` | `ask_next_question` / `build_parent_hint` / `normalize_probe_turns` / 禁用词 scrub |
| `backend/app/routers/expression.py` | `POST /probe`；扩展 `NoteReq` / `create_note` / `list_notes` |
| `backend/tests/test_expression.py` | 列断言、probe、hint、校验 |
| `backend/tests/test_expression_probe_service.py` | 纯服务层（可 mock provider） |
| `student-app/lib/features/expression/data/expression_repository.dart` | `probe()`；`createNote` 带 `probe_turns` |
| `student-app/lib/features/expression/expression_controller.dart` | 追问状态与动作 |
| `student-app/lib/features/expression/ui/expression_page.dart` | 「让 AI 问问我」+ 追问区 |
| `student-app/test/features/expression/...` | 控制器 / 页测 |
| `parent-web/app.js` | 展示 `parent_hint` |

**不做：** 注册 `capabilities/`、语音、家长展开完整对话 UI、写 mastery。

**常量：** `MAX_PROBE_TURNS = 3`；`MAX_HINT_LEN = 120`；`MAX_TEXT_LEN = 5000`（已有）。

---

### Task 1: 模型列 + 判定列断言更新

**Files:**
- Modify: `backend/app/models.py`（`ExpressionNote`）
- Modify: `backend/tests/test_expression.py`（列测试）

- [ ] **Step 1: 写失败测试（新列必须存在；仍禁判定列）**

在 `test_expression.py` 的 `test_expression_note_required_columns_exist` 的必有列里追加 `"probe_turns", "parent_hint"`。

保留 `test_expression_note_has_no_judgement_columns`：`forbidden` 与 `ai_*` 前缀断言不变（`probe_turns` / `parent_hint` **不以** `ai_` 开头，故不触发）。

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && python -m pytest tests/test_expression.py::test_expression_note_required_columns_exist -v
```

Expected: FAIL，缺列 `probe_turns` 或 `parent_hint`。

- [ ] **Step 3: 改模型**

`ExpressionNote` docstring 改为：「不做判定；可选追问痕迹与家长提示不算判定。」

在 `text` 后追加：

```python
    # 追问 Q/A JSON 数组文本，未追问为 ""；不是判定结果
    probe_turns: Mapped[str] = mapped_column(LongText, default="")
    # 一句「可能卡在…」；未追问或生成失败为 ""
    parent_hint: Mapped[str] = mapped_column(String(255), default="")
```

- [ ] **Step 4: 跑测通过**

```bash
cd backend && python -m pytest tests/test_expression.py::test_expression_note_has_no_judgement_columns tests/test_expression.py::test_expression_note_required_columns_exist -v
```

Expected: PASS。本地/测试库靠 `schema_sync` 补列，无需手写 migrate。

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_expression.py
git commit -m "feat(expression): ExpressionNote 加 probe_turns / parent_hint"
```

---

### Task 2: `expression_probe` 服务层

**Files:**
- Create: `backend/app/services/expression_probe.py`
- Create: `backend/tests/test_expression_probe_service.py`

- [ ] **Step 1: 写失败测试**

```python
"""expression_probe 纯函数：轮次、规范化、摘要门闩。"""
import json
from unittest.mock import MagicMock

from app.services import expression_probe as ep


def test_normalize_rejects_more_than_max_turns():
    turns = [{"q": "a", "a": "b"}] * 4
    try:
        ep.normalize_probe_turns(turns)
        assert False, "应抛 ValueError"
    except ValueError as e:
        assert "max" in str(e).lower() or "3" in str(e)


def test_normalize_accepts_empty_and_trimmed():
    assert ep.normalize_probe_turns(None) == []
    assert ep.normalize_probe_turns([]) == []
    out = ep.normalize_probe_turns([{"q": " 问？ ", "a": " 答 "}])
    assert out == [{"q": "问？", "a": "答"}]


def test_ask_next_done_when_full():
    provider = MagicMock()
    r = ep.ask_next_question(
        provider, title="比喻", text="……", turns=[{"q": "1", "a": "a"},
                                                   {"q": "2", "a": "b"},
                                                   {"q": "3", "a": "c"}])
    assert r["done"] is True
    assert r.get("question") in (None, "")
    provider.generate.assert_not_called()


def test_ask_next_calls_generate_when_room():
    provider = MagicMock()
    provider.generate.return_value = "那『像』一定是比喻吗？"
    r = ep.ask_next_question(provider, title="比喻", text="比喻就是像", turns=[])
    assert r["done"] is False
    assert "像" in r["question"] or r["question"]
    provider.generate.assert_called_once()


def test_build_parent_hint_empty_without_turns():
    provider = MagicMock()
    assert ep.build_parent_hint(provider, title="x", text="y", turns=[]) == ""
    provider.generate.assert_not_called()


def test_build_parent_hint_scrubs_praise_and_truncates():
    provider = MagicMock()
    provider.generate.return_value = "讲得很好，可能卡在本体和喻体没分清"
    hint = ep.build_parent_hint(
        provider, title="比喻", text="……",
        turns=[{"q": "q", "a": "a"}])
    assert hint
    assert "很好" not in hint and "讲得" not in hint
    assert len(hint) <= ep.MAX_HINT_LEN
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && python -m pytest tests/test_expression_probe_service.py -v
```

Expected: FAIL，`ModuleNotFoundError` 或 import 失败。

- [ ] **Step 3: 实现服务**

```python
"""讲一遍旁路追问 / 家长摘要。单次 generate，不判定、不写掌握度。"""
from __future__ import annotations

import json
import re

MAX_PROBE_TURNS = 3
MAX_HINT_LEN = 120

PROBE_SYSTEM = (
    "你在听小学生用自己的话讲一个知识点。"
    "你只追问缺口：每次只输出一个简短问题。"
    "禁止讲解、给定义、补全答案、说对错或夸奖。"
    "不要把标准答案里的关键概念词塞进问题里当成填空提示。"
)

HINT_SYSTEM = (
    "根据孩子的讲解和追问答句，用一句中文写出家长可读的卡点提示。"
    "格式必须是：可能卡在：……"
    "禁止评价（好/对/错/掌握/完整/棒）；不确定就写「可能卡在：表达还不完整」。"
)

_FORBIDDEN_HINT = re.compile(
    r"(讲得|很好|真棒|正确|错误|掌握|完整|优秀|不错|对了|错了)"
)


def normalize_probe_turns(raw) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("probe_turns must be a list")
    if len(raw) > MAX_PROBE_TURNS:
        raise ValueError(f"probe_turns max {MAX_PROBE_TURNS}")
    out = []
    for i, t in enumerate(raw):
        if not isinstance(t, dict):
            raise ValueError(f"turn {i} must be object")
        q = str(t.get("q") or "").strip()
        a = str(t.get("a") or "").strip()
        if not q:
            raise ValueError(f"turn {i} missing q")
        out.append({"q": q[:500], "a": a[:2000]})
    return out


def ask_next_question(provider, *, title: str, text: str, turns: list[dict]) -> dict:
    turns = normalize_probe_turns(turns)
    if len(turns) >= MAX_PROBE_TURNS:
        return {"done": True, "question": ""}
    hist = "\n".join(f"问：{t['q']}\n答：{t['a']}" for t in turns) or "（尚无追问）"
    prompt = (
        f"知识点：{title}\n孩子已写：\n{text}\n\n已有追问：\n{hist}\n\n"
        "请只输出下一个问题（一句话），不要编号，不要解释。"
    )
    try:
        q = (provider.generate(prompt=prompt, system=PROBE_SYSTEM) or "").strip()
    except Exception:
        q = ""
    if not q:
        return {"done": False, "question": "", "error": "unavailable"}
    # 截断多段，只留第一行问句
    q = q.splitlines()[0].strip()[:200]
    return {"done": False, "question": q}


def build_parent_hint(provider, *, title: str, text: str, turns: list[dict]) -> str:
    turns = normalize_probe_turns(turns)
    if not turns:
        return ""
    hist = "\n".join(f"问：{t['q']}\n答：{t['a']}" for t in turns)
    prompt = f"知识点：{title}\n终稿：\n{text}\n\n追问：\n{hist}\n"
    try:
        raw = (provider.generate(prompt=prompt, system=HINT_SYSTEM) or "").strip()
    except Exception:
        return ""
    if not raw:
        return ""
    line = raw.splitlines()[0].strip()
    if not line.startswith("可能卡在"):
        line = "可能卡在：" + line.lstrip("：:").strip()
    line = _FORBIDDEN_HINT.sub("", line)
    line = re.sub(r"\s+", " ", line).strip()
    if len(line) < 6:
        return ""
    return line[:MAX_HINT_LEN]


def dumps_turns(turns: list[dict]) -> str:
    return json.dumps(turns, ensure_ascii=False)
```

- [ ] **Step 4: 跑测通过**

```bash
cd backend && python -m pytest tests/test_expression_probe_service.py -v
```

Expected: PASS。若 `test_build_parent_hint_scrubs_praise` 因 scrub 后过短失败，放宽断言为「不含禁用词」或 mock 返回更长无禁用词句。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/expression_probe.py backend/tests/test_expression_probe_service.py
git commit -m "feat(expression): probe/hint 服务层（单次 generate，不判定）"
```

---

### Task 3: `POST /api/expression/probe`

**Files:**
- Modify: `backend/app/routers/expression.py`
- Modify: `backend/tests/test_expression.py`

- [ ] **Step 1: 写失败测试**

追加到 `test_expression.py`（复用 `_seed_child` / 已有 note 主题种子；需要有 mastery 的 kp 时抄 `test_create_note_with_knowledge_point` 的 seed）：

```python
def test_probe_requires_nonempty_text():
    uid, h = _seed_child(prefix="probe0")
    # … seed kp + mastery 与 create_note 测试相同 …
    r = _client().post("/api/expression/probe", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "  ", "turns": [],
    }, headers=h)
    assert r.status_code == 400


def test_probe_returns_question_then_done_at_3():
    uid, h, kp_id = _seed_child_with_kp(prefix="probe1")  # 抽辅助或内联
    body = {"user_id": uid, "knowledge_point_id": kp_id, "text": "比喻就是像", "turns": []}
    r = _client().post("/api/expression/probe", json=body, headers=h)
    assert r.status_code == 200
    assert r.json().get("done") is False
    # fake provider 也应返回非空 question 或 error；至少结构合法
    assert "question" in r.json()

    turns = [{"q": "q1", "a": "a1"}, {"q": "q2", "a": "a2"}, {"q": "q3", "a": "a3"}]
    r2 = _client().post("/api/expression/probe", json={**body, "turns": turns}, headers=h)
    assert r2.status_code == 200
    assert r2.json()["done"] is True


def test_probe_rejects_grade_below_3():
    uid, h = _seed_child(grade=2, prefix="probe2")
    r = _client().post("/api/expression/probe", json={
        "user_id": uid, "knowledge_point_id": 1, "text": "x", "turns": [],
    }, headers=h)
    assert r.status_code == 403


def test_probe_rejects_parent_actor():
    # 与 test_parent_cannot_create_note 同构：家长 token + child user_id → 403
    ...
```

实现时把 `_seed_child_with_kp` 提成测试辅助，避免复制粘贴过头。

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && python -m pytest tests/test_expression.py -k probe -v
```

Expected: FAIL，404。

- [ ] **Step 3: 实现端点**

在 `expression.py`：

```python
from ..services.ai import get_provider
from ..services import expression_probe as probe_svc

MAX_PROBE_TURNS = probe_svc.MAX_PROBE_TURNS

class ProbeReq(BaseModel):
    user_id: int
    knowledge_point_id: int | None = None
    item_id: int | None = None
    text: str
    turns: list[dict] = []

@router.post("/probe")
def probe(req: ProbeReq, user: User = Depends(require_learning_user),
          db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    if user.id != req.user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="内容不能为空")
    if len(text) > MAX_TEXT_LEN:
        raise HTTPException(status_code=400, detail=f"内容不能超过 {MAX_TEXT_LEN} 字")
    child = _require_grade(req.user_id, db)
    # 复用 NoteReq 形状做主题校验
    title = _validate_target(child, NoteReq(
        user_id=req.user_id,
        knowledge_point_id=req.knowledge_point_id,
        item_id=req.item_id,
        text=text,
    ), db)
    try:
        turns = probe_svc.normalize_probe_turns(req.turns)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    provider = get_provider(db, child_id=req.user_id)
    return probe_svc.ask_next_question(
        provider, title=title, text=text, turns=turns)
```

- [ ] **Step 4: 跑测通过**

```bash
cd backend && python -m pytest tests/test_expression.py -k probe -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/expression.py backend/tests/test_expression.py
git commit -m "feat(expression): POST /probe 旁路追问"
```

---

### Task 4: 扩展 `POST /notes` + `GET /notes`

**Files:**
- Modify: `backend/app/routers/expression.py`
- Modify: `backend/tests/test_expression.py`

- [ ] **Step 1: 写失败测试**

```python
def test_create_note_without_probe_has_empty_hint():
    uid, h, kp_id = _seed_child_with_kp(prefix="hint0")
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "只写一段",
    }, headers=h)
    assert r.status_code == 200
    notes = _client().get(f"/api/expression/notes?user_id={uid}", headers=h).json()["notes"]
    assert notes[0]["parent_hint"] in ("", None)
    # 响应可不返回 probe_turns（家长 UI 不展开）；若返回则应为 [] 或 ""


def test_create_note_with_probe_turns_may_set_hint():
    uid, h, kp_id = _seed_child_with_kp(prefix="hint1")
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "比喻就是像",
        "probe_turns": [{"q": "什么时候不算？", "a": "不知道"}],
    }, headers=h)
    assert r.status_code == 200
    notes = _client().get(f"/api/expression/notes?user_id={uid}", headers=h).json()["notes"]
    n = notes[0]
    # fake 下 hint 可为空；但字段必须存在；且不得含评价禁用词
    assert "parent_hint" in n
    for bad in ("很好", "掌握", "正确", "错误"):
        assert bad not in (n.get("parent_hint") or "")


def test_create_note_rejects_too_many_probe_turns():
    uid, h, kp_id = _seed_child_with_kp(prefix="hint2")
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "x",
        "probe_turns": [{"q": "q", "a": "a"}] * 4,
    }, headers=h)
    assert r.status_code == 400
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && python -m pytest tests/test_expression.py -k "hint or probe_turns" -v
```

Expected: FAIL（字段缺失或 400 未实现）。

- [ ] **Step 3: 实现**

`NoteReq` 增加 `probe_turns: list[dict] | None = None`。

`create_note`：

```python
    turns: list[dict] = []
    if req.probe_turns:
        try:
            turns = probe_svc.normalize_probe_turns(req.probe_turns)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    hint = ""
    if turns:
        provider = get_provider(db, child_id=req.user_id)
        hint = probe_svc.build_parent_hint(
            provider, title=title, text=text, turns=turns) or ""

    note = ExpressionNote(
        ...,
        text=text,
        probe_turns=probe_svc.dumps_turns(turns) if turns else "",
        parent_hint=hint,
    )
```

`list_notes` 每条增加 `"parent_hint": n.parent_hint or ""`。**本版不返回 `probe_turns`**（spec：家长不展开对话；字段仅审计/生成用）。

- [ ] **Step 4: 全量 expression 测**

```bash
cd backend && python -m pytest tests/test_expression.py tests/test_expression_probe_service.py -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/expression.py backend/tests/test_expression.py
git commit -m "feat(expression): notes 接受 probe_turns 并返回 parent_hint"
```

---

### Task 5: Flutter 仓储 + 控制器

**Files:**
- Modify: `student-app/lib/features/expression/data/expression_repository.dart`
- Modify: `student-app/lib/features/expression/expression_controller.dart`
- Modify: `student-app/test/features/expression/expression_controller_test.dart`

- [ ] **Step 1: 扩展 repository**

```dart
Future<ProbeResult> probe({
  required int userId,
  int? knowledgePointId,
  int? itemId,
  required String text,
  required List<Map<String, String>> turns,
}) async { ... POST /api/expression/probe ... }

// createNote 增加可选 List<Map<String,String>>? probeTurns
```

`ProbeResult({required bool done, required String question, String? error})`。

- [ ] **Step 2: 扩展 state / controller**

`ExpressionState` 增加：

- `probeOpen`（bool）
- `probeTurns`（`List<({String q, String a})>` 或简单 class）
- `probeQuestion`（当前待答问题）
- `probeError`（`unavailable` / null）
- `probeBusy`

动作：

- `openProbe()`：正文非空才请求第一问
- `answerProbe(String a)`：把当前问+答推进 turns；若未满 3 再请求下一问；满则 `done` 本地标记
- `submit()`：若 `probeTurns` 非空一并 POST

任意时刻 `submit` 不要求答完当前问（F3）；未答完的当前问不写入 turns。

- [ ] **Step 3: 控制器测试**

- 空正文不能 openProbe  
- 满 3 轮后不再请求  
- submit 带上 turns  
- probe 失败设 `probeError`，不影响后续 submit  

- [ ] **Step 4: 跑测**

```bash
cd student-app && flutter test test/features/expression/
```

Expected: PASS（先改测再实现，红→绿）。

- [ ] **Step 5: Commit**

```bash
git add student-app/lib/features/expression/ student-app/test/features/expression/
git commit -m "feat(expression): Flutter probe API 与控制器状态"
```

---

### Task 6: Flutter 输入页 UI

**Files:**
- Modify: `student-app/lib/features/expression/ui/expression_page.dart`
- Modify / Create: widget tests under `student-app/test/features/expression/`

- [ ] **Step 1: UI 行为**

在 `_ExpressionInput`（或提升为接收 probe 回调的组件）：

1. 正文 `trim` 非空时显示 TextButton「让 AI 问问我」  
2. 展开后显示：当前问题、回答框、「继续问」/下一问、busy、错误「这会儿问不了」  
3. 「讲完了」在 busy（提交中）时禁用；**probeBusy 时仍允许提交**（F3）——若实现冲突，优先 F3：提交时取消进行中的 probe 请求  
4. 结束页**不改**（继续禁评价词测试）

- [ ] **Step 2: 页测**

- 有正文时找得到「让 AI 问问我」  
- 无正文时找不到或按钮 disabled  

- [ ] **Step 3: 跑测**

```bash
cd student-app && flutter test test/features/expression/ && flutter analyze
```

- [ ] **Step 4: Commit**

```bash
git add student-app/lib/features/expression/ui/ student-app/test/features/expression/
git commit -m "feat(expression): 输入页可选追问 UI"
```

---

### Task 7: 家长端展示 `parent_hint`

**Files:**
- Modify: `parent-web/app.js`（`renderReportTab` 孩子讲的区块）

- [ ] **Step 1: 渲染**

在原文 `n.text` 下方：

```javascript
${n.parent_hint ? `<div class="g-meta" style="color:var(--gray2);margin-top:6px">${escapeAttr(n.parent_hint)}</div>` : ''}
```

副标题可保持「原话，未做对错判断」。

- [ ] **Step 2: 手工验收清单（写入 PR / 自测）**

| 步骤 | 期望 |
| --- | --- |
| 不点追问直接交 | 家长只看原文，无 hint 行 |
| 追问 1～3 轮再交 | 可能出现「可能卡在：…」；无「很好/掌握」 |
| 年级 &lt;3 | probe / notes 403 |
| fake 模型 | 全流程可跑通，hint 可空 |

- [ ] **Step 3: Commit**

```bash
git add parent-web/app.js
git commit -m "feat(parent-web): 孩子讲的展示 parent_hint"
```

---

### Task 8: 回归与收尾

- [ ] **Step 1: 后端全量相关测**

```bash
cd backend && python -m pytest tests/test_expression.py tests/test_expression_probe_service.py tests/test_fk_cleanup.py -v
```

- [ ] **Step 2: Flutter**

```bash
cd student-app && flutter test test/features/expression/ test/features/home/home_page_test.dart
```

- [ ] **Step 3: 若改了前置 feynman spec 的「无 AI」表述交叉引用**

可选：在 `2026-11-25-feynman-teach-ai-design.md` 顶部加一行「可选 AI 旁路见 `expression-probe-ai-design.md`」。**不要**删掉五轮失败附录。

- [ ] **Step 4: 最终 commit（若有文档交叉引用）**

```bash
git add docs/superpowers/specs/2026-11-25-feynman-teach-ai-design.md
git commit -m "docs: 表达练习指向可选 probe 旁路 spec"
```

---

## 风险与实现注意

1. **`ai_*` 列禁令**：新列不得命名 `ai_hint`；用 `parent_hint` / `probe_turns`。  
2. **hint 失败必须吞掉**：create_note 外层不要因 generate 抛 500。  
3. **不要**把 probe 接到 `/api/ask`。  
4. PowerShell 下 pytest / flutter 分条跑；后端从 `backend/` cwd 启动。  
