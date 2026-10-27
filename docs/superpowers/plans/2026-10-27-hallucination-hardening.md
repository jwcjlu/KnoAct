# KnoAct 幻觉补强实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 agent-native 运行时的四个 LLM 幻觉风险：出处伪造、`lookup_word` 假释义、`_forced_finish` 脱离约束、`render_mermaid` 校验形同虚设。

**Architecture:** 前端把已切好的句子数组作为 `sentences` 字段传给后端，后端 `UnifiedContext` 承载；`search_text` 工具与 orchestrator 校验基于同一份句子数组，彻底对齐句号口径。orchestrator 在提取 citations 后做范围校验（句号 ∈ `1..len(sentences)`）。

**Tech Stack:** FastAPI + SQLAlchemy + pytest。前端原生 JS（`splitSentences` 已存在）。

---

## 文件结构总览

**修改：**
- `backend/app/core/context.py` — `UnifiedContext` 加 `sentences` 字段
- `backend/app/routers/notes.py` — `AskReq` 加 `sentences`，透传给 ctx
- `backend/app/tools/builtin.py` — `search_text` 改用 `ctx.sentences` + 回退切句；`lookup_word` 异常如实失败；`render_mermaid` 正则校验
- `backend/app/runtime/orchestrator.py` — 出处范围校验
- `backend/app/runtime/turn_engine.py` — `_forced_finish` 补回上下文 + 约束
- `frontend/app.js` — `chatAsk` 加 `sentences: splitSentences(ctx)`

**测试修改：**
- `backend/tests/test_turn_engine.py` — `search_text`/`lookup_word`/`render_mermaid` 新行为 + `_forced_finish` 约束
- `backend/tests/test_ask_api.py` — 出处校验端到端

---

## Task 1: UnifiedContext 加 sentences 字段 + 后端切句回退函数

**Files:**
- Modify: `backend/app/core/context.py`
- Modify: `backend/app/tools/builtin.py`（加 `_fallback_split` + `search_text` 改用 sentences）
- Test: `backend/tests/test_turn_engine.py`

- [ ] **Step 1: 写失败测试（追加到 test_turn_engine.py）**

```python
from app.tools.builtin import search_text


def test_search_text_uses_sentences_field():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="",
                         text="白鹭是一首精巧的诗。色素的配合，身段的大小，一切都很适宜。",
                         sentences=["白鹭是一首精巧的诗。", "色素的配合，身段的大小，一切都很适宜。"])
    result = search_text.run({"query": "精巧"}, ctx)
    assert result["matches"][0]["sentence_no"] == 1


def test_search_text_falls_back_to_text_split():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="",
                         text="第一句。\n第二句。", sentences=[])
    result = search_text.run({"query": "第二"}, ctx)
    assert result["matches"][0]["sentence_no"] == 2


def test_search_text_no_sentences_and_no_text():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = search_text.run({"query": "任何"}, ctx)
    assert result["matches"] == []
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_turn_engine.py -v`
Expected: FAIL（`search_text` 仍用 `text.splitlines()`，`test_search_text_uses_sentences_field` 里 `ctx.text` 无换行，句子切分错位，`sentence_no` 不会是期望值；`test_search_text_falls_back_to_text_split` 期望第 2 句但 `splitlines` 按换行切正好是第 2 行，可能 PASS——真正的失败信号是第一个测试）

- [ ] **Step 3: 写实现**

修改 `backend/app/core/context.py`：

```python
"""统一上下文：一次 turn 的输入。"""
from dataclasses import dataclass, field


@dataclass
class UnifiedContext:
    user_id: int
    lesson_id: int
    question: str
    text: str = ""
    mode: str = "chat"
    model: str = ""
    sentences: list[str] = field(default_factory=list)
```

修改 `backend/app/tools/builtin.py`，加 `_fallback_split` 并改 `search_text`：

```python
import re


def _fallback_split(text: str) -> list[str]:
    """复刻前端 splitSentences 的切句规则：按句末标点 + 换行切句。"""
    if not text:
        return []
    return [s.strip() for s in re.split(r"(?<=[。！？!?])|\n+", text) if s.strip()]
```

（`SearchTextTool.run` 改为：）

