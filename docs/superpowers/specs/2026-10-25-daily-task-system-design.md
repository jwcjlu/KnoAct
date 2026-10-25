# 今日任务系统设计

日期：2026-10-25
状态：已确认，待实现

## 背景与目标

当前首页「今日学习任务」是一段**前端写死的假数据**（`frontend/app.js` 的 `tasks` 数组，写死「第 12 课」「第 8、10 课」等课程号），不随真实学习进度、科目变化。同时「学习中心」与首页的「智能复习」入口重叠，整体信息杂乱。

本设计将「今日任务」升级为**数据库实体 + 定时生成 + 双阶段家长审核 + 拍照闭环**的完整任务系统，替换写死数组，让首页与家长端都读到真实任务数据。

范围：本次**只做任务系统**（听写/基础练习/复习/阅读理解/听力理解/自由任务），不做「学习报告」「积分商城」「周报」等占位页，也不引入「难度」分级（见下文「明确不做」）。

## 核心概念

一条任务的生命周期：

```
凌晨定时生成 → 待内容审核(pending_review)
  → 家长审核内容（通过/修改/删除/新增）→ 已发布(published)
  → 孩子看到并完成 → 待完成审核(submitted)
  → 家长审核完成（听写看照片）→ 已完成(done) + 发积分
```

两个独立的审核环节：

- **内容审核**：凌晨生成的当天任务，家长先审「今天学这些合不合适」（改/删/增），审完孩子才看得见。
- **完成审核**：孩子做完后，家长审「做对了没」，通过才发积分。听写类需孩子拍照上传，家长看照片核对。

## 任务类型

| task_type | 名称 | 内容来源 | 定时自动生成 |
|-----------|------|----------|--------------|
| `dictation` | 听写 | 当前课 `WordBank` 生词/单词 | 是 |
| `knowledge` | 基础练习 | 当前课 `KnowledgePoint` 知识点 | 是 |
| `review` | 复习 | `WordMastery` 到期词 + 到期知识点 | 是（仅当有到期内容） |
| `reading` | 阅读理解 | 当前课 `Text` + `Question` | 否（家长手动加） |
| `listening` | 听力理解 | AI 生成对话 | 否（家长手动加） |
| `custom` | 自由任务 | 家长手写文字 | 否（家长手动加） |

定时只自动生成教材驱动的三类核心（听写/基础练习/复习）；阅读理解、听力、自由任务由家长手动新增。

## 分科

语文、英语**分开各生成一套任务**。孩子端首页按科目 tab（语文/英语）切换看到对应科的任务，孩子一天既学语文也学英语。

- 生成时按 `subject` 分别取当前课、生词、知识点。
- 任务 `content` 快照内需记录 `subject`，或直接在 `Task` 表加 `subject` 字段区分。

**进度分科的现状缺口**：`LearningProgress` 目前只有单个 `current_lesson_id`（不分科），而 `home.py` 的 `_lesson_progress` 是按 subject 反查序号。任务生成需要「各科的当前课」。需明确：当前课如何按科确定（复用 `home.py` 的按 subject 排序取当前逻辑，或扩展 `LearningProgress` 为分科记录）。实现阶段需先确认这个数据源。

## 数据模型

新增 `Task` 表（`backend/app/models.py`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int PK | |
| `user_id` | FK→users | 属于哪个孩子 |
| `subject` | str | '语文' / '英语' |
| `date` | date | 任务所属日期 |
| `task_type` | str | dictation / knowledge / review / reading / listening / custom |
| `title` | str | 任务标题 |
| `detail` | str | 任务描述（如「15 个重点生词」） |
| `content` | JSON | 任务内容快照（生词列表 / 题目 / 复习词） |
| `points` | int | 完成奖励积分 |
| `content_status` | str | pending_review / published（家长不满意时用 DELETE 删除并重新生成/新增，不引入 rejected 中间态） |
| `submit_status` | str | not_started / submitted / approved |
| `photo_path` | str | 听写拍照上传路径（可空） |
| `reviewed_by` | int | 审核的家长 user_id |
| `difficulty` | str | 预留，本次恒为 null（见「明确不做」） |
| `created_at` | datetime | 生成时间 |

## 定时生成逻辑

**依赖**：新增 `apscheduler==3.10.4`。

**调度器**：`main.py` 启动时挂 `BackgroundScheduler`，每天 03:00（服务器本地时间）跑 `generate_daily_tasks()`。

**生成逻辑**（`backend/app/services/task_gen.py`，独立函数，供定时器与手动触发共用）：

对每个 `role="child"` 用户、每个科目（语文/英语）：

