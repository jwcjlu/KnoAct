# 听力材料纳入每日任务预生成 — Design

日期：2026-10-27

## 背景

`GET /api/listening/material?user_id=4` 每次请求都实时同步调用一次 LLM
（`tools/generation.py` 的 `generate_listening`），耗时约 14s，阻塞孩子端听力页首屏。
根因与 memory 中 [project-perf-ai-slow-calls] 记录的是同一类问题：AI 实时调用未缓存。

对比同文件的 `/api/reading/material`：阅读题首次生成后落库 `Question`，之后命中缓存。
听力接口缺这一步。

## 目标

- 消除听力接口的 14s 实时 LLM 调用。
- 听力材料基于**孩子已学的生词 + 知识点**个性化生成（而非通用一份）。
- 纳入每日定时任务预生成；接口读库秒回，未命中时实时生成兜底。

## 关键约束（已确认）

1. 听力只有英语一科。
2. 「已学生词」= 该孩子当前课（`LearningProgress.current_lesson_id`，回退英语第一课）
   下 `WordBank` 的所有词，取课逻辑与 `_current_lesson` / `_gen_dictation` 一致。
3. 「知识点」= 同课 `KnowledgePoint`。
4. 落库复用 `Task` 表：已有 `UniqueConstraint(user_id, subject, date, task_type)`，
   `task_type` 已预留 `listening`，无需建新表，幂等自动成立。
5. 听力 `Task` 落库时 `content_status` 直接设为 `published`（跳审）——它不是打卡任务，
   而是材料缓存，不应出现在家长端审核列表。

## 改动点

### 1. `backend/app/tools/generation.py` — `GenerateListeningTool` 加个性化参数

`run()` 增两个可选参数：

- `words`：已学生词列表（`list[str]`）
- `knowledge_points`：知识点列表（`list[str]`）

拼进 prompt，让 LLM 只用这些词/点编对话。参数为空时回退到现有通用 prompt，
保持兜底行为，不破坏 `test_generate_listening_returns_structure`。

### 2. `backend/app/services/task_gen.py` — 新增 `_gen_listening` 并接入

- 新增 `_gen_listening(db, lesson)`：
  取该课 `WordBank` 词表 + `KnowledgePoint` 点表，
  调 `generate_listening.run({"words": ..., "knowledge_points": ...}, ctx)`，
  把返回的 `dialogue` / `question` / `answer` 拼成 JSON 存进 `Task.content`，
  `task_type="listening"`、`subject="英语"`、`title="英语听力练习"`、`content_status="published"`。
- 在 `generate_tasks_for_user` 的生成元组中，仅当 `subject == "英语"` 时追加
  `_gen_listening`（语文不出一份听力）。

### 3. `backend/app/routers/learning.py` — 接口改「读库优先、实时兜底」

`/api/listening/material?user_id=4` 逻辑：

1. 查 `Task` 中 `user_id=4, subject="英语", date=今天, task_type="listening"` 第一条。
2. 命中且 `content` 能解析出 dialogue → 直接返回。
3. 未命中 → 走现有实时 `generate_listening` 生成，并顺手落一条 `Task` 记录
   （当天后续访问秒回，与定时任务结果格式一致）。

## 数据流

```
每天 03:00  main.py 调度器
  → generate_daily_tasks(db, today)
    → 每个 child × 英语科
      → _gen_listening(db, lesson)  取词+点 → generate_listening → 落 Task(type=listening, published)

前端点开听力
  → GET /api/listening/material?user_id=4
    → 读 Task(listening, today) 命中 → 秒回
    → 未命中（当天没生成 / 新孩子）→ 实时生成 + 落库兜底
```

## 不做的事（YAGNI）

- 不建新缓存表（复用 `Task`）。
- 不改前端（接口返回结构不变：`{"text", "questions"}`）。
- 不做多份/按课多份听力（每天每孩子一份当天材料即可）。
- 不引入异步任务队列（沿用现有 03:00 定时同步生成）。