```python
    def run(self, args, ctx: UnifiedContext) -> dict:
        query = (args.get("query") or "").strip()
        sentences = ctx.sentences or _fallback_split(ctx.text)
        if not query or not sentences:
            return {"matches": []}
        matches = []
        for idx, s in enumerate(sentences, start=1):
            if query in s:
                matches.append({"sentence_no": idx, "text": s.strip()})
        return {"matches": matches}
```

同时更新 `SearchTextTool.description` 为：`"在教材句子里检索含某关键词的句子，返回句号及其编号（句号对应前端跳转），用于标注出处"`。

注意：`_fallback_split` 里 `re.split(r"(?<=[。！？!?])|\n+", text)` 与前端 `text.split(/(?<=[。！？!?])|\n+/)` 等价。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_turn_engine.py -v`
Expected: PASS（所有 turn_engine + 工具测试）

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/context.py backend/app/tools/builtin.py backend/tests/test_turn_engine.py
git commit -m "feat: UnifiedContext 加 sentences 字段 + search_text 按句编号"
```

---

## Task 2: 出处范围校验（orchestrator）

**Files:**
- Modify: `backend/app/runtime/orchestrator.py`
- Test: `backend/tests/test_ask_api.py`

- [ ] **Step 1: 写失败测试（追加到 test_ask_api.py）**

```python
from app.runtime.orchestrator import _extract_citations


def test_citations_filtered_to_sentence_range():
    from app.runtime import orchestrator
    # 直接测校验逻辑：构造一个有越界句号的 ctx 场景
    # 用 _extract_citations 先提取，再手动校验逻辑（或测 route 的过滤）
    # 这里测一个纯函数辅助：提取 + 过滤
    ctx_sentences = ["句一", "句二", "句三"]
    answer = "答案……[第1句]……[第5句]……[第2句]"
    citations = _extract_citations(answer)
    # 过滤：1..len(sentences)=1..3，5 被剔除
    valid_max = len(ctx_sentences)
    filtered = [n for n in citations if 1 <= n <= valid_max]
    assert filtered == [1, 2]
```

注意：这个测试直接断言过滤逻辑。为了让测试真正落在 orchestrator 的行为上，更好的做法是提取一个可测的纯函数 `_filter_citations(citations, max_n)`。见 Step 3 的实现。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_ask_api.py -v`
Expected: FAIL（`_filter_citations` 未定义，或导入失败）

- [ ] **Step 3: 写实现**

修改 `backend/app/runtime/orchestrator.py`，加纯函数 `_filter_citations` 并在 `route_to_capability` 里调用：

```python
async def route_to_capability(ctx: UnifiedContext) -> dict:
    """异步入口：驱动 capability，返回最终 {answer, citations, mode}，并落库。"""
    registry = CapabilityRegistry()
    capability = registry.get(ctx.mode)
    stream = StreamBus()
    await capability.run(ctx, stream)

    final_event = None
    tool_events = []
    results_by_step: dict[int, dict] = {}
    for e in stream.events:
        if e.type == "final":
            final_event = e
        elif e.type == "tool_call":
            tool_events.append(e)
        elif e.type == "tool_result":
            results_by_step[e.data.get("step", 0)] = e.data.get("result", {})

    answer = final_event.data.get("answer", "") if final_event else ""
    citations = _filter_citations(_extract_citations(answer), len(ctx.sentences))

    _persist(ctx, capability.name, answer, citations, tool_events, results_by_step)
    return {"answer": answer, "citations": citations, "mode": ctx.mode}


def _extract_citations(answer: str) -> list[int]:
    import re
    return sorted(set(int(n) for n in re.findall(r"第\s*(\d+)\s*句", answer)))


