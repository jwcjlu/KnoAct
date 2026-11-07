# KnoAct（知学伴）— Architecture

> **定位说明**：KnoAct 目前**不是 agent-native**。AI 以「一次性函数调用」形态
> 散落在后端各处，没有 turn 引擎、没有 capability 编排、没有工具注册表。
> 前端虽已有对话/可视化/解题三种「模式」的界面，但后端实现只是**换一个
> system 提示词字符串再单次 `generate`**，并非真正的 agent 能力。
> 本文如实记录现状，并在最后给出向 agent-native 演进的差距与路径（见
> [Agent-Native Roadmap](#agent-native-roadmap)）。

## Overview

KnoAct（知学伴）是一个面向小学生的 AI 学习伙伴：上传 PDF 教材 →
自动拆课 → AI 提取生词/知识点/课文 → 孩子端做听写、听力、阅读、边读边问测验，
家长端管理教材/目标/任务/规则。后端是 **FastAPI + SQLAlchemy**。前端有三个：
`student-app/` 是 **Flutter 学生端**（Web + Android，Riverpod + go_router），逐步
替代旧版；另有两个**单文件原生 JS** 应用（无框架，`render*()` 函数拼 HTML 字符串）：
`frontend/` 是旧版学生端 Web（已冻结，将由 Flutter 学生 App 取代），`parent-web/`
是独立的家长端。三者均直接调用后端 `/api`。数据库本地开发用 SQLite，
docker-compose 部署用内置的 MySQL 8.4（长文本列在 MySQL 上为 MEDIUMTEXT），所有 AI/语音能力都走可配置的 provider 抽象层，未配置时
回落本地 `fake` 兜底，保证任何环境下都能跑起来。

## Architecture（现状）

```
  student-app/  Flutter 学生端 (Web + Android)
  Riverpod + go_router + dio (docker :8082，nginx 反代 /api)
        │
        │   frontend/  旧版学生端 Web (冻结，待 Flutter 取代)    parent-web/  家长端 (独立)
        │   index.html + app.js (原生 JS，静态托管 :8766)      index.html + app.js (原生 JS，:8767)
        │         │                                                  │
        └─────────┴────────── fetch → http://127.0.0.1:8010/api ─────┘
                               │
                               ▼
┌──────────────────────────────────────────────┐
│            FastAPI (main.py)                 │
│  CORS 全开 · /uploads 静态挂载 · 每日任务调度   │
└──────────────┬───────────────────────────────┘
               │  include_router(...)
┌──────────────┼───────────────────────────────────────────────┐
│   routers/   │                                               │
│  auth config pdf progress notes points learning goals        │
│  mistakes knowledge questions tts annotations home tasks     │
│  quiz mastery users                                          │
└──────────────┼───────────────────────────────────────────────┘
               │  Depends(get_db) · Session
┌──────────────▼───────────────────────────────────────────────┐
│             models.py  (SQLAlchemy ORM)                      │
└──────────────┬───────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────┐
│                    services/                                 │
│   ai (LLM 客户端封装) · model_config (resolve) · mastery      │
│   scheduler · quiz · question_gen · task_gen ·                │
│   lesson_extract · pdf_split · tts                           │
└──────────────────────────────────────────────────────────────┘
```

关键约束：**数据库路径由进程 cwd 决定**。`DATABASE_URL` 默认是
`sqlite:///./zhixueban.db`（相对路径），真实库在 `backend/zhixueban.db`。
启动后端必须从 `backend/` 目录跑（或用绝对 `DATABASE_URL`），否则会在别的
目录生成一个 0 字节空库，看起来「返回空数据」其实是读错了库。

## AI 调用现状：prompt-in-code

当前 AI 有**两种形态**。`/api/ask` 已升级为 **agent-native**：经
`runtime/orchestrator.py` 的 `route_to_capability` → `capabilities/` 选中的
capability → `runtime/turn_engine.py` 的 `TurnEngine` 多步工具循环（调
`tools/` 里注册的 `lookup_word` / `search_text` / `render_mermaid`），并把
`Turn` / `ToolCall` 落库；不再使用 `_MODE_SYSTEM` + 单次 `generate()`。

其余 7 处仍是「构造 prompt → 单次 `generate()` → 解析返回」，
由业务代码直接发起，没有 agent 循环、没有工具调用、没有多步推理。

| 调用点                                | 角色 / 提示词                    | 形态                     |
| ------------------------------------- | -------------------------------- | ------------------------ |
| `routers/notes.py` `/api/ask`         | 学习助手（chat/visualize/solve） | **agent-native**（见下） |
| `routers/quiz.py` 出题 / 判分         | 阅读理解出题 + 判分              | `generate(json_mode)`    |
| `routers/learning.py` 阅读 / 听力材料 | 实时出阅读/听力题（慢，无缓存）   | `generate`               |
| `routers/annotations.py` 生词释义     | 划词查释义                       | `generate`               |
| `services/question_gen.py`            | 阅读理解题（入库/后台，兜底）    | `generate(json_mode)`    |
| `services/quiz.py` `generate_quiz`    | 出题 + evidence 证据校验         | `generate(json_mode)`    |
| `services/lesson_extract.py`          | 拆课提取（生词/知识点/课文）     | `generate` + 正则兜底    |
| `services/ai.py` `ocr_image`          | 扫描版页面 OCR                   | 视觉模型单次调用         |

### 「伪 capability」的现状 —— 已解决

> 此节所述问题**已解决**。三种模式（`chat` / `visualize` / `solve`）现在是
> `capabilities/chat.py` 里的真实 capability（`ChatCapability` /
> `VisualizeCapability` / `SolveCapability`，共同继承 `AgenticChatCapability`），
> 由 `TurnEngine` 多步工具循环驱动，`_MODE_SYSTEM` 已删除。详见下文
> [Agent-Native Roadmap](#agent-native-roadmap) 第 1–3 步已 DONE。

（历史记录）此前 `frontend/app.js` 有对话栏（`chatMessages`/`chatBusy`）、三种
模式 `CHAT_MODES = [chat, visualize, solve]`、模型切换、citations 定位——这些是
**agent-native 的界面雏形**。但后端 `/api/ask` 对「模式」的处理仅是换一段
`_MODE_SYSTEM` 的 system 提示词 + 单次 `generate`：`visualize` 只是靠提示词诱导
模型输出 mermaid 文本，`solve` 只是靠提示词诱导分步，**没有真正的工具在模型
背后执行**。现在这些工具（`render_mermaid` 等）已作为真实工具注册，由 LLM 在
turn 内按需调用。

## Model Configuration Layer

所有 AI/语音能力通过 **三级降级** 解析，入口是
`services/model_config.py` 的 `resolve(db, role)`，绝不抛异常：

```
binding (ModelProfile + ModelConnection)  →  legacy (ModelConfig 老键)  →  default (fake)
```

- **Role**（`provider_registry.REGISTRY` 的 key）：`llm | task | embedding |
  search | tts | stt | imagegen`。`task` 默认**继承 llm**，除非显式配了 profile。
- **Provider**（`provider_registry.ProviderSpec`）：`openai`（中转站/OpenAI 兼容，
  需 `base_url`）、`deepseek`、`glm`、`minimax`、`xunfei`、`fake`（本地兜底）。
- `services/ai.py` 的 `get_provider(db)` 返回 `AIProvider` 子类，统一
  `generate(prompt, system="", json_mode=False)`。OCR 走 `ocr_image(db, image_bytes)`
  （视觉模型取 llm 档的 `options.vision_model`）。
- 密钥掩码：`redact()` / `restore()` 用 `***` 往返，前端保存时不回传明文。

## Domain Services

| Service               | 职责                                                            |
| --------------------- | -------------------------------------------------------------- |
| `pdf_split.py`        | 按学科锚点拆课（`SUBJECT_RULES`）；扫描版走 OCR；`render_pages` 预渲染 PNG |
| `lesson_extract.py`   | 提取课文/生词/知识点，AI 失败回退正则兜底                              |
| `question_gen.py`     | 阅读理解题，任何异常回退 `FALLBACK_QUESTIONS`                          |
| `quiz.py`             | 出题（`generate_quiz`）+ 纯比较判分（`grade_answers`，无 LLM）          |
| `mastery.py`          | 掌握度 `compute_mastery` / 判分 `grade_answer`（逐字复制自 DeepTutor） |
| `scheduler.py`        | 艾宾浩斯复习间隔（`INTERVALS`）+ `next_review_after` / `select_words`  |
| `task_gen.py`         | 每日任务生成（幂等，`generate_daily_tasks` 由 main.py 03:00 触发）      |
| `tts.py`              | TTS provider 抽象（MiniMax / 讯飞 / OpenAI / fake）                     |

## Data Model

见 `backend/app/models.py`。核心关系：

- `PdfDocument` → `Lesson`（拆课结果）→ `WordBank` / `KnowledgePoint` / `Text` /
  `Question` / `Quiz` / `Note` / `Annotation`。
- 掌握度分两层：`WordMastery`（生词，保留旧字段 `correct_count/mistake_count/is_weak`）
  与 `KnowledgeMastery`（知识点）。
- `Task` 有 `UniqueConstraint(user_id, subject, date, task_type)`，每日任务幂等。
- 模型配置三表：`ModelConnection`（凭证+端点，可复用）→ `ModelProfile`（角色下的一档）
  → `RoleBinding`（角色当前启用哪一档，主键即 role）。

## Running / Verification

本地验证有几个反复踩坑的环境事实（详见 memory）：

1. **两个 Python**：Bash 的 `python` 装了全部依赖；PowerShell 终端里的 `python`
   是 conda base，**没装 sqlalchemy**。跑后端用 Bash 的 python。
2. **SQLite 路径随 cwd**：`preview_start` 不遵循 launch.json 的 `cwd`，会从仓库根
   目录起服务、读空库。正确启动：
   ```bash
   cd backend && python -m uvicorn app.main:app --port 8010
   ```
   或绝对路径 `DATABASE_URL="sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db"`。
3. **GBK 管道**：`curl … | python -c "json.load(sys.stdin)"` 会把中文按 GBK 重解码
   报 JSONDecodeError。验证 API 用 `urllib`/`requests` 单进程做请求+解析。
4. **JWT 与管理账号（生产）**：`JWT_SECRET` 在生产环境必须设为长随机密钥（默认
   `dev-change-me` 仅本地）；`ADMIN_INITIAL_PASSWORD` 控制种子为无密码用户及默认
   `login_name=admin` 写入的初始密码（默认 `ChangeMe123`）。部署后应尽快在运营后台改
   `admin` 密码。未正确设置时，后端启动日志会 warning（`pytest` 不触发）。详见仓库根
   `README.md`「生产环境：JWT 与管理员密码」与 `.env.example`。

前端静态页：学生端 `python -m http.server 8766 --directory frontend`，家长端
`python -m http.server 8767 --directory parent-web`，运营后台
`python -m http.server 8768 --directory admin-web`（`API` 默认
`http://127.0.0.1:8010`）。运行配置见 `.claude/launch.json`（prototype/backend/frontend/parent-web 四个）。

Flutter 学生端（`student-app/`）：`flutter run -d chrome`（连 `127.0.0.1:8010`），
安卓必须 `--dart-define=API_BASE=http://10.0.2.2:8010`（模拟器）；`API_BASE=` 空值时
Web 走同源。验证：`flutter analyze && flutter test`（Flutter 位于 `E:\dev\flutter`）。

## Key Files

| Path                                      | Purpose                              |
| ----------------------------------------- | ------------------------------------ |
| `backend/app/main.py`                     | FastAPI 装配 + 每日任务调度器        |
| `backend/app/models.py`                   | 全部 SQLAlchemy 模型                 |
| `backend/app/database.py`                 | engine / SessionLocal / get_db       |
| `backend/app/config.py`                   | `DATABASE_URL`（相对路径，随 cwd）   |
| `backend/app/routers/notes.py`            | `/api/ask` 路由（经 orchestrator 转 capability） |
| `backend/app/routers/`                    | 每领域一个 router                    |
| `backend/app/routers/users.py`            | `GET /api/users?role=child`（家长端孩子列表） |
| `backend/app/services/ai.py`              | `AIProvider` 抽象 + `get_provider` / `ocr_image` |
| `backend/app/services/model_config.py`    | `resolve()` 三级降级 + 密钥掩码      |
| `backend/app/services/provider_registry.py` | provider 白名单（代码常量）         |
| `backend/app/services/mastery.py`         | 掌握度 / 判分（复制自 DeepTutor）    |
| `backend/app/services/pdf_split.py`       | 拆课 + 扫描版 OCR + 页面渲染         |
| `backend/app/seed.py`                     | 种子数据（幂等）                     |
| `backend/app/core/`                       | agent 协议层：`tool_protocol.py`（BaseTool/ToolDefinition）、`context.py`（UnifiedContext）、`stream.py`（StreamEvent/StreamBus）、`capability_protocol.py`（TurnCapability/CapabilityManifest） |
| `backend/app/tools/`                      | `registry.py`（ToolRegistry）+ `builtin.py`（lookup_word/search_text/render_mermaid） |
| `backend/app/runtime/`                    | `turn_engine.py`（TurnEngine 多步工具循环）+ `orchestrator.py`（route_to_capability + _persist 落库 Turn/ToolCall） |
| `backend/app/capabilities/`               | `registry.py`（CapabilityRegistry）+ `chat.py`（Chat/Visualize/Solve 三 capability） |
| `backend/tests/`                          | pytest，`conftest.py` + 每领域 test   |
| `student-app/lib/core/`                   | Flutter 学生端：`router.dart`（登录守卫 + 三 Tab Shell）、`api_client.dart`、`config.dart`（`API_BASE` 解析） |
| `student-app/lib/features/`               | `auth` · `home` · `center` · `profile` · `shell` · `reader`（`/reader/view` pdfrx PDF 页内划选 + 标注墨迹，对齐 Web；`pdf_lesson_reader.dart` / `reader_selection_bar.dart`） |
| `student-app/test/`                       | flutter_test：`app_flow_test.dart`（整 App 流程）+ 每功能 test |
| `student-app/Dockerfile` / `nginx.conf`   | Flutter Web 镜像（自带 CanvasKit）与 nginx 反代/缓存配置 |
| `frontend/index.html` / `frontend/app.js` | 旧版学生端 Web（已冻结，待 Flutter 学生 App 取代；含对话栏 UI） |
| `parent-web/index.html` / `parent-web/app.js` | 家长端（独立单文件原生 JS，调用后端 `/api`） |
| `prototype/`                              | 早期原型（静态）                     |

---

## Agent-Native Roadmap

KnoAct 要对齐 DeepTutor 的 agent-native 架构（turn 引擎 + capability + tool），
需要跨越以下差距。此节是**演进蓝图**：第 1–3 步（Tool 抽象、Turn 引擎、
Capability）已在 `/api/ask` 落地，第 4–5 步（流式、收编其余调用点）尚未实现。

### 现状与目标的差距

| 维度          | 现状（prompt-in-code）                       | 目标（agent-native）                         |
| ------------- | -------------------------------------------- | -------------------------------------------- |
| 调用形态      | 业务代码直接 `generate(prompt)`，一次返回    | LLM 通过**工具调用**在 turn 内多步执行        |
| 能力编排      | 无；「模式」= 换 system 提示词               | `Capability` 接管整个 turn（多 stage）        |
| 工具抽象      | 无；OCR/渲染/判分都是散落的普通函数          | `ToolRegistry` + `BaseTool`，LLM 按需选择    |
| 上下文        | 每次拼一段 prompt，无统一 context            | `UnifiedContext` 规范化上下文                |
| 流式/事件     | 同步 `generate`，前端 polling / 一次性返回   | `StreamBus` 事件协议，异步流式回放           |
| 对话持久化    | 前端内存 `chatMessages`，无服务端 turn 状态  | 服务端持久化 turn 状态，可 replay            |

### 演进路径（建议顺序）

1. ✅ **DONE — 抽 Tool 抽象**（`core/tool_protocol.py`）：`BaseTool` + `ToolDefinition`
   已就绪；`tools/builtin.py` 已把生词释义（`lookup_word`）、知识库检索
   （`search_text`）、渲染（`render_mermaid`）收编为工具，`tools/registry.py`
   的 `ToolRegistry` 统一注册。
2. ✅ **DONE — 引入 Turn 运行时**（`runtime/turn_engine.py` + `core/context.py`）：
   `UnifiedContext` 已建立，`TurnEngine` 把一次 `/api/ask` 变成「一个 turn、
   最多 8 步工具调用」，服务端持久化 `Turn`/`ToolCall`（orchestrator `_persist`）。
3. ✅ **DONE — 把「模式」升级为 Capability**（`capabilities/chat.py`）：
   `chat` / `visualize` / `solve` 各自是拥有 `system_prompt` + `tools` 的
   capability（继承 `AgenticChatCapability`），经 `CapabilityRegistry` 路由，
   替换并删除了 `_MODE_SYSTEM`。
4. ✅ **DONE — StreamBus + 流式回放**：新增 `/api/ask/stream` SSE 端点（事件级
   流式：`stage`/`tool_call`/`tool_result`/`final`），`_event_stream` 用
   `asyncio.create_task` 并发跑 capability + 按索引轮询 `StreamBus.events` 实时
   yield（含 provider 异常竞态处理，保证流必终止）；前端 `chatAsk` 用
   `fetch` + `ReadableStream` 读取，`tool_call` 更新「正在…」占位、`final`
   渲染答案。落库复用 `persist_turn`。
5. ✅ **DONE — 收编散落的 prompt 调用点**：出题/材料生成抽成工具
   （`tools/generation.py`：`generate_listening` / `generate_quiz_questions` /
   `generate_diagnostic_questions`），`listening_material`、`quiz_generate`、
   `ask_questions` 三个端点改调工具，`ask_reply` 改走 TurnEngine（`chat`
   capability，AI 未配置时从 503 变为降级返回）。生词释义已是 `lookup_word`
   工具。OCR / 拆课 / 后台出题（单次确定性调用）保持现状。

> 第 1–5 步全部完成，`/api/ask` 已完全 agent 化，其余交互式/出题调用点也已
> 收编进工具层或 TurnEngine。

## 幻觉补强（已落地）

针对 `/api/ask` agent 化后的四个 LLM 幻觉风险，已做如下补强：

1. **出处句号校验**：前端把已切好的句子数组作为 `sentences` 字段传给后端
   （`UnifiedContext.sentences`），`orchestrator._filter_citations` 剔除越界句号
   （`[第N句]` 的 N 必须 ∈ `1..len(sentences)`），杜绝模型伪造不存在的引用。
2. **`search_text` 按句编号**：`search_text` 工具改用 `ctx.sentences`（回退
   `_fallback_split` 复刻前端 `splitSentences` 规则），句号与前端 `jumpToSentence`
   对齐，消除「行号 vs 句号」错位。
3. **`lookup_word` 如实失败**：查词异常回落 `meaning=""` + `error="释义暂不可用"`
   （不再编造「（示例）」假释义）。
4. **`_forced_finish` 补回约束**：兜底收尾 prompt 补回教材上下文 + 「不要编造
   教材里没有的内容」约束，且 history 为空时不输出空「工具结果」段。
5. **`render_mermaid` 严格校验**：子串匹配改为行首图类型声明正则
   （`graph|flowchart|sequenceDiagram|…`），拒绝 `"photograph of a graph"` 之类
   的伪图。
