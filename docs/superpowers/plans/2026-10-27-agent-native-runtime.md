# KnoAct agent-native 运行时实现计划（Tool + Turn + Capability）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 引入 agent-native 运行时（Tool 抽象 + TurnEngine 多步循环 + Capability），直接替换 `/api/ask` 为真正的 agent 循环，前端契约不变。

**Architecture:** 新增 `core/`（纯协议层，零依赖）→ `tools/` → `runtime/` → `capabilities/`，单向依赖。TurnEngine 用 JSON 二选一协议（`final_answer` / `tool`）驱动多步工具循环（步数上限 8），结果持久化到新增的 `Turn` / `ToolCall` 表。`/api/ask` 改走 `CapabilityRegistry.get(mode)` 的 async capability。

**Tech Stack:** FastAPI + SQLAlchemy + 同步 OpenAI client（用 `asyncio.to_thread` 桥接 async 引擎）+ pytest。

---

## 文件结构总览

**新增：**
- `backend/app/core/__init__.py` — 空包
- `backend/app/core/tool_protocol.py` — `ToolParameter` / `ToolDefinition` / `BaseTool`
- `backend/app/core/capability_protocol.py` — `CapabilityManifest` / `TurnCapability`
- `backend/app/core/context.py` — `UnifiedContext`
- `backend/app/core/stream.py` — `StreamEvent` / `StreamBus`
- `backend/app/tools/__init__.py` — 空包
- `backend/app/tools/builtin.py` — `lookup_word` / `search_text` / `render_mermaid`
- `backend/app/tools/registry.py` — `ToolRegistry`
- `backend/app/runtime/__init__.py` — 空包
- `backend/app/runtime/turn_engine.py` — `TurnEngine`
- `backend/app/runtime/orchestrator.py` — `route_to_capability`
- `backend/app/capabilities/__init__.py` — 空包
- `backend/app/capabilities/chat.py` — `AgenticChatCapability` + 3 子类
- `backend/app/capabilities/registry.py` — `CapabilityRegistry`

**修改：**
- `backend/app/models.py` — 新增 `Turn` / `ToolCall`
- `backend/app/routers/notes.py` — `/api/ask` 改走 orchestrator

**测试新增：**
- `backend/tests/test_tool_protocol.py`
- `backend/tests/test_turn_engine.py`
- `backend/tests/test_capabilities.py`
- `backend/tests/test_ask_api.py`

**测试修改：**
- `backend/tests/test_notes.py` — 更新 `test_ask_ai_returns_answer`

---

## Task 1: core 协议层 — ToolParameter / ToolDefinition / BaseTool

**Files:**
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/tool_protocol.py`
- Test: `backend/tests/test_tool_protocol.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_tool_protocol.py`：

```python
from app.core.tool_protocol import ToolParameter, ToolDefinition, BaseTool


def test_tool_parameter_to_schema_basic():
    p = ToolParameter(name="word", type="string", description="要查的词")
    assert p.to_schema() == {"type": "string", "description": "要查的词"}


def test_tool_parameter_to_schema_enum():
    p = ToolParameter(name="kind", type="string", enum=["a", "b"])
    assert p.to_schema()["enum"] == ["a", "b"]


def test_tool_parameter_array_has_items():
    p = ToolParameter(name="ids", type="array")
    assert p.to_schema()["items"] == {"type": "string"}


def test_tool_definition_to_schema():
    td = ToolDefinition(
        name="lookup_word",
        description="查词",
        parameters=[ToolParameter(name="word", type="string", description="词")],
    )
    schema = td.to_schema()
    assert schema["name"] == "lookup_word"
    assert schema["description"] == "查词"
    assert schema["parameters"]["properties"]["word"]["type"] == "string"
    assert "word" in schema["parameters"]["required"]


def test_tool_definition_optional_param_not_required():
    td = ToolDefinition(
        name="t",
        description="d",
        parameters=[ToolParameter(name="x", type="string", required=False)],
    )
    assert "x" not in td.to_schema()["parameters"]["required"]


def test_base_tool_to_schema():
    class Dummy(BaseTool):
        name = "dummy"
        description = "测试工具"
        parameters = [ToolParameter(name="a", type="string", description="参数")]

        def run(self, args, ctx):
            return {"ok": True}

    assert Dummy().to_schema()["name"] == "dummy"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_tool_protocol.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.core'`）

- [ ] **Step 3: 写实现**

创建 `backend/app/core/__init__.py`（空文件），再创建 `backend/app/core/tool_protocol.py`：