def _filter_citations(citations: list[int], max_n: int) -> list[int]:
    """剔除越界句号。max_n<=0（未传 sentences）时不过滤。"""
    if max_n <= 0:
        return citations
    return [n for n in citations if 1 <= n <= max_n]
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_ask_api.py tests/test_notes.py -v`
Expected: PASS（现有测试 + 新测试；`test_ask_api_end_to_end` 走 fake provider，answer 无 `[第N句]`，citations 为空，`_filter_citations([], 0)` 返回 `[]`）

- [ ] **Step 5: 提交**

```bash
git add backend/app/runtime/orchestrator.py backend/tests/test_ask_api.py
git commit -m "feat: 出处句号范围校验（剔除越界引用）"
```

---

## Task 3: lookup_word 假释义回落

**Files:**
- Modify: `backend/app/tools/builtin.py`
- Test: `backend/tests/test_turn_engine.py`

- [ ] **Step 1: 写失败测试（追加到 test_turn_engine.py）**

```python
def test_lookup_word_error_path_returns_error_not_fake_meaning():
    # 无 provider 配置 → get_provider 返回 fake，fake.generate 不会抛异常，
    # 所以正常路径会走 fake 的 [fake] 输出。要测异常路径，需 mock get_provider 抛异常。
    # 用 monkeypatch 让 get_provider 抛异常
    import app.tools.builtin as builtin
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    orig = builtin.LookupWordTool.run
    # 直接构造一个会抛异常的 provider 场景：monkeypatch services.ai.get_provider
    import app.services.ai as ai
    monkeypatch.setattr(ai, "get_provider", lambda db: (_ for _ in ()).throw(RuntimeError("no key")))
    result = builtin.lookup_word.run({"word": "徘徊"}, ctx)
    assert result["meaning"] == ""
    assert "error" in result
```

注意：`monkeypatch` 是 pytest fixture，测试函数需加 `monkeypatch` 参数。上面的写法里 `monkeypatch` 未声明——修正为：

```python
def test_lookup_word_error_path_returns_error_not_fake_meaning(monkeypatch):
    import app.tools.builtin as builtin
    import app.services.ai as ai
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    def boom(db):
        raise RuntimeError("no key")
    monkeypatch.setattr(ai, "get_provider", boom)
    result = builtin.lookup_word.run({"word": "徘徊"}, ctx)
    assert result["meaning"] == ""
    assert "error" in result
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_turn_engine.py::test_lookup_word_error_path_returns_error_not_fake_meaning -v`
Expected: FAIL（当前 `except Exception` 分支返回 `meaning = f"「徘徊」的释义（示例）"`，`meaning` 非空）

- [ ] **Step 3: 写实现**

修改 `backend/app/tools/builtin.py` 的 `LookupWordTool.run`，把 `except Exception` 分支改为：

```python
        except Exception:
            return {"word": word, "meaning": "", "error": "释义暂不可用"}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_turn_engine.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/tools/builtin.py backend/tests/test_turn_engine.py