1. **听写** — 取该科当前课 `WordBank` 生词（复用 `learning.dictation_words` 取词逻辑），标题「第 X 课生词听写」，points=20。
2. **基础练习** — 取该科当前课 `KnowledgePoint` 知识点，标题「第 X 课基础知识」，points=20。
3. **复习** — 取 `WordMastery.next_review_at <= now` 的到期词（复用 `scheduler.select_words`），标题「到期复习」，points=25；**无到期内容则不生成**。

**数量**：每类任务的默认数量由家长在「任务设置」配置（见「数量可调」），生成时取默认值。

**幂等**：同一 `(user_id, subject, date)` 只生成一次——生成前查当天是否已有记录，有则跳过，保证手动重跑/重启不重复。

## 接口设计

新增 `backend/app/routers/tasks.py`（前缀 `/api/tasks`）：

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/tasks?user_id=&date=&subject=` | 列出任务（孩子端读 published，家长端读全部） |
| POST | `/api/tasks/generate` | 手动触发当天生成（调试/补生成） |
| POST | `/api/tasks/{id}/approve` | 家长内容审核通过（pending_review→published） |
| POST | `/api/tasks/approve-all` | 全部通过 |
| PUT | `/api/tasks/{id}` | 家长修改任务内容（修改 title/detail 文字，或改「数量」触发重新生成 content 快照） |
| DELETE | `/api/tasks/{id}` | 家长删除任务 |
| POST | `/api/tasks` | 家长新增任务（预设类型自动生成 或 custom 手写） |
| POST | `/api/tasks/{id}/submit` | 孩子提交完成（含听写拍照信息） |
| POST | `/api/tasks/{id}/upload-photo` | 听写拍照上传（multipart） |
| POST | `/api/tasks/{id}/confirm` | 家长完成审核通过 → 发积分 + submit_status=approved |

## 数量可调

- **全局默认（任务设置页）**：家长配置「听写默认 X 词、基础练习默认 X 题」，定时生成按它来。存 `ModelConfig`（key 如 `task_dictation_count`、`task_knowledge_count`）。
- **单条临时改**：审核时家长可单条改数量（`PUT /api/tasks/{id}` 更新 `content` 与 `detail`）。

## 前端交互

### 孩子端首页（`renderHome` 改造）

- 任务卡不再读硬编码 `tasks`，改读 `GET /api/tasks?user_id=&date=today&subject=当前科目`，只显示 `content_status=published` 的任务。
- 任务卡显示真实 title/detail/points，点击进入对应练习（听写/基础练习/阅读/听力）。
- 完成按钮 → `POST /submit`；听写类弹「拍照上传」。
- 任务提交后，卡片显示「已完成，等待家长确认」。

### 家长端

- 新增「任务」tab（现有 tab：教材/知识点/目标/报告/规则/设置）。
- 展示当天任务列表（按科分组），每条：内容、状态（待审核/已发布/待完成审核/已完成）、操作（通过/修改/删除）。
- 「全部通过」按钮、「新增任务」按钮（选类型→自动生成或手写）。
- 孩子提交后显示「待完成审核」，听写类可查看照片 → 通过发积分。
- 任务设置入口：配置每类默认数量。

## 听写拍照

- 孩子端：`<input type="file" accept="image/*" capture>` 拍照或选图。
- 上传到 `/api/tasks/{id}/upload-photo`（multipart），存 `uploads/task_photos/`，路径写入 `Task.photo_path`。
- 家长端：图片 URL 直接 `<img>` 展示核对。

## 明确不做（本次范围外）

- **难度分级**：本次不引入。听写无难度之分；数学、阅读理解等题型未来才有难度，届时再给 `Task` 加难度分级逻辑（`difficulty` 字段已预留）。
- **学习报告 / 积分商城**：仍为占位页（已有 TODO 标记），本次不实现。
- **周报（week_stats）**：后端仍无学习时长/打卡数据源，本次不实现。
- **数学科目**：本次任务系统仅覆盖语文、英语；数学拆课/出题/难度后续再做。

## 待实现阶段确认的技术点

1. **分科当前课数据源**：`LearningProgress` 现为单值 `current_lesson_id`，需确认如何按科取当前课（复用 `home.py` 逻辑 或 扩展分科进度）。
2. **APScheduler 与 uvicorn reload**：`--reload` 模式下调度器可能被重复创建，需确保单例（或在非 reload 时启动）。
3. **听写拍照存储目录**：`uploads/task_photos/` 需加入静态挂载（现有 `/uploads` 已挂载，子目录应可直接访问）。