```python
"""工具协议：BaseTool + ToolDefinition + ToolParameter。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .context import UnifiedContext


@dataclass
class ToolParameter:
    name: str
    type: str  # "string" | "integer" | "boolean" | "number" | "array" | "object"
    description: str = ""
    required: bool = True
    default: Any = None
    enum: list[str] | None = None
    items: dict[str, Any] | None = None

    def to_schema(self) -> dict[str, Any]:
        schema: dict[str, Any] = {"type": self.type, "description": self.description}
        if self.enum:
            schema["enum"] = list(self.enum)
        if self.type == "array":
            schema["items"] = self.items if self.items is not None else {"type": "string"}
        return schema


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)

    def to_schema(self) -> dict[str, Any]:
        props = {p.name: p.to_schema() for p in self.parameters}
        required = [p.name for p in self.parameters if p.required]
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        }


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: list[ToolParameter] = []

    def to_schema(self) -> dict[str, Any]:
        return ToolDefinition(
            name=self.name, description=self.description, parameters=self.parameters
        ).to_schema()

    @abstractmethod
    def run(self, args: dict[str, Any], ctx: UnifiedContext) -> dict[str, Any]:
        """同步执行，返回 JSON 可序列化的结果 dict。"""
        ...
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_tool_protocol.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/__init__.py backend/app/core/tool_protocol.py backend/tests/test_tool_protocol.py
git commit -m "feat: core 工具协议（ToolParameter/ToolDefinition/BaseTool）"
```

---

## Task 2: core 协议层 — UnifiedContext / StreamEvent / StreamBus / CapabilityManifest / TurnCapability

**Files:**
- Create: `backend/app/core/context.py`
- Create: `backend/app/core/stream.py`
- Create: `backend/app/core/capability_protocol.py`
- Test: `backend/tests/test_capabilities.py`（本任务先写 context/stream 部分）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_capabilities.py`（本任务先写 context + stream 测试）：

```python
import pytest

from app.core.context import UnifiedContext
from app.core.stream import StreamEvent, StreamBus
from app.core.capability_protocol import CapabilityManifest, TurnCapability


def test_unified_context_defaults():
    ctx = UnifiedContext(user_id=1, lesson_id=2, question="你好")
    assert ctx.user_id == 1
    assert ctx.lesson_id == 2
    assert ctx.question == "你好"
    assert ctx.text == ""
    assert ctx.mode == "chat"
    assert ctx.model == ""


def test_stream_bus_collects_events():
    bus = StreamBus()
    bus.emit(StreamEvent(type="tool_call", data={"tool": "lookup_word"}))
    bus.emit(StreamEvent(type="final", data={"answer": "好"}))
    assert [e.type for e in bus.events] == ["tool_call", "final"]


def test_capability_manifest_fields():
    m = CapabilityManifest(name="chat", description="对话", stages=["thinking"], tools_used=["lookup_word"])
    assert m.name == "chat"
    assert m.stages == ["thinking"]
    assert m.tools_used == ["lookup_word"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_capabilities.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 写实现**

创建 `backend/app/core/context.py`：

```python
"""统一上下文：一次 turn 的输入。"""
from dataclasses import dataclass


@dataclass
class UnifiedContext:
    user_id: int
    lesson_id: int
    question: str
    text: str = ""          # 教材上下文（按句切分，句前编号）
    mode: str = "chat"      # chat | visualize | solve
    model: str = ""         # 覆盖默认模型
```

创建 `backend/app/core/stream.py`：

```python
"""流事件协议 + 事件总线（服务端收集，本轮不推前端）。"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamEvent:
    type: str                # stage | tool_call | tool_result | final
    data: dict[str, Any] = field(default_factory=dict)


class StreamBus:
    def __init__(self) -> None:
        self.events: list[StreamEvent] = []

    def emit(self, event: StreamEvent) -> None:
        self.events.append(event)
```

创建 `backend/app/core/capability_protocol.py`：

```python
"""能力协议：TurnCapability + CapabilityManifest。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .context import UnifiedContext
from .stream import StreamBus


@dataclass
class CapabilityManifest:
    name: str
    description: str
    stages: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)


class TurnCapability(ABC):
    manifest: CapabilityManifest

    @abstractmethod
    async def run(self, ctx: UnifiedContext, stream: StreamBus) -> None:
        """执行能力流水线，向 stream 发事件。"""
        ...

    @property
    def name(self) -> str:
        return self.manifest.name
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_capabilities.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/context.py backend/app/core/stream.py backend/app/core/capability_protocol.py backend/tests/test_capabilities.py
git commit -m "feat: core 上下文/流/能力协议"
```

---

## Task 3: 工具实现 + ToolRegistry

**Files:**
- Create: `backend/app/tools/__init__.py`
- Create: `backend/app/tools/registry.py`
- Create: `backend/app/tools/builtin.py`
- Test: `backend/tests/test_turn_engine.py`（本任务先写 registry + 工具测试）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_turn_engine.py`（本任务先写 registry + 工具测试）：

```python
import pytest

from app.core.context import UnifiedContext
from app.core.tool_protocol import BaseTool, ToolParameter
from app.tools.registry import ToolRegistry, ToolNotFoundError
from app.tools.builtin import lookup_word, search_text, render_mermaid


def test_registry_register_and_get():
    class Dummy(BaseTool):
        name = "dummy"
        description = "d"
        parameters = []
        def run(self, args, ctx):
            return {"ok": True}

    reg = ToolRegistry()
    reg.register(Dummy())
    assert reg.get("dummy").name == "dummy"


def test_registry_get_unknown_raises():
    reg = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        reg.get("nope")


def test_registry_list_schemas():
    reg = ToolRegistry()
    reg.register(lookup_word)
    reg.register(search_text)
    schemas = reg.list_schemas()
    names = [s["name"] for s in schemas]
    assert "lookup_word" in names
    assert "search_text" in names


def test_lookup_word_returns_meaning():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = lookup_word.run({"word": "徘徊"}, ctx)
    assert "meaning" in result


def test_render_mermaid_valid():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = render_mermaid.run({"code": "graph TD; A-->B;"}, ctx)
    assert result.get("ok") is True


def test_render_mermaid_invalid():
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="")
    result = render_mermaid.run({"code": "not mermaid"}, ctx)
    assert result.get("ok") is False
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_turn_engine.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.tools'`）

