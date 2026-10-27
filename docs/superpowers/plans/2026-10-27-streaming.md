# KnoAct 前端流式实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 引入 SSE 流式，把 `/api/ask` 的 capability 执行过程（stage/tool_call/tool_result/final 事件）实时推给前端，用户看到中间进度而非只等最终答案。

**Architecture:** StreamBus 加 asyncio.Queue 双通道（emit 同时 put 进队列）；新增 `/api/ask/stream` 用 `asyncio.create_task` 并发跑 capability + 读队列逐条 yield SSE；前端 `chatAsk` 改 `fetch` + `ReadableStream` 读流，`tool_call` 更新占位、`final` 渲染答案。落库复用 `_persist`。

**Tech Stack:** FastAPI StreamingResponse + asyncio.Queue；前端原生 JS fetch ReadableStream；pytest + TestClient。

---

## 文件结构总览

**修改：**
- `backend/app/core/stream.py` — StreamBus 加 `_queue` + `subscribe()`
- `backend/app/routers/notes.py` — 新增 `/api/ask/stream` 端点 + `_event_stream` + `_sse`
- `frontend/app.js` — `chatAsk` 改流式 + `thinkingText` 状态 + `updateThinking` + `handleStreamEvent` + `toolLabel`

**测试修改：**
- `backend/tests/test_ask_api.py` — 流式端点测试 + StreamBus subscribe 测试

---

## Task 1: StreamBus 加 Queue 订阅

**Files:**
- Modify: `backend/app/core/stream.py`
- Test: `backend/tests/test_ask_api.py`（或新建 test_stream.py）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_ask_api.py` 追加（或新建 `backend/tests/test_stream.py`，推荐后者保持清晰）：

```python
import asyncio
from app.core.stream import StreamEvent, StreamBus


def test_stream_bus_subscribe_receives_events():
    bus = StreamBus()
    q = bus.subscribe()
    bus.emit(StreamEvent(type="tool_call", data={"tool": "lookup_word"}))
    bus.emit(StreamEvent(type="final", data={"answer": "好"}))
    # events 列表保留
    assert len(bus.events) == 2
    # queue 也收到同样事件
    assert q.qsize() == 2
    e1 = asyncio.run(q.get())
    assert e1.type == "tool_call"
    e2 = asyncio.run(q.get())
    assert e2.type == "final"


def test_stream_bus_no_queue_without_subscribe():
    bus = StreamBus()
    bus.emit(StreamEvent(type="final", data={"answer": "好"}))
    # 未 subscribe 时，emit 不创建 queue（无副作用）
    assert bus._queue is None
    assert len(bus.events) == 1
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_stream.py -v`
Expected: FAIL（`StreamBus` 无 `subscribe` 方法、无 `_queue` 属性）

- [ ] **Step 3: 写实现**

修改 `backend/app/core/stream.py`：

```python
"""流事件协议 + 事件总线（同步收集 + 可选实时推送）。"""
import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamEvent:
    type: str                # stage | tool_call | tool_result | final
    data: dict[str, Any] = field(default_factory=dict)


class StreamBus:
    def __init__(self) -> None:
        self.events: list[StreamEvent] = []
        self._queue: asyncio.Queue | None = None   # 惰性创建，仅流式路径用

    def emit(self, event: StreamEvent) -> None:
        self.events.append(event)
        if self._queue is not None:
            self._queue.put_nowait(event)

    def subscribe(self) -> asyncio.Queue:
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_stream.py tests/test_turn_engine.py -v`
Expected: PASS（新 2 个 + 现有 turn_engine 全绿，因为 StreamBus 非流式用法不变）

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/stream.py backend/tests/test_stream.py
git commit -m "feat: StreamBus 加 asyncio.Queue 订阅推送"
```

---

## Task 2: `/api/ask/stream` 端点

**Files:**
- Modify: `backend/app/routers/notes.py`
- Test: `backend/tests/test_ask_api.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_ask_api.py` 追加：

```python
def test_ask_stream_endpoint(setup_db):
    from app.models import ModelConfig
    db = SessionLocal()
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit(); db.close()
    r = client.post("/api/ask/stream", json={"lesson_id": 1, "question": "你好", "context": ""})
    assert r.status_code == 200
    body = r.text
    assert "data: " in body
    assert '"type": "final"' in body
    assert '"answer"' in body


def test_ask_stream_persists_turn(setup_db):
    from app.models import Turn, ModelConfig
    db = SessionLocal()
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit(); db.close()
    r = client.post("/api/ask/stream", json={"lesson_id": 1, "question": "流式问题", "context": ""})
    assert r.status_code == 200
    db = SessionLocal()
    turn = db.query(Turn).filter_by(question="流式问题").first()
    assert turn is not None
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_ask_api.py::test_ask_stream_endpoint -v`
Expected: FAIL（`/api/ask/stream` 不存在，404）

