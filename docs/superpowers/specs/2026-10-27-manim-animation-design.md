# Manim 数学动画能力设计

> 日期：2026-10-27
> 状态：设计已确认，待实现

## 1. 背景与目标

KnoAct（知学伴）是面向小学生的 AI 学习伙伴。当前数学相关的可视化只有
`visualize` capability，通过 `render_mermaid` 工具让 LLM 输出 mermaid 文本、
前端渲染成**静态图**，没有动画。

本项目要补齐 **manim 数学动画能力**：让 LLM 在对话中按需生成 manim 代码，
渲染成**带旁白音轨的成品视频**（画面 + 讲解同步），供孩子观看。这是「真正
manim」+「带音轨视频」的完整落地。

### 关键决策（已与用户确认）

| 决策点 | 结论 |
| --- | --- |
| 核心目标 | 数学 manim 动画，**带旁白音轨的成品视频**（画面+旁白同步） |
| 渲染形态 | **独立渲染服务**（Manim + ffmpeg + LaTeX 单独打包） |
| 数学表现力 | LaTeX 必备，正规数学公式/坐标系/几何是硬需求 |
| 触发入口 | `render_manim` 新工具，进 `visualize` capability 的 agent 循环 |
| 工具性质 | **异步提交型**（立即返回 task_id，渲染在后台） |
| 渲染+纠错 | 在渲染服务内部闭环（LLM 出代码→渲染→失败重试） |
| 旁白 | LLM 生成讲解稿 + TTS，画面旁白同源，粗对齐 |
| 状态持久化 | 新增 `RenderTask` 模型 + `/api/render/{task_id}` 轮询 |
| 渲染服务技术栈 | Python + FastAPI |
| TTS | 复用现有 provider 抽象（MiniMax/讯飞/OpenAI/fake） |
| 部署 | 打包可分发 / 上服务器（Docker 镜像 + docker-compose） |

## 2. 整体架构与数据流

```
孩子问「给我演示分数相加」
        │
        ▼
   /api/ask  ──► orchestrator ──► visualize capability
        │                            │
        │                      TurnEngine 循环
        │                            │ LLM 决定调用工具
        │                            ▼
        │                      render_manim 工具
        │                            │ ① 提交任务，立即返回 task_id
        │                            ▼
        │                     渲染服务（独立容器）
        │                     ├─ ② LLM 生成 manim 代码
        │                     ├─ ③ manim render → mp4
        │                     ├─ ④ TTS 生成旁白
        │                     ├─ ⑤ ffmpeg 合成音轨（画面+旁白同步）
        │                     └─ ⑥ 存视频，回报状态
        │                            │
        ▼                            ▼
   前端 SSE 流：先收到 task_id（「动画渲染中…」）
        │
        ▼
   前端轮询进度 ──► 渲染完成 ──► 拿到 mp4 URL ──► 播放带旁白的动画
```

**核心设计点：**

1. **`render_manim` 是「异步提交型」工具**——它不像 `lookup_word` 那样同步返回
   结果，而是提交一个渲染任务到渲染服务，**立即返回 `task_id` + 一个「渲染中」
   占位**，让 turn 循环能继续跑、能出最终回答，不被几十秒的渲染卡死。

2. **渲染 + 纠错循环发生在渲染服务内部，不在 TurnEngine 里**——LLM 生成 manim
   代码容易出错，渲染服务自己负责「渲染失败 → 把错误喂回 LLM → 重试」，主服务
   的 agent 循环不感知这个细节。

3. **前端两条通道**：主对话走现有 SSE（拿 `task_id`），视频进度走独立轮询
   （拿渲染状态 + 最终 mp4 URL）。

4. **优雅降级**（符合 KnoAct「未配置降级 fake」哲学）：渲染服务没起时，
   `render_manim` 返回「渲染服务不可用」+ 附上 manim 代码文本，前端降级为展示
   代码/静态说明，不报错。

## 3. 渲染服务内部设计

渲染服务是一个独立的 FastAPI 容器，只做一件事：**收 manim 代码/指令 → 渲染成
带旁白的视频 → 回报状态和 mp4 URL**。它不碰主服务的数据库，主服务也不懂 manim。

### 3.1 接口

主服务 → 渲染服务，两个端点：

| 端点 | 作用 |
| --- | --- |
| `POST /render` | 提交任务。入参 `{ task_id, prompt, narration, voice, quality }`（`voice` 选 TTS 音色；LLM/TTS provider 配置由渲染服务连库自读，见 §3.4）。立即返回 `202 Accepted`（不等待渲染）。 |
| `GET /render/{task_id}` | 查进度。返回 `{ status, video_url?, error?, progress? }` |

`status` 枚举：`queued | generating | rendering | mixing | done | error`。