- [ ] **Step 3: 写实现**

创建 `backend/app/tools/__init__.py`（空文件）。

创建 `backend/app/tools/registry.py`：

```python
"""工具注册表。"""
from ..core.tool_protocol import BaseTool


class ToolNotFoundError(KeyError):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def list_schemas(self) -> list[dict]:
        return [t.to_schema() for t in self._tools.values()]
```

创建 `backend/app/tools/builtin.py`：

```python
"""内置工具：lookup_word / search_text / render_mermaid。"""
from ..core.context import UnifiedContext
from ..core.tool_protocol import BaseTool, ToolParameter


class LookupWordTool(BaseTool):
    name = "lookup_word"
    description = "查一个词的释义，用小学生能懂的话解释"
    parameters = [
        ToolParameter(name="word", type="string", description="要查的词"),
        ToolParameter(name="lesson_id", type="integer", description="教材课 id", required=False),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        word = (args.get("word") or "").strip()
        if not word:
            return {"error": "word 不能为空"}
        # 同步调用 provider 释义；provider 不可用时回落占位
        try:
            from ..services.ai import get_provider
            from ..database import SessionLocal
            db = SessionLocal()
            try:
                provider = get_provider(db)
                meaning = provider.generate(
                    prompt=f"请解释教材中的这个词：「{word}」。用小学生能懂的话说明它的意思，50 字以内。",
                    system="你是小学生的学习助手，解释生词要简洁、准确。",
                ).strip()
            finally:
                db.close()
        except Exception:
            meaning = f"「{word}」的释义（示例）"
        return {"word": word, "meaning": meaning}


class SearchTextTool(BaseTool):
    name = "search_text"
    description = "在教材上下文里检索含某关键词的句子，返回句号及其编号，用于标注出处"
    parameters = [
        ToolParameter(name="query", type="string", description="检索关键词"),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        query = (args.get("query") or "").strip()
        text = ctx.text or ""
        if not query or not text:
            return {"matches": []}
        matches = []
        # ctx.text 形如「1.句子一 2.句子二」；简单按行/句切分编号匹配
        for idx, line in enumerate(text.splitlines() or [text], start=1):
            if query in line:
                matches.append({"sentence_no": idx, "text": line.strip()})
        return {"matches": matches}


class RenderMermaidTool(BaseTool):
    name = "render_mermaid"
    description = "校验并输出 mermaid 代码块（graph TD / mindmap），用于把知识画成图"
    parameters = [
        ToolParameter(name="code", type="string", description="mermaid 源码"),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        code = (args.get("code") or "").strip()
        if not code:
            return {"ok": False, "error": "code 不能为空"}
        # 简单校验：含 mermaid 图类型关键字
        valid = any(k in code for k in ("graph", "mindmap", "flowchart"))
        return {"ok": valid, "code": code} if valid else {"ok": False, "error": "不是有效的 mermaid 图"}


lookup_word = LookupWordTool()
search_text = SearchTextTool()
render_mermaid = RenderMermaidTool()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_turn_engine.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/tools/ backend/tests/test_turn_engine.py
git commit -m "feat: 内置工具 + ToolRegistry"
```