- [ ] **Step 3: 写实现**

修改 `backend/app/routers/notes.py`，在文件顶部补 import：

```python
import asyncio
import json
from fastapi.responses import StreamingResponse
```

在 `ask_ai` 之后新增（注意：`_event_stream` 需要 `CapabilityRegistry`、`StreamBus`、`_extract_citations`、`_filter_citations`、`_persist`，从 `runtime.orchestrator` 和 `capabilities.registry` 导入）：

```python
@router.post("/api/ask/stream")
async def ask_stream(req: AskReq, db: Session = Depends(get_db)):
    from ..models import User
    child = db.query(User).filter_by(role="child").first()
    user_id = child.id if child else 0
    ctx = UnifiedContext(
        user_id=user_id, lesson_id=req.lesson_id, question=req.question,
        text=req.context, mode=req.mode, model=req.model, sentences=req.sentences,
    )
    return StreamingResponse(_event_stream(ctx), media_type="text/event-stream")


async def _event_stream(ctx: UnifiedContext):
    from ..core.stream import StreamBus
    from ..capabilities.registry import CapabilityRegistry
    from ..runtime.orchestrator import _extract_citations, _filter_citations, _persist

    registry = CapabilityRegistry()
    capability = registry.get(ctx.mode)
    stream = StreamBus()
    queue = stream.subscribe()

    task = asyncio.create_task(capability.run(ctx, stream))
    tool_events = []
    results_by_step = {}
    answer = ""
    citations = []

    try:
        while True:
            event = await queue.get()
            if event.type == "tool_call":
                tool_events.append(event)
                yield _sse(event.type, event.data)
            elif event.type == "tool_result":
                results_by_step[event.data.get("step", 0)] = event.data.get("result", {})
                yield _sse(event.type, event.data)
            elif event.type == "final":
                answer = event.data.get("answer", "")
                citations = _filter_citations(_extract_citations(answer), len(ctx.sentences))
                yield _sse("final", {"answer": answer, "citations": citations, "mode": ctx.mode})
                break
            else:
                yield _sse(event.type, event.data)
    finally:
        try:
            await task
        except Exception:
            pass

    _persist(ctx, capability.name, answer, citations, tool_events, results_by_step)


def _sse(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, 'data': data}, ensure_ascii=False)}\n\n"
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_ask_api.py tests/test_notes.py tests/test_stream.py -v`
Expected: PASS（流式 2 个 + 现有非流式 `/api/ask` 3 个 + notes 3 个 + stream 2 个）

注意：`test_ask_stream_endpoint` 用 fake provider → TurnEngine 走降级路径 → forced_finish 发 final 事件，所以 SSE 文本里会有 `"type": "final"` 和 `"answer"`。TestClient 对 StreamingResponse 会等响应流读完，返回完整 body 文本。

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/notes.py backend/tests/test_ask_api.py
git commit -m "feat: 新增 /api/ask/stream SSE 流式端点"
```

---

## Task 3: 前端 chatAsk 流式化

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1: 加 thinkingText 状态变量**

在 `frontend/app.js` 顶部状态区（`chatBusy` 附近，约 line 130）加：

```js
let thinkingText = '正在思考…';   // 流式期间显示的占位文案
```

- [ ] **Step 2: 改 renderImmersiveChat 读 thinkingText**

把 line 1988 的硬编码改为读变量：

```js
  if(chatBusy) list += `<div class="im-msg ai"><div class="bubble" style="color:#aab1ab">${escapeAttr(thinkingText)}</div></div>`;