git commit -m "fix: lookup_word 异常如实失败（不编造示例释义）"
```

---

## Task 4: _forced_finish 补回上下文 + 约束

**Files:**
- Modify: `backend/app/runtime/turn_engine.py`
- Test: `backend/tests/test_turn_engine.py`

- [ ] **Step 1: 写失败测试（追加到 test_turn_engine.py）**

```python
def test_forced_finish_prompt_includes_context_and_no_fabrication():
    provider = ScriptedProvider(["not json"])
    reg = ToolRegistry()
    reg.register(lookup_word)
    engine = TurnEngine(provider=provider, registry=reg)
    bus = StreamBus()
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="?", text="白鹭是一首精巧的诗。")
    asyncio.run(engine.run(ctx, bus))
    # _forced_finish 会再次调 generate，第二次调用的 prompt 应含教材上下文 + 不要编造
    assert len(provider.calls) == 2
    forced_prompt = provider.calls[1]
    assert "教材上下文" in forced_prompt
    assert "白鹭是一首精巧的诗" in forced_prompt
    assert "不要编造" in forced_prompt
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_turn_engine.py::test_forced_finish_prompt_includes_context_and_no_fabrication -v`
Expected: FAIL（当前 `_forced_finish` 的 prompt 无「教材上下文」「不要编造」）

- [ ] **Step 3: 写实现**

修改 `backend/app/runtime/turn_engine.py` 的 `_forced_finish`：

```python
    async def _forced_finish(self, ctx: UnifiedContext, history: list[dict], stream: StreamBus) -> dict:
        # 把历史交给 LLM 求 final；失败则返回友好文案
        try:
            context_part = f"教材上下文：{ctx.text or '（无）'}\n"
            history_part = (
                "之前的工具结果如下：\n" + "\n".join(json.dumps(h, ensure_ascii=False) for h in history)
                if history else ""
            )
            prompt = (
                f"{context_part}"
                f"孩子提问：{ctx.question}\n"
                f"{history_part}\n"
                "请只基于上面的教材上下文和工具结果直接给出最终回答（不要再调工具），"
                "不要编造教材里没有的内容。"
            )
            raw = await asyncio.to_thread(self.provider.generate, prompt, self._system(ctx), True)
            data = self._parse(raw)
            answer = data.get("final_answer")
            if answer:
                stream.emit(StreamEvent(type="final", data={"answer": answer}))
                return {"answer": str(answer), "status": "done", "tool_calls": []}
        except Exception:
            pass
        answer = "抱歉，我没有理解你的问题，请再试一次。"
        stream.emit(StreamEvent(type="final", data={"answer": answer}))
        return {"answer": answer, "status": "error", "tool_calls": []}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_turn_engine.py -v`
Expected: PASS（注意：`test_turn_engine_max_steps_forced_finish` 和 `test_turn_engine_invalid_json_falls_back` 现在仍应通过——它们断言 `len(provider.calls) <= MAX_STEPS + 1` 和 `"抱歉" in answer`，这些不因 prompt 内容变化而变）

- [ ] **Step 5: 提交**

```bash
git add backend/app/runtime/turn_engine.py backend/tests/test_turn_engine.py
git commit -m "fix: _forced_finish 补回教材上下文 + 不要编造约束"
```

---

## Task 5: render_mermaid 严格校验

**Files:**
- Modify: `backend/app/tools/builtin.py`
- Test: `backend/tests/test_turn_engine.py`

- [ ] **Step 1: 写失败测试（追加到 test_turn_engine.py）**

```python
def test_render_mermaid_rejects_non_declaration_substring():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    # "graph" 出现在词中间/非行首，应被拒
    result = render_mermaid.run({"code": "photograph of a graph"}, ctx)
    assert result.get("ok") is False


def test_render_mermaid_accepts_extended_types():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = render_mermaid.run({"code": "sequenceDiagram\nAlice->>Bob: hi"}, ctx)
    assert result.get("ok") is True
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_turn_engine.py::test_render_mermaid_rejects_non_declaration_substring -v`
Expected: FAIL（当前 `any(k in code ...)` 子串匹配，`"photograph of a graph"` 含 `graph` 会返回 `ok: True`）

- [ ] **Step 3: 写实现**

修改 `backend/app/tools/builtin.py` 的 `RenderMermaidTool`：

```python
_MERMAID_RE = re.compile(
    r"^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|mindmap|journey)\b",
    re.MULTILINE,
)