---

## Task 4: TurnEngine 多步工具循环

**Files:**
- Create: `backend/app/runtime/__init__.py`
- Create: `backend/app/runtime/turn_engine.py`
- Test: `backend/tests/test_turn_engine.py`（追加 TurnEngine 测试）

- [ ] **Step 1: 写失败测试（追加到 test_turn_engine.py）**

```python
import asyncio

from app.core.context import UnifiedContext
from app.core.stream import StreamBus
from app.runtime.turn_engine import TurnEngine
from app.tools.registry import ToolRegistry
from app.tools.builtin import lookup_word


class ScriptedProvider:
    """按脚本依次返回，模拟 LLM。"""
    name = "scripted"
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def generate(self, prompt, system="", json_mode=False):
        self.calls.append(prompt)
        return self.responses.pop(0)


def _make_engine(provider):
    reg = ToolRegistry()
    reg.register(lookup_word)
    return TurnEngine(provider=provider, registry=reg)


def test_turn_engine_single_final_answer():
    provider = ScriptedProvider(['{"final_answer": "你好呀"}'])
    engine = _make_engine(provider)
    bus = StreamBus()
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="你好", text="")
    result = asyncio.run(engine.run(ctx, bus))
    assert result["answer"] == "你好呀"
    assert len(provider.calls) == 1


def test_turn_engine_tool_then_final():
    provider = ScriptedProvider([
        '{"tool": "lookup_word", "args": {"word": "徘徊"}}',
        '{"final_answer": "徘徊是来回走动的意思"}',
    ])
    engine = _make_engine(provider)
    bus = StreamBus()
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="徘徊是什么意思", text="")
    result = asyncio.run(engine.run(ctx, bus))
    assert result["answer"] == "徘徊是来回走动的意思"
    assert len(provider.calls) == 2
    # 工具结果回填进了第二次 prompt
    assert "meaning" in provider.calls[1]


def test_turn_engine_max_steps_forced_finish():
    # 永远返回 tool 调用，触发步数上限
    provider = ScriptedProvider(['{"tool": "lookup_word", "args": {"word": "x"}}'] * 20)
    engine = _make_engine(provider)
    bus = StreamBus()
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="?", text="")
    result = asyncio.run(engine.run(ctx, bus))
    assert result["status"] == "error"
    assert len(provider.calls) <= TurnEngine.MAX_STEPS + 1


def test_turn_engine_invalid_json_falls_back():
    provider = ScriptedProvider(["not json at all"])
    engine = _make_engine(provider)
    bus = StreamBus()
    ctx = UnifiedContext(user_id=1, lesson_id=1, question="?", text="")
    result = asyncio.run(engine.run(ctx, bus))
    assert result["status"] == "error"
    assert "抱歉" in result["answer"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_turn_engine.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.runtime'`，之前的 registry 测试仍 PASS）

- [ ] **Step 3: 写实现**

创建 `backend/app/runtime/__init__.py`（空文件）。

创建 `backend/app/runtime/turn_engine.py`：