任务队列用**进程内队列 + 有限并发**（渲染吃 CPU，同时最多 2–3 个，防打爆容器）。

### 3.2 渲染流水线（每个任务内部）

```
① 生成代码  LLM(prompt) → manim Python 代码
      ↓ 失败/语法错
② 渲染      manim render → 视频帧 → mp4（静音）
      ↓ 失败（manim 报错）
      把 stderr 喂回 LLM 纠错，回到 ①（最多重试 3 次）
③ 旁白      TTS(讲解稿) → audio
④ 合成      ffmpeg 把 audio 对齐合成进 mp4 → final.mp4
⑤ 落盘      视频存到渲染服务的 /media 目录，回报 done + URL
```

**关键点：**

1. **「生成代码 → 渲染 → 纠错重试」是渲染服务内部的闭环**，纠错只在这一处发生，
   主服务 agent 循环完全不感知。

2. **旁白文本由 LLM 生成、与 manim 代码同源**——保证旁白和画面讲的是同一件事。
   这是「带音轨视频」成立的关键。讲解稿既作为 TTS 输入，也用于对齐。

3. **粗对齐**：ffmpeg 合成时旁白总时长决定视频时长。第一版做「旁白总时长 ≈
   视频时长」的粗对齐；精确到帧的「动画到哪句旁白」对齐留作后置。

4. **重依赖打包**：容器装 `manim` + `ffmpeg` + **TeX Live 数学子集**，镜像体积
   大（预计 1–2GB），但**只此一处**，主服务镜像保持轻量。本地 docker-compose 起，
   服务器独立容器。

### 3.3 资源与安全（「可分发」约束下的硬要求）

- **超时**：单个任务整体超时（120s），超时标记 error，防止卡死占坑。
- **并发上限**：同时渲染 ≤ 3，队列排队，前端显示「排队中」。
- **代码沙箱**：LLM 生成的 manim 代码是要执行的 Python 代码，有任意代码执行风险。
  第一版用**容器本身做隔离**（渲染服务跑在无敏感数据的容器、非 root、无主服务
  网络访问、磁盘只写 /media）。更强的沙箱（每任务独立容器）留作后置。

### 3.4 配置来源

渲染服务**自己连主服务数据库读配置**，复用 `model_config.resolve(db, role)` 和
`get_tts(db)` 的 provider 解析逻辑（LLM 走 `role="llm"`，TTS 走 `role="tts"`），
不跨服务透传密钥。

实现方式：渲染服务 import 主服务的 `models.py`（ORM）+ `database.py`
（`SessionLocal`）+ `services/model_config.py`，通过 `DATABASE_URL` 环境变量指向
同一个库。SQLite 场景下需用**绝对路径** `DATABASE_URL`（相对路径随 cwd 漂移，
见 AGENTS.md 环境陷阱）；MySQL 场景天然共享。

> 注意：渲染服务与主服务是**两个进程**，SQLite 并发写需留意。本场景渲染服务
> 只**读**配置（`ModelConnection` / `ModelProfile` / `RoleBinding` / `ModelConfig`），
> 不写库，读写竞争风险低。

## 4. 主服务侧：`render_manim` 工具 + 状态持久化

### 4.1 `render_manim` 作为「提交型」工具

`BaseTool.run` 保持同步——`render_manim` 的 `run()` 只做「调渲染服务
`POST /render` 拿 task_id」，这个 HTTP 调用很快，同步执行没问题：

```python
class RenderManimTool(BaseTool):
    name = "render_manim"
    description = "把数学概念渲染成带旁白的动画视频，返回渲染任务 id"
    parameters = [
        ToolParameter(name="prompt", type="string",
                      description="要演示的数学概念，如「演示 1/2+1/4=3/4」"),
        ToolParameter(name="narration", type="string",
                      description="旁白讲解稿（小学生能听懂的话）", required=False),
    ]

    def run(self, args, ctx):
        task_id = render_client.submit(prompt=..., narration=..., ...)
        return {"task_id": task_id, "status": "submitted", "video_url": None}
```

返回值 JSON 可序列化，**TurnEngine 无需改动**。差异只在语义：`task_id` 是「去
轮询的凭证」，不是最终答案。

### 4.2 状态持久化 —— 新增 `RenderTask` 模型

新增 SQLAlchemy 模型（`models.py`）：

```
RenderTask
  id (PK)
  task_id (渲染服务返回的 id, 唯一)
  user_id
  turn_id (关联哪次对话触发，可空)
  prompt / narration
  status: submitted|queued|generating|rendering|mixing|done|error
  video_url
  error
  created_at / updated_at
```

主服务提供两个轻端点供前端轮询：

