# 个性化学习 + 遗忘曲线出题 设计

日期：2026-10-29
状态：已确认，待实现
范围：改造「新课学习」为「个性化学习」，并让每日任务按遗忘曲线出题

## 背景与目标

KnoAct 现有两处「不精准」的出题/学习逻辑：

1. **新课学习**（`startNewLesson`）入口独立，学完 → 答题 → 通过 60% → 推进 `LearningProgress.current_lesson_id`。但没有「选课」环节，来源不清晰，AI 对话无开关。
2. **每日任务出题**（`task_gen.py`）**不看遗忘曲线**：`_gen_dictation` 简单取当前课前 15 个生词，`_gen_knowledge` 取前 5 个知识点，只有 `_gen_review` 用了到期词（但 `WordMastery` 一直为空，导致复习任务永远生成不了）。

目标：

1. 把「新课学习」改造为「个性化学习」——选课（标明来源）→ 分课时阅读（可 AI 对话，测试阶段禁用）→ AI 现场出作业 → 通过后更新进度并落掌握度。
2. 让每日听写/知识点按**遗忘曲线**出题：当天进度课多出（5 新），旧课到期词少出（2 旧），凑不满不硬补。

## 需求参数（已确认）

| 项 | 值 |
|----|-----|
| 每日听写量 | 语文生词 7 个 + 英语单词 7 个（可配置，按学科） |
| 新/旧比例 | 5 新 + 2 旧 |
| 旧课不足时 | 凑不满就少出（不硬补） |
| 作业通过标准 | 正确率 ≥ 阈值（可配置，默认 60%） |
| 作业题数 | 可配置，默认 4 道 |
| 作业出题 | AI 现场出题，基于当前学习内容 |
| 难度 | 三档（简单/中等/困难），默认中等，按学科分别配置 |
| AI 对话 | 复用现有「边读边问」，测试阶段通过开关禁用 |

## 第一部分：个性化学习流程

改造现有「新课学习」为「个性化学习」：

1. **入口**：去掉原「进入下一课」独立入口，改为进入「个性化学习」，先**选课**（列表显示教材来源 + 课程名 + 当前进度标记）。
2. **学习**：复用现有分课时阅读（读课文、划词、笔记）。
3. **AI 对话**：保留「边读边问」，加配置开关 `personalized_disable_chat`（默认 true，测试阶段禁用）。
4. **学完出题**：沿用「读完 → 点『去答题』」节奏，AI 现场出作业题（默认 4 道，难度按学科三档默认中等）。
5. **判分**：正确率 ≥ 阈值（默认 60%）→ 自动推进 `current_lesson_id`。
6. **落掌握度**：每道题答完调 `record_attempt`，更新 `WordMastery`/`KnowledgeMastery` 的 `next_review_at`（遗忘曲线数据源）。

数据流：

```
选课 → 读课文（禁AI对话开关） → 点答题 → AI出4题(按学科难度)
  → 判分 → 通过?
      ├─ 是 → 推进 current_lesson_id + record_attempt 落掌握度
      └─ 否 → 不推进，提示重学
```

## 第二部分：每日任务按遗忘曲线出题

改造 `task_gen.py` 的 `_gen_dictation` / `_gen_knowledge`：

### 听写（dictation）

1. 每天语文生词 7 个 + 英语单词 7 个（配置 `task_dictation_count_语文` / `task_dictation_count_英语`）。
2. 5 新 + 2 旧（配置 `task_new_ratio`，默认「新」5 个）：
   - **5 新** = 当前进度课（`current_lesson_id`）的生词
   - **2 旧** = 其它已学课中「到期该复习」的生词（`WordMastery.next_review_at <= now`，按遗忘曲线排序，错得多的优先）
3. 旧课到期词不足 2 个时，只出「5 新 + 实际到期数」，不硬补。

### 知识点（knowledge）

同理：当天当前课知识点多出（5 个名额），旧课到期知识点少出（2 个名额，按 `KnowledgeMastery.next_review_at`）。