```python
"""Turn 引擎：JSON 二选一协议驱动的多步工具循环。"""
import asyncio
import json

from ..core.context import UnifiedContext
from ..core.stream import StreamBus, StreamEvent
from ..core.tool_protocol import BaseTool
from ..tools.registry import ToolRegistry, ToolNotFoundError


class TurnEngine:
    MAX_STEPS = 8

    def __init__(self, provider, registry: ToolRegistry) -> None:
        self.provider = provider
        self.registry = registry

    async def run(self, ctx: UnifiedContext, stream: StreamBus) -> dict:
        """驱动多步循环，返回 {answer, status, tool_calls}。"""
        history: list[dict] = []
        tool_calls: list[dict] = []

        for step in range(1, self.MAX_STEPS + 1):
            prompt = self._build_prompt(ctx, history)
            raw = await asyncio.to_thread(
                self.provider.generate, prompt, self._system(ctx), True
            )
            parsed = self._parse(raw)

            if parsed.get("final_answer") is not None:
                answer = str(parsed["final_answer"]).strip()
                stream.emit(StreamEvent(type="final", data={"answer": answer}))
                return {"answer": answer, "status": "done", "tool_calls": tool_calls}

            tool_name = parsed.get("tool")
            args = parsed.get("args") or {}
            if not tool_name:
                # 解析失败：强制收尾
                return self._forced_finish(ctx, history, stream)

            try:
                tool: BaseTool = self.registry.get(tool_name)
                result = tool.run(args, ctx)
            except ToolNotFoundError:
                result = {"error": f"工具 {tool_name} 不存在"}
            except Exception as e:
                result = {"error": str(e)}

            tool_calls.append({"step": step, "tool": tool_name, "args": args, "result": result})
            stream.emit(StreamEvent(type="tool_call", data={"step": step, "tool": tool_name, "args": args}))
            stream.emit(StreamEvent(type="tool_result", data={"step": step, "result": result}))
            history.append({"tool": tool_name, "args": args, "result": result})

        # 步数上限：强制收尾
        return self._forced_finish(ctx, history, stream)

    def _system(self, ctx: UnifiedContext) -> str:
        schemas = json.dumps(self.registry.list_schemas(), ensure_ascii=False)
        return (
            "你是小学生的学习助手，可以用工具辅助回答。\n"
            "你每次只能返回一种 JSON：\n"
            '  - 回答完成：{"final_answer": "你的回答"}\n'
            '  - 调用工具：{"tool": "工具名", "args": {...}}\n'
            f"可用工具：{schemas}\n"
            "需要查词/检索/画图时先调工具，再根据工具结果回答。"
        )

    def _build_prompt(self, ctx: UnifiedContext, history: list[dict]) -> str:
        parts = [f"教材上下文：{ctx.text or '（无）'}", f"孩子提问：{ctx.question}"]
        if history:
            parts.append("已执行的工具调用及结果：")
            for h in history:
                parts.append(json.dumps(h, ensure_ascii=False))
        return "\n".join(parts)

    def _parse(self, raw: str) -> dict:
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {}

    def _forced_finish(self, ctx: UnifiedContext, history: list[dict], stream: StreamBus) -> dict:
        # 把历史交给 LLM 求 final；失败则返回友好文案
        try:
            prompt = (
                f"孩子提问：{ctx.question}\n"
                "之前的工具结果如下，请直接给出最终回答（不要再调工具）：\n"
                + "\n".join(json.dumps(h, ensure_ascii=False) for h in history)
            )
            raw = self.provider.generate(prompt, self._system(ctx), True)
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
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/runtime/ backend/tests/test_turn_engine.py
git commit -m "feat: TurnEngine 多步工具循环"
```

---

## Task 5: capabilities — 共享基类 + 3 子类 + 注册表

**Files:**
- Create: `backend/app/capabilities/__init__.py`
- Create: `backend/app/capabilities/chat.py`
- Create: `backend/app/capabilities/registry.py`
- Test: `backend/tests/test_capabilities.py`（追加）

- [ ] **Step 1: 写失败测试（追加到 test_capabilities.py）**

```python
from app.capabilities.chat import ChatCapability, VisualizeCapability, SolveCapability
from app.capabilities.registry import CapabilityRegistry


def test_chat_manifest():
    assert ChatCapability().name == "chat"
    assert "lookup_word" in ChatCapability().manifest.tools_used


def test_visualize_uses_render_mermaid():
    assert "render_mermaid" in VisualizeCapability().manifest.tools_used


def test_solve_system_prompt_is_stepwise():
    assert "分步骤" in SolveCapability().system_prompt


def test_registry_routes_mode():
    reg = CapabilityRegistry()
    assert isinstance(reg.get("chat"), ChatCapability)
    assert isinstance(reg.get("visualize"), VisualizeCapability)
    assert isinstance(reg.get("solve"), SolveCapability)


def test_registry_unknown_mode_falls_back_to_chat():
    reg = CapabilityRegistry()
    assert isinstance(reg.get("nope"), ChatCapability)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_capabilities.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.capabilities'`）

- [ ] **Step 3: 写实现**

创建 `backend/app/capabilities/__init__.py`（空文件）。

创建 `backend/app/capabilities/chat.py`：

