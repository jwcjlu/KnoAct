# KnoAct agent-native 运行时设计（Tool + Turn + Capability）

日期：2026-10-27

## 背景与目标

KnoAct 目前**不是 agent-native**：AI 以「构造 prompt → 单次 `generate()` → 解析返回」
的形态散落在后端 8 处，没有 turn 引擎、capability 编排、工具注册表。前端虽有
对话栏与 `chat/visualize/solve` 三种模式，但后端 `/api/ask` 对「模式」的处理只是
`_MODE_SYSTEM` 里换一段 system 提示词再单次 `generate`，并非真正的 agent 能力。

本次重构引入 agent-native 运行时，范围 = AGENTS.md roadmap 的 **1–3 步**：
Tool 抽象 + Turn 引擎 + Capability。**不包含** roadmap 第 4 步（StreamBus 流式推前端）。

### 已确认的关键决策

| 决策 | 选择 |
| --- | --- |
| 范围 | Tool + Turn + Capability（不做前端流式） |
| 工具调用机制 | JSON 协议自建（LLM 返回 JSON 指定工具，兼容所有 provider 含 fake） |
| 首发场景 | 对话/学习助手（升级 `/api/ask` 三模式） |
| 编排深度 | 多步工具循环（步数上限 8） |
| 状态持久化 | 数据库（新增 Turn / ToolCall 表，可 replay） |
| 兼容策略 | 直接替换 `/api/ask`，前端不改 |
| 架构风格 | async + StreamBus（服务端收集事件，为 roadmap 第 4 步铺路） |
| capability 组织 | 3 个独立类（chat/visualize/solve）+ 共享基类消重 |

## 架构

在 `backend/app/` 下新增三层，依赖方向**单向**（`core` 零依赖 → 上层逐层依赖）：

```
backend/app/
├── core/                          # 协议层（纯 dataclass/ABC，无 DB 依赖）
│   ├── tool_protocol.py           #   BaseTool + ToolDefinition + ToolParameter
│   ├── capability_protocol.py     #   TurnCapability + CapabilityManifest
│   ├── context.py                 #   UnifiedContext
│   └── stream.py                  #   StreamEvent + StreamBus
├── tools/
│   ├── builtin.py                 #   lookup_word / search_text / render_mermaid
│   └── registry.py                #   ToolRegistry
├── runtime/
│   ├── turn_engine.py             #   TurnEngine：多步工具循环
│   └── orchestrator.py            #   路由 UnifiedContext → capability
├── capabilities/
│   ├── chat.py                    #   AgenticChatCapability 基类 + 3 个子类
│   └── registry.py                #   CapabilityRegistry
├── models.py                      # 修改：新增 Turn / ToolCall 表
└── routers/notes.py               # 修改：/api/ask 改走 orchestrator
```

依赖约束：`core` 不依赖任何东西 → `tools`/`capabilities` 依赖 `core` →
`runtime` 依赖 core+tools+capabilities → `routers` 依赖 runtime。**不反向引用**。

## TurnEngine 循环协议（JSON 自建）

```
用户提问 + UnifiedContext(教材文本/lesson/历史对话)
  → for step in 1..MAX_STEPS(=8):
      1. 拼 prompt：system(工具清单 JSON Schema) + 上下文 + 历史(tool_call/result)
      2. provider.generate(json_mode=True)
      3. 解析 JSON：
         - {"final_answer": "..."}  → 结束
         - {"tool": "lookup_word", "args": {...}}
           → 查 ToolRegistry 执行 → 结果 append 进历史 → 回到 1
         - 解析失败 / 超步数 → 强制收尾
  → emit StreamEvent 序列（stage/tool_call/tool_result/final）
  → 持久化 Turn + ToolCall 到 DB
```

要点：

1. **二选一协议**：LLM 每次只返回 `final_answer` 或 `tool` 两种 JSON 之一，判断简单。
2. **工具清单内嵌**：system 里用 JSON Schema 描述可用工具，LLM 靠描述选工具填参数。
3. **历史回填**：每次工具执行后把 `{tool, args, result}` 作为新消息 append，
   下一次 `generate` 能看到之前的结果（多步推理）。
4. **MAX_STEPS=8** 上限，超了强制收尾（把历史交给 LLM 求 final，再失败则报错）。
5. **预留多动作扩展**：当前只实现「单次一个工具」，但 `tool` 字段将来可扩展为
   `tools: [...]` 数组并行多动作，本轮不做。
6. **兼容 fake**：fake 不返回合法 JSON → 走「解析失败→收尾→报错」路径，不崩。

## Tool 层（Level 1）

```python
class BaseTool(ABC):
    name: str
    description: str                        # 给 LLM 看的用途
    parameters: list[ToolParameter]         # 参数 schema
    def to_schema(self) -> dict             # → JSON Schema
    def run(self, args: dict, ctx: UnifiedContext) -> dict   # 同步执行，返回 JSON
```

`ToolParameter` 对齐 DeepTutor：`name/type/description/required/default/enum/items`，
`to_schema()` 生成 JSON Schema property（`type="array"` 时补 `items`）。

首发 3 个工具：

| 工具 | 参数 | 作用 | 来源 |
| --- | --- | --- | --- |
| `lookup_word` | word, lesson_id | 划词释义 | 抽自 `routers/annotations.py` glossary |
| `search_text` | query, lesson_id | 课文/知识点检索，供 citations 定位 | 新写 |
| `render_mermaid` | code | 校验并输出 mermaid 代码块（支撑 visualize 画图） | 新写 |

## Capability 层（Level 2）