```

- [ ] **Step 3: 改 chatAsk 为流式 + 加 handleStreamEvent/toolLabel/updateThinking**

替换现有 `chatAsk` 函数（约 line 1954-1973）为流式版本，并新增辅助函数：

```js
async function chatAsk(preset){
  const q = (preset || question || '').trim();
  if(!q || chatBusy) return;
  const ctx = excerpt && excerpt.trim() ? excerpt.trim() : currentText;
  chatMessages.push({role:'user', text:q});
  question = '';
  chatBusy = true;
  thinkingText = '正在思考…';
  renderImmersiveChat();
  const body = {lesson_id:currentLessonId, question:q, context:ctx, mode:chatMode, sentences: splitSentences(ctx)};
  if(chatModel) body.model = chatModel;

  try{
    const resp = await fetch(API + '/api/ask/stream', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body),
    });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while(true){
      const {done, value} = await reader.read();
      if(done) break;
      buf += decoder.decode(value, {stream:true});
      let idx;
      while((idx = buf.indexOf('\n\n')) >= 0){
        const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2);
        const line = chunk.split('\n').find(l=>l.startsWith('data: '));
        if(!line) continue;
        try{
          const evt = JSON.parse(line.slice(6));
          handleStreamEvent(evt);
        }catch(e){ /* 跳过坏事件 */ }
      }
    }
  }catch(err){
    chatMessages.push({role:'ai', text:'抱歉，回答出错了，请稍后再试。', citations:[], mode:chatMode});
  }
  chatBusy = false;
  thinkingText = '正在思考…';
  renderImmersiveChat();
}

function updateThinking(text){
  thinkingText = text;
  renderImmersiveChat();
}

function handleStreamEvent(evt){
  if(evt.type === 'tool_call'){
    updateThinking(`正在${toolLabel(evt.data.tool)}…`);
  } else if(evt.type === 'final'){
    const d = evt.data;
    chatMessages.push({role:'ai', text:d.answer || '（暂无回答）', citations:d.citations || [], mode:d.mode || chatMode});
    renderImmersiveChat();
  }
}

function toolLabel(name){
  return {lookup_word:'查词', search_text:'检索原文', render_mermaid:'画图'}[name] || '思考';
}
```

- [ ] **Step 4: 验证**

前端是纯 JS，无法用 pytest 验证。验证方式：
1. 用 `node --check` 或语法检查确认无语法错误（如果有 node）。
2. 仔细阅读代码确认：`splitSentences`、`escapeAttr`、`renderImmersiveChat`、`renderAnswer` 都在作用域内；`thinkingText`/`updateThinking`/`handleStreamEvent`/`toolLabel` 定义正确、无重名冲突。
3. 确认旧的 `chatAsk` 里的 `await api('/api/ask', ...)` 已被完整替换为流式 fetch。

- [ ] **Step 5: 提交**

```bash
git add frontend/app.js
git commit -m "feat: chatAsk 改流式 SSE 读取（tool_call 更新占位 + final 渲染答案）"
```

---

## Task 4: 全量回归 + 文档

**Files:**
- Modify: `AGENTS.md`（标注 roadmap 第 4 步已落地）

- [ ] **Step 1: 全量回归**

Run: `cd backend && python -m pytest -v`
Expected: 全绿（应 163+ 个测试通过，因为新增了 stream/ask_stream 测试）。

- [ ] **Step 2: 更新 AGENTS.md**

把「Agent-Native Roadmap」第 4 步从「尚未实现」改为「✅ DONE」：

```
4. ✅ **DONE — StreamBus + 流式回放**：`core/stream.py` 的 `StreamBus` 加了
   asyncio.Queue 订阅推送，新增 `/api/ask/stream` SSE 端点（事件级流式：
   stage/tool_call/tool_result/final），前端 `chatAsk` 用 ReadableStream 读取、
   `tool_call` 更新占位、`final` 渲染答案。落库复用 `_persist`。
```

- [ ] **Step 3: 提交**

```bash
git add AGENTS.md
git commit -m "docs: roadmap 第 4 步（前端流式）已落地"
```

---

## 自审记录

- **Spec 覆盖**：设计 5 节 → Task 1（StreamBus Queue）、Task 2（/api/ask/stream 端点 + citations + 落库）、Task 3（前端 chatAsk 流式化）、Task 4（回归 + 文档）。全覆盖。
- **Placeholder 扫描**：无 TBD/TODO。每个代码步骤含完整代码。
- **类型一致性**：`StreamBus.subscribe()` 返回 `asyncio.Queue`（Task 1 定义），Task 2 `queue.get()` 引用一致；`_event_stream` 里 `_sse`/`_persist`/`_extract_citations`/`_filter_citations` 从 orchestrator 导入（Task 2），与 orchestrator 现有签名一致；前端 `thinkingText`/`updateThinking`/`handleStreamEvent`/`toolLabel`（Task 3）命名前后一致。
- **注意点**：`notes.py` 需在文件顶部补 `import asyncio`、`import json`、`from fastapi.responses import StreamingResponse`——Task 2 里明确列出，避免遗漏 import 导致运行时 ImportError。