### 前提

依赖 `WordMastery`/`KnowledgeMastery` 有历史数据。当前为空，所以「2 旧」初期为空、实际只出 5 新。随着「个性化学习作业」判分落掌握度（第一部分第 6 步），数据逐渐积累。

数据流：

```
生成任务时：
  当前课生词 → 取 5 个（新）
  到期旧课生词(next_review_at<=now) → 按遗忘曲线排序 → 取 2 个（旧）
  合并 = 当天听写 7 个（旧不足则少）
```

## 第三部分：配置项 + 家长端设置 UI

### 配置项（存 `ModelConfig` 表，复用 `_default_count` 机制）

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `task_dictation_count_语文` | 7 | 语文每日听写量 |
| `task_dictation_count_英语` | 7 | 英语每日听写量 |
| `task_new_ratio` | 5 | 每日任务中「新」的名额（旧 = 总量 - 新） |
| `assignment_question_count` | 4 | 个性化学习作业题数 |
| `assignment_pass_threshold` | 0.6 | 作业通过正确率 |
| `difficulty_语文` / `difficulty_英语` / `difficulty_数学` | 中等 | 各学科出题难度（简单/中等/困难） |
| `personalized_disable_chat` | true | 测试阶段禁用 AI 对话开关 |

### 家长端 UI

新建独立「学习配置」区块（不并入模型配置页），家长可调整：

- 每日听写量（语文/英语各几个）
- 新/旧比例
- 作业题数、通过阈值
- 各学科出题难度（三档下拉）
- 测试开关（禁用 AI 对话）

## 复用策略

- **掌握度/遗忘曲线**：复用 `mastery.py` 的 `record_attempt`（落 `next_review_at`）与 `scheduler.py` 的 `select_words`（「到期 > 错得多」排序）。不新造算法。
- **配置读取**：复用 `_default_count(db, key, fallback)` 模式，扩展到各新配置键。
- **出题**：复用现有 `generate_reading_questions` / `math_gen.generate_math_questions`，新增难度参数。
- **AI 出作业**：新增一个「作业出题」函数（按学科难度 + 当前课内容），可复用 `question_gen.py` 的 prompt 结构。

## 数据模型

无需新表。改动：

- `ModelConfig` 存新配置键（复用现有表）
- `WordMastery` / `KnowledgeMastery` 已有 `next_review_at`（上一阶段已加），无需迁移

## 接口

```
# 新增/调整
GET  /api/learning/lessons?user_id&subject   → 选课列表（含教材来源、当前进度标记）
POST /api/learning/assignment                 → AI 现场出作业（题数/难度按配置）
POST /api/learning/assignment/grade           → 判分 + 落掌握度 + 通过则推进进度

# 配置
GET  /api/config/learning                      → 读学习配置
POST /api/config/learning                      → 改学习配置（家长端）

# 任务生成（调整）
POST /api/tasks/generate                       → 按遗忘曲线出题（已加 force）
```

## 测试

- `backend/tests/test_task_gen.py`（扩展）：
  - `_gen_dictation`：当前课取 5 新 + 到期旧课 2 旧；旧不足则少出
  - `_gen_knowledge`：同理按知识点到期出题
  - 配置键生效（改 `task_dictation_count` 后出题量变化）
- `backend/tests/test_learning.py`（新增或扩展）：
  - 作业出题按难度参数
  - 判分通过阈值推进进度
  - 判分落掌握度（`record_attempt` 被调用）
- 前端 `node --check`

## 明确不做（本阶段）

- 不做「定性通过」的多题型诊断（沿用现有判分）
- 不做错误诊断（LLM 分析错因）
- 不做自适应难度（难度是家长手动配的三档，非自动调）

## 后续

- 测试阶段通过后，放开 AI 对话开关（`personalized_disable_chat=false`）
- 掌握度积累后，复习任务（`_gen_review`）自然能生成到期词