```python
class TurnCapability(ABC):
    manifest: CapabilityManifest   # name/description/stages/tools_used
    async def run(self, ctx: UnifiedContext, stream: StreamBus) -> None
```

组织：**3 个独立类 + 共享基类消重**。

```
TurnCapability (ABC)
   └── AgenticChatCapability (共享基类：封装「调 TurnEngine 多步循环」公共逻辑)
          ├── ChatCapability      (name=chat, 全工具, 通用 system)
          ├── VisualizeCapability (name=visualize, tools=[render_mermaid,...], 画图 system)
          └── SolveCapability     (name=solve, 分步解题 system)
```

三模式当前差异（system 提示词 + 工具子集）落在各自 `manifest` + `system_prompt`
属性里；将来加专属 stage 各有位置，互不干扰。

**映射**：原 `_MODE_SYSTEM`（换字符串）→ 3 个 capability（能力自治 + manifest 清晰）。

## 数据模型（新增 2 表）

```python
class Turn(Base):
    __tablename__ = "turns"
    id, user_id(FK users), lesson_id, capability(str),
    mode(str), question(Text), context(Text),
    status(str: 'running'|'done'|'error'),
    final_answer(Text), citations(Text JSON 数组),
    created_at, finished_at

class ToolCall(Base):
    __tablename__ = "tool_calls"
    id, turn_id(FK turns), step(int),
    tool_name(str), args(Text JSON), result(Text JSON),
    created_at
```

设计点：

1. **citations 独立列**：从 `search_text` 工具结果提取，存 `Turn.citations`（JSON 数组文本），
   独立于 `final_answer`。
2. **ToolCall 完整存**：`args`+`result` 全存，支持 replay 推理链。不设上限（教材原文量大，
   清理策略留待后续）。
3. **只存单 turn 内**：跨轮对话历史仍由前端 `context` 参数传回，服务端**不建会话表**，
   避免过度设计。

## `/api/ask` 替换与前端影响

### 后端（直接替换）

```python
@router.post("/api/ask")
async def ask_ai(req: AskReq, db=Depends(get_db)):
    ctx = UnifiedContext(user_id, lesson_id, question, text=req.context,
                         mode=req.mode, model=req.model)
    capability = CapabilityRegistry.get(req.mode)
    stream = StreamBus()
    await capability.run(ctx, stream)          # async 驱动 TurnEngine
    turn = persist_turn(ctx, stream)           # 落 Turn + ToolCall
    return {"answer": turn.final_answer, "citations": turn.citations, "mode": req.mode}
```

**请求/响应契约不变**：前端 `chatAsk` 已 POST `{lesson_id, question, context, mode, model?}`、
期望 `{answer, citations, mode}`，所以**前端无需改动**。

### 前端影响

- 核心结论：**前端不改即可跑通**（响应形状不变）。
- 本轮**不做前端流式**：`/api/ask` 仍是「请求→完整响应」，StreamBus 仅服务端收集事件
  用于落库/trace。前端 `chatBusy` + 「正在思考…」占位已覆盖等待体验。流式留 roadmap 第 4 步。

### 同步/异步桥接

`ai.py` 的 `AIProvider.generate()` 是同步的。capability 是 async，TurnEngine 内统一用
`asyncio.to_thread` 包同步 `generate`，避免阻塞事件循环（FastAPI async endpoint 天然支持）。

## 错误处理（分层降级）

沿用「绝不崩、回退兜底」哲学，`/api/ask` 永不 500：

| 层 | 失败场景 | 处理 |
| --- | --- | --- |
| Provider | 非法 JSON / fake / 无 key | TurnEngine 捕获 → 强制收尾（历史求 final），再失败返回友好文案 |
| 工具 | 工具执行异常 | 工具内 try/except，返回 `{"error": ...}` 作 tool_result 回填 |
| 超步数 | 循环 > 8 | 强制收尾，status='error' 但仍返回已生成答案（若有） |
| 持久化 | Turn/ToolCall 落库失败 | 不影响响应（先返回答案，落库失败记日志） |

## 测试策略

沿用 pytest + fake provider 确定性测试，**用 mock provider 而非真 LLM**：

1. `test_tool_protocol.py`：`ToolParameter.to_schema()` / `BaseTool.to_schema()` 正确。
2. `test_turn_engine.py`（核心）：注入脚本化 fake provider（第一步返回 tool、第二步返回
   final_answer），断言多步回填 / 步数上限 / 非法 JSON 降级 / StreamEvent 序列。
3. `test_capabilities.py`：三 capability 的 manifest 正确、路由（mode→capability）正确、
   mock TurnEngine 断言各自 system 提示词与工具子集。
4. `test_ask_api.py`：`/api/ask` 端到端，mock provider 后断言响应形状不变 + Turn/ToolCall 落库。
5. 回归：现有 `test_notes.py`、`test_annotations.py` 跑绿。

**关键设计**：`TurnEngine` 依赖注入 `AIProvider`（不硬编码 `get_provider(db)`），
让 agent 循环可单测。

## 非目标（本轮不做）

- 前端流式（roadmap 第 4 步）
- 工具并行多动作（预留 `tools: [...]` 扩展位）
- 服务端多轮会话表（跨轮历史仍由前端传）
- 迁移其余 8 处 AI 调用点（`learning.py` 阅读+听力、`quiz.py` 出题+判分、
  `lesson_extract.py` 拆课、`question_gen.py`、`services/quiz.py` generate_quiz、
  `pdf_split.py` ocr_image，后续逐一轮次收编为工具；`config_router.py` 的
  「连接测试」2 处是配置校验，非业务能力，不迁移）