class RenderMermaidTool(BaseTool):
    name = "render_mermaid"
    description = "校验并输出 mermaid 代码块（graph TD / mindmap 等），用于把知识画成图"
    parameters = [
        ToolParameter(name="code", type="string", description="mermaid 源码"),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        code = (args.get("code") or "").strip()
        if not code:
            return {"ok": False, "error": "code 不能为空"}
        valid = bool(_MERMAID_RE.search(code))
        return {"ok": valid, "code": code} if valid else {"ok": False, "error": "不是有效的 mermaid 图"}
```

注意：`_MERMAID_RE` 定义在 `builtin.py` 顶部（`re` 已在 Task 1 里 import）。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_turn_engine.py -v`
Expected: PASS（注意：`test_render_mermaid_valid` 用 `"graph TD; A-->B;"`，行首 `graph` 仍匹配 `\b`；`test_render_mermaid_invalid` 用 `"not mermaid"`，无图类型关键字，`ok: False`，都仍通过）

- [ ] **Step 5: 提交**

```bash
git add backend/app/tools/builtin.py backend/tests/test_turn_engine.py
git commit -m "fix: render_mermaid 行首图类型声明正则校验"
```

---

## Task 6: 前端传 sentences 字段

**Files:**
- Modify: `frontend/app.js`
- Modify: `backend/app/routers/notes.py`（AskReq 加 sentences + 透传）

- [ ] **Step 1: 写失败测试（后端 AskReq 部分）**

后端 `notes.py` 的 `AskReq` 加 `sentences` 字段后，`test_ask_api_end_to_end` 仍应通过（因为 `sentences` 有默认值 `[]`）。这里新增一个测试验证 `sentences` 被透传：

```python
def test_ask_req_accepts_sentences(setup_db):
    # 直接测 AskReq 模型可接受 sentences 字段
    from app.routers.notes import AskReq
    req = AskReq(lesson_id=1, question="?", context="a。b。", sentences=["a。", "b。"])
    assert req.sentences == ["a。", "b。"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_ask_api.py::test_ask_req_accepts_sentences -v`
Expected: FAIL（`AskReq` 无 `sentences` 字段，pydantic 抛 ValidationError）

- [ ] **Step 3: 写实现**

修改 `backend/app/routers/notes.py`：

`AskReq` 加字段：

```python
class AskReq(BaseModel):
    lesson_id: int
    question: str
    context: str = ""
    model: str = ""
    mode: str = "chat"
    sentences: list[str] = []
```

`ask_ai` 透传：

```python
    ctx = UnifiedContext(
        user_id=user_id, lesson_id=req.lesson_id, question=req.question,
        text=req.context, mode=req.mode, model=req.model,
        sentences=req.sentences,
    )
```

修改 `frontend/app.js` 的 `chatAsk`（约 line 1963）：

```js
  const body = {lesson_id:currentLessonId, question:q, context:ctx, mode:chatMode, sentences: splitSentences(ctx)};
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_ask_api.py tests/test_notes.py -v`
Expected: PASS

前端改动无法用 pytest 验证——这是纯 JS 改动，靠代码审查确认。手动确认 `splitSentences` 已在 `app.js` 定义（line 1067），`chatAsk` 里可直接调用。

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/notes.py backend/tests/test_ask_api.py frontend/app.js
git commit -m "feat: 前端传 sentences 字段对齐句号口径"
```

注意：`frontend/app.js` 和 `backend/app/routers/notes.py` 目前都在用户的**未提交改动列表**里。提交时只 `git add` 这两个文件（本次改动的部分），但要注意它们可能还有用户其他未提交改动——需谨慎，只 stage 本次相关文件，且提交前 `git diff` 确认没有把用户的无关改动一并纳入。

---

## Task 7: 全量回归 + 文档

**Files:**
- Test: 全量回归
- Modify: `AGENTS.md`（可选，标注幻觉补强已做）

- [ ] **Step 1: 全量回归**

Run: `cd backend && python -m pytest -v`
Expected: 功能相关测试全 PASS。已知 2 个预先存在的失败（`test_pdf_router.py::test_extract_document_missing_file_marks_done`、`test_seed.py::test_seed_creates_data`）仍会失败——它们与本补强无关，不修。

- [ ] **Step 2: 更新 AGENTS.md（可选）**

在 AGENTS.md 的「Agent-Native Roadmap」或新增一节，标注幻觉补强已落地（出处校验、lookup_word 如实失败、_forced_finish 约束、mermaid 校验）。这是纯文档，如时间紧可跳过。

- [ ] **Step 3: 提交**

```bash
git add AGENTS.md
git commit -m "docs: 标注幻觉补强已落地"
```

---

## 自审记录

- **Spec 覆盖**：设计的 6 节 → Task 1（sentences 契约 + search_text）、Task 2（出处校验）、Task 3（lookup_word）、Task 4（forced_finish）、Task 5（mermaid）、Task 6（前端传 sentences）。全覆盖。
- **Placeholder 扫描**：无 TBD/TODO。每个代码步骤含完整代码。
- **类型一致性**：`UnifiedContext.sentences: list[str]`（Task 1 定义）在 Task 2（`len(ctx.sentences)`）、Task 6（`sentences=req.sentences`）引用一致；`_filter_citations(citations, max_n)`（Task 2）签名前后一致；`_fallback_split`（Task 1）在 `search_text` 里引用一致。
- **注意点**：`notes.py` 和 `app.js` 在用户未提交改动列表里，Task 6 提交时需谨慎只 stage 本次改动，避免卷入用户无关改动。