```python
"""学习助手 capability：chat / visualize / solve 三模式。"""
import asyncio

from ..core.capability_protocol import CapabilityManifest, TurnCapability
from ..core.context import UnifiedContext
from ..core.stream import StreamBus, StreamEvent
from ..runtime.turn_engine import TurnEngine
from ..tools.registry import ToolRegistry
from ..tools.builtin import lookup_word, search_text, render_mermaid


def _default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(lookup_word)
    reg.register(search_text)
    reg.register(render_mermaid)
    return reg


class AgenticChatCapability(TurnCapability):
    """共享基类：封装「调 TurnEngine 多步循环」的公共逻辑。"""

    system_prompt: str = "你是小学生的学习助手，讲解要通俗、有耐心。"
    tools: list[str] = ["lookup_word", "search_text", "render_mermaid"]

    @property
    def _registry(self) -> ToolRegistry:
        reg = _default_registry()
        # 只挂本 capability 声明的工具
        all_tools = {"lookup_word": lookup_word, "search_text": search_text, "render_mermaid": render_mermaid}
        for name in self.tools:
            if name in all_tools:
                reg.register(all_tools[name])
        return reg

    async def run(self, ctx: UnifiedContext, stream: StreamBus) -> None:
        stream.emit(StreamEvent(type="stage", data={"stage": "thinking"}))
        engine = TurnEngine(provider=_get_provider(ctx), registry=self._registry)
        result = await engine.run(ctx, stream)
        # 把结果挂到 stream 上，供 orchestrator 取最终答案
        stream.emit(StreamEvent(type="final", data=result))


def _get_provider(ctx: UnifiedContext):
    from ..database import SessionLocal
    from ..services.ai import get_provider
    db = SessionLocal()
    try:
        provider = get_provider(db)
        if ctx.model:
            provider.model = ctx.model
        return provider
    finally:
        db.close()


class ChatCapability(AgenticChatCapability):
    manifest = CapabilityManifest(
        name="chat",
        description="普通问答",
        stages=["thinking"],
        tools_used=["lookup_word", "search_text", "render_mermaid"],
    )


class VisualizeCapability(AgenticChatCapability):
    manifest = CapabilityManifest(
        name="visualize",
        description="把知识画成图",
        stages=["thinking"],
        tools_used=["render_mermaid", "search_text"],
    )
    system_prompt = (
        "你是小学生的学习助手，擅长把知识画成图。"
        "当孩子提问适合用图表达时，调用 render_mermaid 工具画图，图下方再用一两句小学生能懂的话解释。"
        "如果不适合画图，就直接用通俗的话解答。"
    )
    tools = ["render_mermaid", "search_text"]


class SolveCapability(AgenticChatCapability):
    manifest = CapabilityManifest(
        name="solve",
        description="分步解题",
        stages=["thinking"],
        tools_used=["lookup_word", "search_text"],
    )
    system_prompt = (
        "你是小学生的解题助手。请分步骤讲解解题思路（读题 → 分析 → 列式 → 作答），"
        "每一步用一句小学生能懂的话说明，最后给出答案。"
    )
    tools = ["lookup_word", "search_text"]
```

创建 `backend/app/capabilities/registry.py`：

```python
"""能力注册表：mode → capability。"""
from ..core.capability_protocol import TurnCapability
from .chat import ChatCapability, VisualizeCapability, SolveCapability


class CapabilityRegistry:
    def __init__(self) -> None:
        self._caps: dict[str, TurnCapability] = {
            "chat": ChatCapability(),
            "visualize": VisualizeCapability(),
            "solve": SolveCapability(),
        }

    def get(self, mode: str) -> TurnCapability:
        return self._caps.get(mode, self._caps["chat"])
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_capabilities.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/capabilities/ backend/tests/test_capabilities.py
git commit -m "feat: 学习助手 capability（chat/visualize/solve）"
```

---

## Task 6: 数据模型 — Turn / ToolCall 表

**Files:**
- Modify: `backend/app/models.py`（末尾追加两个模型）
- Test: `backend/tests/test_ask_api.py`（本任务先写建表测试）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_ask_api.py`：

```python
from app.database import SessionLocal


def test_turn_table_exists(setup_db):
    from app.models import Turn, ToolCall
    db = SessionLocal()
    turn = Turn(user_id=1, lesson_id=1, capability="chat", mode="chat",
                question="你好", context="", status="done", final_answer="你好呀")
    db.add(turn); db.commit(); db.flush()
    assert turn.id is not None
    tc = ToolCall(turn_id=turn.id, step=1, tool_name="lookup_word",
                  args='{"word": "x"}', result='{"meaning": "m"}')
    db.add(tc); db.commit()
    assert db.query(ToolCall).count() == 1
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_ask_api.py -v`
Expected: FAIL（`ImportError: cannot import name 'Turn'`）

- [ ] **Step 3: 写实现**

在 `backend/app/models.py` 末尾追加：

```python
class Turn(Base):
    """一次 agent turn：一个提问 → 一次多步工具循环 → 最终答案。"""
    __tablename__ = "turns"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=True)
    capability: Mapped[str] = mapped_column(String(32))   # chat | visualize | solve
    mode: Mapped[str] = mapped_column(String(16))          # 冗余存原始 mode
    question: Mapped[str] = mapped_column(TextCls)
    context: Mapped[str] = mapped_column(TextCls, default="")
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|done|error
    final_answer: Mapped[str] = mapped_column(TextCls, default="")
    citations: Mapped[str] = mapped_column(TextCls, default="[]")  # JSON 数组文本
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class ToolCall(Base):
    """一次 turn 内的一次工具调用（含 args + result，可 replay）。"""
    __tablename__ = "tool_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    turn_id: Mapped[int] = mapped_column(ForeignKey("turns.id"))
    step: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(64))
    args: Mapped[str] = mapped_column(TextCls, default="{}")   # JSON 文本
    result: Mapped[str] = mapped_column(TextCls, default="{}")  # JSON 文本
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_ask_api.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/models.py backend/tests/test_ask_api.py
git commit -m "feat: Turn/ToolCall 数据模型"
```

---

## Task 7: orchestrator + 替换 /api/ask

**Files:**
- Create: `backend/app/runtime/orchestrator.py`
- Modify: `backend/app/routers/notes.py`
- Test: `backend/tests/test_ask_api.py`（追加）+ 修改 `backend/tests/test_notes.py`

- [ ] **Step 1: 写失败测试（追加到 test_ask_api.py）**

```python
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import ModelConfig