| 端点 | 作用 |
| --- | --- |
| `GET /api/render/{task_id}` | 返回状态 + video_url。主服务先查本地 `RenderTask`，中间态再透传问一次渲染服务，更新本地缓存。 |
| （可选）`/api/render/{task_id}/stream` | SSE，渲染完成时推 `done`。第一版先轮询，SSE 后置。 |

### 4.3 前端展示（现有对话栏 UI）

孩子问「演示分数相加」后，对话流里：

1. `tool_call` 事件：显示「正在准备动画…」占位（复用现有 `tool_call` 占位机制）。
2. `final` 事件：LLM 基于工具结果，用一句小学生能懂的话收尾，把 `task_id` 附在
   最终消息里。
3. 前端拿到 `task_id` 后，在消息里渲染**视频卡片**：先显示「渲染中…/排队中…」
   进度条，轮询 `/api/render/{task_id}`，`done` 后换成 `<video>` 播放带旁白动画。
4. 降级：`error` 时卡片显示「动画生成失败」+ 附 manim 代码折叠块（若返回了代码）。

### 4.4 capability 挂载

`render_manim` 注册进 `ToolRegistry`，加进 `visualize` capability 的 `tools`
列表（**不新建 `math` capability**）。TurnEngine 的 system prompt 已有「可用工具
列表」注入，LLM 看到 `render_manim` 的描述和参数就会在合适时调用。**「什么数学
问题值得做动画」由 LLM 判断**，工具描述里引导（如「当孩子需要直观演示几何/分数/
运算过程时调用」）。

## 5. 分阶段落地计划

跨「新渲染服务 + 新工具 + 新模型 + 前端改动」，拆三阶段，每阶段独立验证。

### 阶段 1：渲染服务骨架 + 最小链路（MVP 跑通）

- **目标**：独立容器能把「写死的 manim 代码 + 写死的旁白」渲染成带音轨的 mp4。
- 内容：`POST /render` + `GET /render/{id}` + 进程内队列 + `manim render` +
  `ffmpeg` 合音轨 + 复用 `services/tts.py` 的 provider 抽象（fake/真实任一）。
- 验证：`curl` 提交写死任务，拿到 mp4 能播放、有声音。
- **不碰**主服务、LLM 生成代码、前端。

> 这是全项目最大不确定性（依赖、渲染、合成），先消除它。

### 阶段 2：接 LLM 生成代码 + 纠错循环

- **目标**：渲染服务能自己「LLM 出 manim 代码 → 渲染 → 失败纠错重试」。
- 内容：渲染服务内接 LLM（配置由任务透传，见 §3.4）+ 纠错闭环（≤3 次）。
- 验证：给数学意图，自动出代码、渲染、纠错、产出视频。

### 阶段 3：接入主服务 agent 循环 + 前端

- **目标**：孩子在对话里能触发动画。
- 内容：主服务 `render_manim` 工具 + `RenderTask` 模型 + `/api/render/{task_id}`
  端点 + 挂进 `visualize`；前端视频卡片 + 轮询进度 + 降级展示。
- 验证：真实对话「演示分数相加」→ 占位 → 进度 → 播放带旁白动画。

## 6. 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| LLM 生成的 manim 代码质量不稳 | 阶段 2 纠错循环 + 工具描述里给「manim 代码最小可用模板」，避免从零生成 |
| 模型配置进渲染服务 | 渲染服务自己连库读配置，复用 `resolve`/`get_tts`，`DATABASE_URL` 绝对路径（§3.4） |
| TeX Live 体积/安装 | 数学子集；阶段 1 就装进镜像并验证公式渲染 |
| 并发与超时 | 严格限并发 + 整体超时，防坏动画拖垮队列 |
| 代码执行安全 | 容器隔离（非 root、无网络、只写 /media）兜底 |
| 旁白/画面同步 | 第一版粗对齐（总时长≈），帧级同步后置 |

## 7. 关键文件（预计新增/改动）

| Path | 改动 |
| --- | --- |
| `render_service/`（新目录，与 backend 平级） | 独立渲染服务：FastAPI app + 队列 + manim/ffmpeg/TTS 编排 + Dockerfile；import 主服务 `models`/`database`/`services` 读配置 |
| `backend/app/tools/builtin.py` | 新增 `RenderManimTool`（提交型工具） |
| `backend/app/tools/registry.py` | 注册 `render_manim` |
| `backend/app/capabilities/chat.py` | `visualize` 的 `tools` 加 `render_manim` |
| `backend/app/models.py` | 新增 `RenderTask` 模型 |
| `backend/app/routers/`（新文件或并入现有） | `/api/render/{task_id}` 端点 |
| `frontend/app.js` / `index.html` | 视频卡片 + 进度轮询 + 降级 |
| `docker-compose.yml`（或 render_service 内） | 编排渲染服务容器 |
