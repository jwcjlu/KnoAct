# KnoAct 前端流式设计（roadmap 第 4 步）

日期：2026-10-27

## 背景

agent-native 运行时已落地，但 `/api/ask` 仍是「请求 → 完整响应」，前端一次 `await` 拿全部结果。多步工具循环（最多 8 步）和 LLM 调用期间，用户只看到「正在思考…」占位，看不到中间过程。本次引入 SSE 流式，把 capability 执行过程中的事件实时推给前端。

## 已确认的关键决策

| 决策 | 选择 |
| --- | --- |
| 传输机制 | SSE / 分块流（`text/event-stream`） |
| 端点策略 | 新增 `/api/ask/stream`，保留 `/api/ask` 不动 |
| StreamBus 改造 | asyncio.Queue 订阅推送（保留 events 列表兼容非流式） |
| 事件流结构 | 逐事件 + final 收尾 |
| citations 计算 | 流式端点自己算（复用 `_extract_citations` / `_filter_citations`） |
| 落库 | 流式路径也落库（复用 `_persist`） |

## 设计

### 1. StreamBus 改造（Queue 订阅推送）

`core/stream.py` 现在是同步 `emit → append`。改造为双通道：

```python
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
        self.events.append(event)          # 同步收集（兼容非流式）
        if self._queue is not None:
            self._queue.put_nowait(event)  # 实时推送（流式路径）

    def subscribe(self) -> asyncio.Queue:
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue
```

- `events` 列表保留（`route_to_capability` 非流式路径 + `_persist` 依赖）。
- `_queue` 惰性创建，只有流式端点 `subscribe()` 才触发。
- `put_nowait` 非阻塞（queue 无界），SSE 生成器在另一协程 `await queue.get()`。

### 2. `/api/ask/stream` 端点

```python
@router.post("/api/ask/stream")
async def ask_stream(req: AskReq, db: Session = Depends(get_db)):
    from ..models import User
    child = db.query(User).filter_by(role="child").first()
    user_id = child.id if child else 0
    ctx = UnifiedContext(user_id=user_id, lesson_id=req.lesson_id,
                         question=req.question, text=req.context,
                         mode=req.mode, model=req.model, sentences=req.sentences)
    return StreamingResponse(_event_stream(ctx), media_type="text/event-stream")
```

`_event_stream` 异步生成器，并发跑 capability + 读 queue：

```python
async def _event_stream(ctx):
    registry = CapabilityRegistry()
    capability = registry.get(ctx.mode)
    stream = StreamBus()
    queue = stream.subscribe()          # 先订阅，拿到实时队列

    task = asyncio.create_task(capability.run(ctx, stream))
    tool_events = []
    results_by_step = {}

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
                final_data = {"answer": answer, "citations": citations, "mode": ctx.mode}
                yield _sse("final", final_data)
                break
            else:
                yield _sse(event.type, event.data)
    finally:
        # 确保 capability 跑完（落库完成）；客户端断开时也等它自然结束
        try:
            await task
        except Exception:
            pass

    # 落库（复用 _persist）
    _persist(ctx, capability.name, answer, citations, tool_events, results_by_step)
```

`_sse` 辅助函数：

```python
def _sse(event_type: str, data: dict) -> str:
    import json
    return f"data: {json.dumps({'type': event_type, 'data': data}, ensure_ascii=False)}\n\n"
```

要点：

- `asyncio.create_task(capability.run(...))` 让 capability 后台跑，主协程读 queue 逐条 yield。
- `tool_call` / `tool_result` 原样透传（同时收集供 `_persist`），`final` 特殊处理（补 citations + mode）。
- break 后 `await task` 确保落库完成；`answer` / `citations` 在 break 前已赋值。
- 客户端断开时 `yield` 抛 GeneratorExit，`finally` 里 `await task` 等 capability 自然结束（TurnEngine 有 MAX_STEPS 上限，不会无限跑）。

### 3. citations 复用

`_event_stream` 直接 import 复用 `orchestrator._extract_citations` 和 `orchestrator._filter_citations`，不重复实现。

### 4. 前端 `chatAsk` 改造

用 `fetch` + `ReadableStream` 逐条读 SSE：

```js
async function chatAsk(preset){
  const q = (preset || question || '').trim();
  if(!q || chatBusy) return;
  const ctx = excerpt && excerpt.trim() ? excerpt.trim() : currentText;
  chatMessages.push({role:'user', text:q});
  question = '';
  chatBusy = true;
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
        try {
          const evt = JSON.parse(line.slice(6));
          handleStreamEvent(evt);
        } catch(e) { /* 跳过坏事件 */ }
      }
    }
  }catch(err){
    chatMessages.push({role:'ai', text:'抱歉，回答出错了，请稍后再试。', citations:[], mode:chatMode});
  }
  chatBusy = false;
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

要点：

- 保留 `chatBusy` + 「正在思考…」占位；`tool_call` 事件更新占位文案，`final` 替换为最终答案。
- `toolLabel` 把工具名映射成中文标签。
- SSE 解析：按 `\n\n` 分隔，找 `data: ` 前缀行，`JSON.parse`。
- 失败降级走现有 catch 分支。

## 错误处理

| 层 | 失败场景 | 处理 |
| --- | --- | --- |
| capability 抛异常 | TurnEngine 内部已降级（fake/非法 JSON → forced_finish → final），正常不抛到外层 | `_event_stream` finally 里 `await task` 包 try/except |
| 客户端断开 | 前端提前关连接 | 生成器 GeneratorExit → finally `await task` 等 capability 自然结束（有步数上限） |
| 落库失败 | `_persist` 已吞异常记日志 | 不影响流（final 已推） |
| 前端 SSE 解析失败 | 某条事件 JSON 坏 | `handleStreamEvent` 外层 try/catch 跳过坏事件 |

## 测试

1. `test_stream_bus_subscribe`：`StreamBus.subscribe()` 后 emit 的事件同时进 `events` 和 queue。
2. `test_ask_stream_endpoint`：TestClient 请求 `/api/ask/stream`，断言 SSE 文本含 `data: ` 和 `final` 事件、格式正确。
3. `test_ask_stream_persists`：流式请求后 Turn 落库。
4. 回归：现有 `test_ask_api.py`（非流式 `/api/ask` 仍工作）、`test_turn_engine.py` 全绿。

## 非目标

- 不做 WebSocket（单向问→答场景，SSE 足够）。
- 不改 `/api/ask` 非流式端点（保留兼容）。
- 不做 token 级流式（只做事件级流式，粒度是 stage/tool_call/tool_result/final）。
- 不迁移其余调用点、不建多轮会话表、不做工具并行（另立任务）。