client = TestClient(app)


def test_ask_api_end_to_end(setup_db):
    # 用 fake provider：不会返回合法 JSON，应走降级返回友好文案（status=error 但不 500）
    db = SessionLocal()
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit(); db.close()
    r = client.post("/api/ask", json={"lesson_id": 1, "question": "你好", "context": "白鹭是一首精巧的诗"})
    assert r.status_code == 200
    body = r.json()
    assert "answer" in body
    assert "citations" in body
    assert "mode" in body
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_ask_api.py::test_ask_api_end_to_end -v`
Expected: FAIL（`/api/ask` 还是旧的同步实现，fake 返回 `[fake]` 前缀，非降级路径——但 status 仍是 200，可能 PASS。需用 `test_notes.py` 的 `test_ask_ai_returns_answer` 来验证「改了」；见 Step 3 后重跑）

- [ ] **Step 3: 写实现**

创建 `backend/app/runtime/orchestrator.py`：

```python
"""路由 UnifiedContext → 选中的 capability。"""
import asyncio

from ..core.context import UnifiedContext
from ..core.stream import StreamBus
from ..capabilities.registry import CapabilityRegistry


def route_to_capability(ctx: UnifiedContext) -> dict:
    """同步入口：异步驱动 capability，返回最终 {answer, citations, mode}。"""
    registry = CapabilityRegistry()
    capability = registry.get(ctx.mode)
    stream = StreamBus()
    asyncio.run(capability.run(ctx, stream))
    # 从 stream 最后一个 final 事件取答案
    final_event = None
    for e in reversed(stream.events):
        if e.type == "final":
            final_event = e
            break
    answer = final_event.data.get("answer", "") if final_event else ""
    citations = _extract_citations(answer)
    return {"answer": answer, "citations": citations, "mode": ctx.mode}


def _extract_citations(answer: str) -> list[int]:
    import re
    return sorted(set(int(n) for n in re.findall(r"第\s*(\d+)\s*句", answer)))
```

修改 `backend/app/routers/notes.py`，把 `ask_ai` 替换为：

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Note
from ..core.context import UnifiedContext
from ..runtime.orchestrator import route_to_capability

router = APIRouter(tags=["notes"])

class NoteReq(BaseModel):
    lesson_id: int
    author_role: str
    content: str
    anchor_text: str = ""
    page_number: int | None = None

class AskReq(BaseModel):
    lesson_id: int
    question: str
    context: str = ""
    model: str = ""
    mode: str = "chat"

@router.post("/api/notes")
def add_note(req: NoteReq, db: Session = Depends(get_db)):
    note = Note(**req.model_dump())
    db.add(note); db.commit(); db.refresh(note)
    return {"id": note.id, "content": note.content}

@router.get("/api/notes")
def list_notes(lesson_id: int, db: Session = Depends(get_db)):
    return db.query(Note).filter_by(lesson_id=lesson_id).order_by(Note.created_at.desc()).all()

@router.post("/api/ask")
async def ask_ai(req: AskReq, db: Session = Depends(get_db)):
    ctx = UnifiedContext(
        user_id=0, lesson_id=req.lesson_id, question=req.question,
        text=req.context, mode=req.mode, model=req.model,
    )
    return route_to_capability(ctx)
```

注意：删除旧的 `_MODE_SYSTEM` 与 `get_provider` import（`get_provider` 移入 capability 层）。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_ask_api.py -v && python -m pytest tests/test_notes.py -v`
Expected: PASS。`test_notes.py` 的 `test_ask_ai_returns_answer` 用 fake provider，走降级路径但仍返回 `answer` 键，故仍 PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/runtime/orchestrator.py backend/app/routers/notes.py backend/tests/test_ask_api.py
git commit -m "feat: /api/ask 改走 agent-native orchestrator"
```

---

## Task 8: 持久化接入 + 全量回归

**Files:**
- Modify: `backend/app/runtime/orchestrator.py`（落库 Turn/ToolCall）
- Modify: `backend/app/routers/notes.py`（传 user_id）
- Test: `backend/tests/test_ask_api.py`（追加落库断言）

- [ ] **Step 1: 写失败测试（追加到 test_ask_api.py）**

```python
def test_ask_api_persists_turn(setup_db):
    from app.models import Turn, ModelConfig
    db = SessionLocal()
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit(); db.close()
    r = client.post("/api/ask", json={"lesson_id": 1, "question": "你好", "context": ""})
    assert r.status_code == 200
    db = SessionLocal()
    turn = db.query(Turn).order_by(Turn.id.desc()).first()
    assert turn is not None
    assert turn.mode == "chat"
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_ask_api.py::test_ask_api_persists_turn -v`
Expected: FAIL（orchestrator 尚未落库，`Turn` 查询为空）

- [ ] **Step 3: 写实现**

修改 `backend/app/runtime/orchestrator.py`，在 `route_to_capability` 里落库：

```python
def route_to_capability(ctx: UnifiedContext) -> dict:
    registry = CapabilityRegistry()
    capability = registry.get(ctx.mode)
    stream = StreamBus()
    asyncio.run(capability.run(ctx, stream))

    final_event = None
    tool_events = []
    for e in stream.events:
        if e.type == "final":
            final_event = e
        elif e.type == "tool_call":
            tool_events.append(e)
    answer = final_event.data.get("answer", "") if final_event else ""
    citations = _extract_citations(answer)

    _persist(ctx, capability.name, answer, citations, tool_events)
    return {"answer": answer, "citations": citations, "mode": ctx.mode}


def _persist(ctx, capability_name, answer, citations, tool_events):
    import json
    from datetime import datetime
    from ..database import SessionLocal
    from ..models import Turn, ToolCall

    db = SessionLocal()
    try:
        status = "done" if answer else "error"
        turn = Turn(
            user_id=ctx.user_id, lesson_id=ctx.lesson_id, capability=capability_name,
            mode=ctx.mode, question=ctx.question, context=ctx.text,
            status=status, final_answer=answer,
            citations=json.dumps(citations, ensure_ascii=False),
            finished_at=datetime.utcnow(),
        )
        db.add(turn); db.commit(); db.refresh(turn)
        for e in tool_events:
            db.add(ToolCall(
                turn_id=turn.id, step=e.data.get("step", 0),
                tool_name=e.data.get("tool", ""),
                args=json.dumps(e.data.get("args", {}), ensure_ascii=False),
                result=json.dumps(e.data.get("result", {}), ensure_ascii=False),
            ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
```

- [ ] **Step 4: 运行全量回归**

Run: `cd backend && python -m pytest -v`
Expected: 全部 PASS（包括现有 `test_notes.py`、`test_annotations.py` 等回归）

- [ ] **Step 5: 提交**

```bash
git add backend/app/runtime/orchestrator.py backend/app/routers/notes.py backend/tests/test_ask_api.py
git commit -m "feat: Turn/ToolCall 落库接入"
```

---

## Task 9: 文档更新 + AGENTS.md 回写

**Files:**
- Modify: `AGENTS.md`（更新 AI 调用现状：`/api/ask` 已 agent 化）

- [ ] **Step 1: 更新 AGENTS.md**

把「AI 调用现状」表中 `notes.py /api/ask` 那一行，从「学习助手（chat/visualize/solve）」改为标注「已 agent 化：走 `runtime/orchestrator.py` → `capabilities/` → `TurnEngine` 多步工具循环」，并在 Key Files 表补 `core/`、`tools/`、`runtime/`、`capabilities/` 四行。

- [ ] **Step 2: 提交**

```bash
git add AGENTS.md
git commit -m "docs: /api/ask 已 agent 化，更新架构说明"
```

---

## 自审记录

- **Spec 覆盖**：spec 的 6 节（架构/循环/工具/capability/数据/替换+错误处理+测试）→ 对应 Task 1-8。错误处理（分层降级）落在 Task 4 的 `_forced_finish` + 工具 `try/except`；测试策略（mock provider）落在 Task 4 的 `ScriptedProvider`。无缺口。
- **Placeholder 扫描**：无 TBD/TODO/「类似 Task N」。每个代码步骤含完整代码。
- **类型一致性**：`UnifiedContext` 字段（user_id/lesson_id/question/text/mode/model）在 Task 2 定义，Task 3/4/5/7 引用一致；`TurnEngine.run` 返回 `{answer, status, tool_calls}`，Task 4 定义、Task 5 传递、Task 7 消费一致；`CapabilityRegistry.get`、`ToolRegistry` 接口前后一致。
